from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from threading import Barrier
from uuid import uuid4
import re
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.main import app
from app.core.database import engine
from app.models.credits import CreditCustomer, CreditMovement, CreditLegacyLink
from app.models.registers import CustomerCredit
from app.services import credits as service
from app.services.listings import business_today
from app.services.money import require_grouped_pesos
from tests.test_migrations import migrate, scratch_database
from tests.test_simple_business import csrf


def person(name="Marcela Pérez", **changes):
    with Session(engine) as db:
        row = service.save_customer(db, {"entry_key": str(uuid4()), "name": name,
            "alias": "", "distinct_person": "1", **changes})
        return row.id


def draft(identifier, **changes):
    with Session(engine) as db:
        row = service.customer(db, identifier)
        return {"entry_key": str(uuid4()), "customer_id": str(identifier), "version": str(row.version),
            "kind": "purchase", "amount": "1000", "entry_date": str(business_today()),
            "observation": "Ejemplo ficticio", **changes}


def add(identifier, **changes):
    with Session(engine) as db:
        row = service.save_movement(db, draft(identifier, **changes))
        return row.id


def balance(identifier):
    with Session(engine) as db:
        return service.account_balance(db, identifier)


def legacy(**changes):
    with Session(engine) as db:
        row = CustomerCredit(entry_key=str(uuid4()), customer="Cliente ficticio anterior", amount=Decimal("8500"),
            observation="Original", entry_date=date(2020, 1, 2), paid=False, version=1)
        for key, value in changes.items():
            setattr(row, key, value)
        db.add(row); db.commit()
        return row.id, service.legacy_hash(row)


@pytest.mark.parametrize("raw,result", [("10000",10000),("10.000",10000),("1.234.567",1234567),
    ("000123",123),("9999999999999999",9999999999999999)])
def test_whole_grouped_money_is_exact(raw, result):
    assert require_grouped_pesos(raw) == Decimal(result)


@pytest.mark.parametrize("raw", ["10,00","10,000","1.50","1.000,00","123.99","1e4","NaN","Infinity",
    "-1","+2","１２３","1 000","10000000000000000",""])
def test_ambiguous_money_is_never_reinterpreted(raw):
    with pytest.raises(ValueError):
        require_grouped_pesos(raw)


def test_purchases_payments_settlement_and_new_period_keep_every_movement(client):
    identifier = person()
    first = add(identifier, amount="5.000", entry_date="2026-11-01")
    add(identifier, amount="10.000", entry_date="2026-11-02")
    add(identifier, amount="30.000", entry_date="2026-11-03")
    payload = draft(identifier, kind="payment", amount="25.000", entry_date="2026-11-10")
    preview = client.post("/fiados", data=payload)
    assert preview.status_code == 200 and "Confirmar pago" in preview.text and "$ 20.000" in preview.text
    assert balance(identifier) == 45000
    paid = client.post("/fiados", data={**payload,"confirmed":"1"})
    assert paid.status_code == 200 and balance(identifier) == 20000
    assert client.post("/fiados",data={**payload,"confirmed":"1"}).status_code == 200
    settle = draft(identifier,kind="settlement",amount="20.000",confirmed="1")
    assert client.post("/fiados",data=settle).status_code == 200 and balance(identifier) == 0
    history = client.get(f"/fiados/{identifier}?history=1")
    assert "Saldado" in history.text and history.context["periods"].total == 1
    add(identifier,amount="12.000")
    current = client.get(f"/fiados/{identifier}")
    assert "$ 12.000" in current.text and current.context["movements"].total == 1
    assert "Historial (1 saldado)" in current.text
    prior = client.get(f"/fiados/{identifier}?history=1&cycle_end=5")
    assert prior.status_code == 200 and prior.context["movements"].total == 5 and "$ 25.000" in prior.text
    with Session(engine) as db:
        assert db.get(CreditMovement,first).delta == Decimal("5000")
        assert db.scalar(select(func.count()).select_from(CreditMovement)) == 6
        for table in ("payments","invoices","business_entries","salary_payments"):
            assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0


