from decimal import Decimal
from uuid import uuid4
from urllib.parse import urlsplit, parse_qs
import pytest
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.database import engine
from app.models.credits import CreditCustomer, CreditMovement, CreditMovementChange
from app.services import credits as service
from tests.test_credit_accounts import person, add, balance, draft


def change_values(identifier, **changes):
    with Session(engine) as db:
        row = db.get(CreditMovement, identifier)
        return dict(entry_key=str(uuid4()), version=str(db.get(CreditCustomer,row.customer_id).version),
            movement_version=str(row.version), amount=str(int(abs(row.delta))),
            entry_date=str(row.entry_date), observation=row.observation, **changes)


def test_edit_detail_keeps_products_money_and_period_and_records_original(client):
    owner=person(); purchase=add(owner,amount="45000",observation="Torta\n2 alfajores")
    add(owner,kind="payment",amount="45000")
    page=client.get(f"/fiados/movimientos/{purchase}/editar")
    assert page.status_code==200 and "Torta\n2 alfajores" in page.text and 'value="45.000"' in page.text
    values=change_values(purchase); values['observation']='Torta\n3 alfajores'
    for _ in range(2):
        assert client.post(f"/fiados/movimientos/{purchase}/editar",data=values,follow_redirects=False).status_code==303
    assert balance(owner)==0
    with Session(engine) as db:
        row=db.get(CreditMovement,purchase)
        assert row.observation=='Torta\n3 alfajores' and row.delta==45000 and row.version==2
        audit=db.scalar(select(CreditMovementChange))
        assert audit.before['observation']=='Torta\n2 alfajores'
        assert audit.after['observation']=='Torta\n3 alfajores'
        assert db.scalar(select(func.count()).select_from(CreditMovementChange))==1
        assert len(db.execute(select(service.closed_periods_statement(owner))).all())==1
    values['observation']='Otro texto'
    assert client.post(f"/fiados/movimientos/{purchase}/editar",data=values).status_code==409


def test_money_edits_and_soft_delete_recalculate_all_views(client):
    owner=person(); purchase=add(owner,amount='10000')
    values=change_values(purchase); values['amount']='15.000'
    assert client.post(f'/fiados/movimientos/{purchase}/editar',data=values).status_code==200
    assert balance(owner)==15000
    payment=add(owner,kind='payment',amount='5000')
    stale=change_values(purchase)
    values=change_values(payment)
    assert client.post(f'/fiados/movimientos/{payment}/eliminar',data=values,follow_redirects=False).status_code==303
    assert client.post(f'/fiados/movimientos/{payment}/eliminar',data=values,follow_redirects=False).status_code==303
    assert balance(owner)==15000
    assert client.post(f'/fiados/movimientos/{purchase}/editar',data=stale).status_code==409
    assert client.get(f'/fiados/movimientos/{payment}/editar').status_code==404
    with Session(engine) as db:
        assert db.get(CreditMovement,payment).delta==Decimal('-5000')
        assert db.get(CreditMovement,payment).deleted_at is not None
        assert len(db.execute(service.history_statement(owner)).all())==1
        assert db.execute(service.accounts_statement()).one()[1]==15000
        statement=service.whatsapp_statement(db,owner,entire=True)
        assert 'Pago*' not in statement['message'] and '$ 15.000' in statement['message']


def test_invalid_edits_and_paid_purchase_deletion_leave_no_effect(client):
    owner=person(); purchase=add(owner,amount='10000'); add(owner,kind='payment',amount='8000')
    values=change_values(purchase)
    assert client.post(f'/fiados/movimientos/{purchase}/eliminar',data=values).status_code==422
    values['amount']='1000'
    assert client.post(f'/fiados/movimientos/{purchase}/editar',data=values).status_code==422
    values['amount']='1,50'
    assert client.post(f'/fiados/movimientos/{purchase}/editar',data=values).status_code==422
    assert balance(owner)==2000
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(CreditMovementChange))==0
        with pytest.raises(IntegrityError):
            db.execute(text("UPDATE credit_movements SET observation='sin control'"))
        db.rollback()


