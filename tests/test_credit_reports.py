import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from tests.test_credit_accounts import person, add
from tests.test_migrations import migrate, scratch_database


def test_local_phone_migration_converts_only_argentine_prefix_and_preserves_records(scratch_database):
    migrate(scratch_database,'0018_credit_updates')
    with scratch_database.begin() as db:
        db.execute(text("""INSERT INTO credit_customers(entry_key,name,search_text,phone)
          VALUES ('first','Prueba uno','prueba uno','5492920000000'),
                 ('second','Prueba dos','prueba dos','1123456789'),
                 ('third','Prueba tres','prueba tres','')"""))
        db.execute(text("""INSERT INTO credit_movements(customer_id,account_seq,entry_key,payload_hash,kind,delta,entry_date,actor)
          SELECT id,1,'movement',repeat('a',64),'purchase',1000,'2026-11-20','test' FROM credit_customers WHERE entry_key='first'"""))
        before=db.execute(text('SELECT * FROM credit_movements')).all()
    migrate(scratch_database,'0019_credit_local_phone')
    with scratch_database.connect() as db:
        assert db.execute(text('SELECT phone,version FROM credit_customers ORDER BY id')).all()==[
            ('2920000000',2),('1123456789',1),('',1)]
        assert db.execute(text('SELECT * FROM credit_movements')).all()==before
    with pytest.raises(DBAPIError), scratch_database.begin() as db:
        db.execute(text("UPDATE credit_customers SET phone='2920 000000'"))


def test_phone_migration_rejects_ambiguous_legacy_without_loss(scratch_database):
    migrate(scratch_database,'0018_credit_updates')
    with scratch_database.begin() as db:
        db.execute(text("""INSERT INTO credit_customers(entry_key,name,search_text,phone)
          VALUES ('first','Prueba','prueba','5492920000000'),('other','Anterior','anterior','59899123456')"""))
        before=db.execute(text('SELECT * FROM credit_customers ORDER BY id')).all()
    with pytest.raises(DBAPIError,match='formatos ambiguos'):
        migrate(scratch_database)
    with scratch_database.connect() as db:
        assert db.execute(text('SELECT * FROM credit_customers ORDER BY id')).all()==before
        assert db.scalar(text('SELECT version_num FROM alembic_version'))=='0018_credit_updates'


def test_name_migration_keeps_separate_identities_and_movements(scratch_database):
    migrate(scratch_database,'0019_credit_local_phone')
    with scratch_database.begin() as db:
        db.execute(text("""INSERT INTO credit_customers(entry_key,name,alias,search_text)
          VALUES ('first','gonzalo PEREZ','vecino','gonzalo perez vecino'),
                 ('second','GONZALO perez','otro','gonzalo perez otro')"""))
        before=db.execute(text('SELECT id,entry_key,alias FROM credit_customers ORDER BY id')).all()
    migrate(scratch_database)
    with scratch_database.connect() as db:
        assert db.execute(text('SELECT id,entry_key,alias FROM credit_customers ORDER BY id')).all()==before
        assert db.execute(text('SELECT name FROM credit_customers ORDER BY id')).scalars().all()==['Gonzalo Perez','Gonzalo Perez']


def test_reports_newest_record_first_without_metadata_or_delete_link(client):
    owner=person()
    old=add(owner,amount='1000',entry_date='2026-11-20',observation='Primera compra')
    recent=add(owner,amount='2000',entry_date='2026-11-01',observation='Última carga con fecha anterior')
    page=client.get(f'/fiados/{owner}')
    assert page.status_code==200
    assert [row.id for row,_ in page.context['movements'].items]==[recent,old]
    assert page.text.index('Última carga con fecha anterior')<page.text.index('Primera compra')
    assert '<th>Detalle</th>' in page.text and '<th>Importe</th>' in page.text
    assert 'Registrado ' not in page.text and 'Registro #' not in page.text
    assert f'/movimientos/{recent}/eliminar' not in page.text
    assert 'Saldo $' not in page.text
    edit=client.get(f'/fiados/movimientos/{recent}/editar')
    assert f'/fiados/movimientos/{recent}/eliminar' in edit.text
    assert 'Última carga con fecha anterior' in edit.text


def test_closed_period_uses_same_report_order_and_whatsapp_controls(client):
    owner=person(); purchase=add(owner,amount='1000'); payment=add(owner,kind='payment',amount='1000')
    summary=client.get(f'/fiados/{owner}?history=1')
    assert '<th>Fecha de cierre</th>' in summary.text
    page=client.get(f'/fiados/{owner}?history=1&cycle_end=2')
    assert [row.id for row,_ in page.context['movements'].items]==[payment,purchase]
    assert 'whatsapp?entire=true' in page.text and 'whatsapp-icon' in page.text
    whatsapp=client.get(f'/fiados/{owner}/whatsapp')
    assert 'Actualizar detalle' not in whatsapp.text and '>Incluir<' not in whatsapp.text
    assert 'WhatsApp abre con el texto preparado' not in whatsapp.text
    assert whatsapp.text.index('data-inline-notice')<whatsapp.text.index('<pre class="credit-message">')
    assert 'class="notice error" data-inline-notice' in whatsapp.text