@pytest.mark.parametrize("amount", ["0","-1","1,50","1.50","1.000,00","1001"])
def test_invalid_and_excess_payments_leave_no_effect(client, amount):
    identifier=person(); add(identifier)
    data=draft(identifier,kind="payment",amount=amount,confirmed="1")
    response=client.post("/fiados",data=data)
    assert response.status_code == 422
    assert balance(identifier) == 1000
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(CreditMovement)) == 1


def test_unselected_name_and_unknown_id_cannot_choose_a_person(client):
    identifier=person()
    for values in ({"customer_id":"","customer_query":"Marcela Pérez"},{"customer_id":"999999"}):
        response=client.post("/fiados",data=draft(identifier,**values))
        assert response.status_code == 422
    assert balance(identifier) == 0


def test_server_search_is_partial_accent_insensitive_and_literal(client):
    first=person("Marcela Pérez",alias="Vecina del centro")
    second=person("Juan PÉREZ")
    person("Ana López")
    special=person("Cliente _100%")
    for query in ("perez","PÉREZ","PeReZ"):
        assert {p['id'] for p in client.get('/fiados/personas/buscar',params={"q":query}).json()} == {first,second}
    assert [p['id'] for p in client.get('/fiados/personas/buscar?q=centro').json()] == [first]
    assert [p['id'] for p in client.get('/fiados/personas/buscar?q=perez+marc').json()] == [first]
    assert [p['id'] for p in client.get('/fiados/personas/buscar',params={"q":"_100%"}).json()] == [special]
    assert client.get('/fiados/personas/buscar',params={"q":"x"*151}).status_code == 422


def test_names_never_merge_and_creation_requires_explicit_similarity_review(client):
    identifier=person()
    payload={"entry_key":str(uuid4()),"name":"MARCELA PEREZ","alias":"Homónima ficticia"}
    warned=client.post('/fiados/personas',data=payload)
    assert warned.status_code == 422 and 'Confirmo que es otra persona' in warned.text
    created=client.post('/fiados/personas',data={**payload,"distinct_person":"1"})
    assert created.status_code == 200
    with Session(engine) as db:
        rows=list(db.scalars(select(CreditCustomer)))
        assert len(rows)==2 and len({p.id for p in rows})==2 and identifier in {p.id for p in rows}
    assert client.post('/fiados/personas',data={**payload,"distinct_person":"1"}).status_code==200


def test_combined_customer_and_purchase_roll_back_together_on_invalid_amount(client):
    values={"entry_key":str(uuid4()),"new_customer":"1","name":"Lucía Torres","alias":"Ejemplo",
        "kind":"purchase","amount":"0","entry_date":str(business_today())}
    assert client.post('/fiados',data=values).status_code==422
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(CreditCustomer))==0
    values['amount']='10.000'
    assert client.post('/fiados',data=values).status_code==200
    assert client.post('/fiados',data=values).status_code==200
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(CreditCustomer))==1
        assert db.scalar(select(func.count()).select_from(CreditMovement))==1


def test_rename_keeps_ids_and_rejects_obsolete_forms(client):
    identifier=person(); add(identifier)
    stale=draft(identifier)
    with Session(engine) as db:
        original=db.get(CreditCustomer,identifier)
        service.save_customer(db,{"entry_key":str(uuid4()),"name":"Marcela Pérez Gómez","alias":"Centro",
            "version":str(original.version)},identifier)
    assert client.post('/fiados',data=stale).status_code==409
    assert balance(identifier)==1000
    assert client.get(f'/fiados/{identifier}').context['person'].id==identifier


def test_same_key_different_payload_is_rejected(client):
    identifier=person(); data=draft(identifier,amount='10.000')
    assert client.post('/fiados',data=data).status_code==200
    assert client.post('/fiados',data={**data,'amount':'20.000'}).status_code==409
    assert balance(identifier)==10000