def test_audit_cannot_be_changed_and_delete_requires_csrf(client):
    owner=person(); purchase=add(owner)
    values=change_values(purchase); values['observation']='Corregido'
    client.post(f'/fiados/movimientos/{purchase}/editar',data=values)
    with Session(engine) as db:
        with pytest.raises(IntegrityError):
            db.execute(text('DELETE FROM credit_movement_changes'))
        db.rollback()
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as anonymous:
        assert anonymous.post(f'/fiados/movimientos/{purchase}/eliminar',data=change_values(purchase)).status_code==403


def test_concurrent_edits_keep_one_version_and_one_audit():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    owner=person(); purchase=add(owner); barrier=Barrier(2)
    forms=[change_values(purchase),change_values(purchase)]
    forms[0]['observation']='Primer cambio'; forms[1]['observation']='Segundo cambio'
    def execute(values):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            try:
                service.change_movement(db,purchase,values)
                return 'saved'
            except service.CreditConflict:
                db.rollback()
                return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(execute,forms))==['conflict','saved']
    with Session(engine) as db:
        assert db.get(CreditMovement,purchase).version==2
        assert db.scalar(select(func.count()).select_from(CreditMovementChange))==1


@pytest.mark.parametrize('raw,expected',[('2920000000','2920000000'),('', ''),('1123456789','1123456789')])
def test_phone_normalization(raw,expected):
    assert service.normalize_phone(raw)==expected


def test_person_names_normalize_each_word_without_merging_people(client):
    owner=person('gonzalo PEREZ')
    with Session(engine) as db:
        assert db.get(CreditCustomer,owner).name=='Gonzalo Perez'
    other=person('GONZALO perez',alias='Otra persona')
    assert owner!=other
    owner2=person('  maría   GÓMEZ ')
    with Session(engine) as db:
        assert db.get(CreditCustomer,owner2).name=='María Gómez'
    page=client.get(f'/fiados/{owner}')
    assert 'Gonzalo Perez' in page.text


@pytest.mark.parametrize('raw',['005491123456789','+54 9 abc','123','+1;alert(1)','9'*16,'5491123456789','2920 000000','2920-000000','2920.000000','2920000000 ','02920000000','１１００００００００'])
def test_invalid_phone(raw):
    with pytest.raises(ValueError): service.normalize_phone(raw)


def test_phone_edit_and_whatsapp_message_are_explicit_and_complete(client):
    owner=person(); first=add(owner,amount='10000',observation='Torta & alfajores\nRetira el viernes')
    person('Marcela Pérez',alias='Otra persona')
    with Session(engine) as db:
        customer=db.get(CreditCustomer,owner)
        values={'entry_key':str(uuid4()),'name':customer.name,'alias':customer.alias,'phone':'1123456789','version':str(customer.version)}
    assert client.post(f'/fiados/personas/{owner}',data=values).status_code==200
    add(owner,kind='payment',amount='2500',observation='Pago en el local')
    with Session(engine) as db:
        data=service.whatsapp_statement(db,owner)
        assert data['person'].phone=='1123456789'
        assert 'Torta & alfajores\nRetira el viernes' in data['message']
        assert '*Saldo pendiente: $ 7.500*' in data['message']
        assert '$ 2.500' in data['message'] and 'Pago en el local' in data['message']
        url=urlsplit(data['whatsapp_links'][0]); assert url.netloc=='wa.me' and url.path=='/5491123456789'
        assert parse_qs(url.query)['text'][0]==data['message']
    page=client.get(f'/fiados/{owner}/whatsapp')
    assert page.status_code==200 and 'Abrir WhatsApp' in page.text and 'noopener noreferrer' in page.text


def test_long_whatsapp_keeps_all_entries_and_no_phone_has_no_external_link(client):
    owner=person()
    for index in range(27): add(owner,observation=f'Producto {index:02d} · '+'detalle '*60)
    with Session(engine) as db:
        row=db.get(CreditCustomer,owner);row.phone='1100000000';db.commit()
        data=service.whatsapp_statement(db,owner,entire=True)
        assert len(data['whatsapp_links'])>1
        combined='\n'.join(parse_qs(urlsplit(url).query)['text'][0] for url in data['whatsapp_links'])
        for index in range(27): assert f'Producto {index:02d}' in combined
        assert '$ 27.000' in combined
        row.phone='';db.commit()
    page=client.get(f'/fiados/{owner}/whatsapp')
    assert 'Agregar celular' in page.text and 'href="https://wa.me/' not in page.text