@pytest.mark.parametrize('same_key',[True,False])
def test_concurrent_payments_cannot_duplicate_or_overdraw(same_key):
    identifier=person(); add(identifier)
    first=draft(identifier,kind='payment',amount='1000')
    second={**first,'entry_key':first['entry_key'] if same_key else str(uuid4())}
    barrier=Barrier(2)
    def attempt(payload):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            try:
                return service.save_movement(db,payload).id
            except service.CreditConflict:
                db.rollback(); return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids=list(pool.map(attempt,[first,second]))
    assert balance(identifier)==0
    assert ids[0]==ids[1] if same_key else ids.count(None)==1
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(CreditMovement))==2


def test_concurrent_similar_creation_warns_instead_of_creating_twice():
    barrier=Barrier(2)
    def attempt(_):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            try:
                service.save_customer(db,{'entry_key':str(uuid4()),'name':'Nombre repetido'}); return True
            except service.SimilarCustomers:
                db.rollback(); return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt,range(2)))==[False,True]


def test_corrections_append_reversal_and_do_not_change_original(client):
    identifier=person(); original_id=add(identifier,amount='10.000')
    data={'entry_key':str(uuid4()),'version':draft(identifier)['version'],'reason':'Importe cargado por error'}
    response=client.post(f'/fiados/movimientos/{original_id}/anular',data=data)
    assert response.status_code==200 and balance(identifier)==0
    assert client.post(f'/fiados/movimientos/{original_id}/anular',data=data).status_code==200
    assert client.post(f'/fiados/movimientos/{original_id}/anular',data={**data,'entry_key':str(uuid4()),
        'version':draft(identifier)['version']}).status_code==409
    with Session(engine) as db:
        assert db.get(CreditMovement,original_id).delta==10000
        reversal=db.scalar(select(CreditMovement).where(CreditMovement.reversal_of==original_id))
        assert reversal.delta==-10000 and reversal.observation==data['reason']
    with pytest.raises(IntegrityError), engine.begin() as db:
        db.execute(text('UPDATE credit_movements SET delta=1 WHERE id=:id'),{'id':original_id})
    with pytest.raises(IntegrityError), engine.begin() as db:
        db.execute(text('DELETE FROM credit_movements WHERE id=:id'),{'id':original_id})


def test_reversing_paid_purchase_cannot_create_credit_but_payment_can_be_reversed(client):
    identifier=person(); purchase=add(identifier); pay=add(identifier,kind='payment')
    data={'entry_key':str(uuid4()),'version':draft(identifier)['version'],'reason':'Corrección ficticia'}
    assert client.post(f'/fiados/movimientos/{purchase}/anular',data=data).status_code==422
    assert balance(identifier)==0
    assert client.post(f'/fiados/movimientos/{pay}/anular',data={**data,'entry_key':str(uuid4())}).status_code==200
    assert balance(identifier)==1000


def test_legacy_review_moves_only_verified_pending_balance_and_keeps_original(client):
    identifier=person(); legacy_id,fingerprint=legacy()
    with Session(engine) as db:
        original={c.name:getattr(db.get(CustomerCredit,legacy_id),c.name) for c in CustomerCredit.__table__.columns}
    home=client.get('/fiados')
    assert home.context['legacy']['count']==1 and home.context['legacy']['debt']==8500
    payload={**draft(identifier),'source_hash':fingerprint}
    assert client.post(f'/fiados/anteriores/{legacy_id}/vincular',data=payload).status_code==200
    assert client.post(f'/fiados/anteriores/{legacy_id}/vincular',data=payload).status_code==200
    assert balance(identifier)==8500
    with Session(engine) as db:
        row=db.get(CustomerCredit,legacy_id)
        assert {c.name:getattr(row,c.name) for c in CustomerCredit.__table__.columns}==original
        assert db.scalar(select(CreditMovement.kind))=='opening'
    assert client.get('/fiados').context['legacy']['count']==0
    assert 'Original' in client.get(f'/fiados/{identifier}?history=1').text
    with pytest.raises(IntegrityError), engine.begin() as db:
        db.execute(text('UPDATE customer_credits SET amount=1 WHERE id=:id'),{'id':legacy_id})
    with pytest.raises(IntegrityError), engine.begin() as db:
        db.execute(text('DELETE FROM credit_legacy_links WHERE legacy_credit_id=:id'),{'id':legacy_id})


@pytest.mark.parametrize('paid_date',[None,date(2020,1,3)])
def test_paid_legacy_is_archive_without_invented_payment_or_dates(client,paid_date):
    identifier=person(); legacy_id,fingerprint=legacy(paid=True,paid_date=paid_date,amount=Decimal('10.25'))
    payload={**draft(identifier),'source_hash':fingerprint}
    assert client.post(f'/fiados/anteriores/{legacy_id}/vincular',data=payload).status_code==200
    assert balance(identifier)==0
    page=client.get(f'/fiados/{identifier}?history=1')
    assert 'Importe histórico para revisar' in page.text and '$ 10,25' not in page.text
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(CreditMovement))==0
        row=db.get(CustomerCredit,legacy_id)
        assert row.paid_date==paid_date and row.paid_at is None and row.created_at is None


def test_unresolved_cents_changed_source_and_removed_legacy_do_not_migrate(client):
    identifier=person(); legacy_id,fingerprint=legacy(amount=Decimal('1.25'))
    data={**draft(identifier),'source_hash':fingerprint}
    assert client.get('/fiados').context['legacy']['needs_review']
    assert client.post(f'/fiados/anteriores/{legacy_id}/vincular',data=data).status_code==422
    with engine.begin() as db:
        db.execute(text('UPDATE customer_credits SET observation=:value WHERE id=:id'),{'value':'Cambió','id':legacy_id})
    assert client.post(f'/fiados/anteriores/{legacy_id}/vincular',data=data).status_code==409
    with engine.begin() as db:
        db.execute(text('UPDATE customer_credits SET deleted_at=now() WHERE id=:id'),{'id':legacy_id})
    assert client.post(f'/fiados/anteriores/{legacy_id}/vincular',data=data).status_code==404
    assert client.get('/fiados').context['legacy']['count']==0
    assert balance(identifier)==0


def test_legacy_mutating_urls_are_retired_and_need_csrf():
    identifier,_=legacy()
    with TestClient(app) as guest:
        page=guest.get('/fiados/nuevo')
        for path in (f'/fiados/{identifier}/paid',f'/fiados/{identifier}/delete'):
            assert guest.post(path,data={}).status_code==403
            assert guest.post(path,data={'csrf_token':csrf(page)}).status_code==409
    with Session(engine) as db:
        row=db.get(CustomerCredit,identifier)
        assert not row.paid and row.deleted_at is None


def test_dates_backdated_after_settlement_keep_prior_period_and_future_is_rejected(client):
    identifier=person(); add(identifier,entry_date='2026-11-10'); add(identifier,kind='payment',entry_date='2026-11-15')
    add(identifier,entry_date='2026-11-01',amount='12000')
    with Session(engine) as db:
        assert service.current_boundary(db,identifier)==2
    page=client.get(f'/fiados/{identifier}')
    assert page.context['movements'].total==1 and '01/11/2026' in page.text
    bad=draft(identifier,entry_date=str(business_today()+timedelta(days=1)))
    assert client.post('/fiados',data=bad).status_code==422 and balance(identifier)==12000


def test_filters_totals_and_sql_pagination_share_same_accounts(client):
    ids=[person(f'Persona ficticia {n:02}') for n in range(27)]
    for identifier in ids[:2]:add(identifier)
    debt=client.get('/fiados')
    assert debt.context['accounts'].total==2 and debt.context['total']==2000
    clear=client.get('/fiados?state=clear')
    assert clear.context['accounts'].total==25 and clear.context['total']==0
    all_rows=client.get('/fiados?state=all&page=2')
    assert all_rows.context['accounts'].total==27 and len(all_rows.context['accounts'].items)==2
    assert all_rows.context['total']==2000


def test_form_uses_overlay_combobox_and_formatted_integer_field_without_removed_help(client):
    identifier=person()
    page=client.get(f'/fiados/nuevo?customer_id={identifier}')
    assert page.status_code==200 and 'role="combobox"' in page.text and 'role="listbox"' in page.text
    assert 'inputmode="numeric"' in page.text and 'data-credit-money' in page.text
    assert 'Pesos enteros, sin puntos ni comas.' not in page.text
    payload=draft(identifier,observation='<img src=x onerror=alert(1)>')
    assert client.post('/fiados',data=payload).status_code==200
    assert '&lt;img src=x onerror=alert(1)&gt;' in client.get(f'/fiados/{identifier}').text


def test_migration_keeps_all_legacy_rows_without_automatic_names_or_payments(scratch_database):
    migrate(scratch_database,'0016_credit_deletion')
    with scratch_database.begin() as db:
        db.execute(text("""INSERT INTO customer_credits(entry_key,customer,amount,observation,entry_date,paid,version,deleted_at)
            VALUES ('SIM-1','Marcela Perez',1000,'Original','2020-01-01',false,2,NULL),
                   ('SIM-2','Marcela Pérez',12.25,'Pagado sin fecha','2020-01-02',true,1,NULL),
                   ('SIM-3','MARCELA PEREZ',2000,'Eliminado','2020-01-03',false,3,now())"""))
        before=db.execute(text('SELECT * FROM customer_credits ORDER BY id')).all()
    migrate(scratch_database)
    with scratch_database.connect() as db:
        assert db.execute(text('SELECT * FROM customer_credits ORDER BY id')).all()==before
        for name in ('credit_customers','credit_movements','credit_legacy_links'):
            assert db.scalar(text(f'SELECT count(*) FROM {name}'))==0
    with pytest.raises(RuntimeError,match='respaldo verificado'):
        migrate(scratch_database,'0016_credit_deletion',downgrade=True)


@pytest.mark.parametrize('amount',['0.5','1.001','10000000000000000'])
def test_database_rejects_fractional_or_out_of_range_money_without_rounding(amount):
    identifier=person()
    with pytest.raises(IntegrityError), engine.begin() as db:
        db.execute(CreditMovement.__table__.insert().values(customer_id=identifier,account_seq=1,
            entry_key=str(uuid4()),payload_hash='0'*64,kind='purchase',delta=Decimal(amount),
            entry_date=business_today(),actor='test'))
    assert balance(identifier)==0


def test_transaction_failure_rolls_back_customer_and_first_purchase(client,monkeypatch):
    record=service._record
    def fail(*args,**kwargs):
        record(*args,**kwargs)
        raise RuntimeError('SIMULATED FAILURE AFTER INSERT')
    monkeypatch.setattr(service,'_record',fail)
    payload={'entry_key':str(uuid4()),'new_customer':'1','name':'Persona de rollback',
        'kind':'purchase','amount':'10000','entry_date':str(business_today())}
    with pytest.raises(RuntimeError,match='SIMULATED'):
        client.post('/fiados',data=payload)
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(CreditCustomer))==0
        assert db.scalar(select(func.count()).select_from(CreditMovement))==0


def test_lost_ack_after_commit_can_retry_same_uuid_without_double_effect(client,monkeypatch):
    identifier=person(); data=draft(identifier)
    original_record=service._record; original_commit=Session.commit
    def record(db,*args,**kwargs):
        result=original_record(db,*args,**kwargs)
        db.info['fail_ack']=True
        return result
    def commit(db):
        original_commit(db)
        if db.info.pop('fail_ack',False):raise RuntimeError('SIMULATED LOST ACK')
    monkeypatch.setattr(service,'_record',record); monkeypatch.setattr(Session,'commit',commit)
    with pytest.raises(RuntimeError,match='LOST ACK'):client.post('/fiados',data=data)
    assert balance(identifier)==1000
    assert client.post('/fiados',data=data).status_code==200
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(CreditMovement))==1
