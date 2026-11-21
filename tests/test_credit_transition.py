from decimal import Decimal
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models.credits import CreditCustomer, CreditMovement, CreditLegacyLink
from app.models.registers import CustomerCredit
from app.services import credits
from scripts.transition_credit_legacy import source_rows, prepare, apply, fingerprints
from tests.test_credit_accounts import legacy


def sources():
    legacy(customer='Persona Única',amount=Decimal('1000'))
    legacy(customer='Archivo Único',amount=Decimal('500'),paid=True)
    legacy(customer='Nombre Repetido',amount=Decimal('200'))
    legacy(customer='nombre repetido',amount=Decimal('300'))
    from app.models.billing import utcnow
    legacy(customer='Baja',amount=Decimal('400'),deleted_at=utcnow())


def test_transition_keeps_originals_unknown_dates_and_defers_homonyms():
    sources()
    with engine.begin() as connection:
        with Session(bind=connection,join_transaction_mode='create_savepoint',expire_on_commit=False) as db:
            rows=source_rows(db); original=fingerprints(rows);plan=prepare(rows)
            result=apply(db,plan)
            assert result['mapped_rows']==2 and result['deferred_rows']==2 and result['deleted_untouched']==1
            assert Decimal(result['mapped_debt'])==1000 and Decimal(result['deferred_debt'])==500
            assert apply(db,plan)==result
            assert fingerprints(source_rows(db))==original
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(CreditCustomer))==2
        assert db.scalar(select(func.count()).select_from(CreditLegacyLink))==2
        assert db.scalar(select(func.count()).select_from(CreditMovement))==1
        assert db.scalar(select(func.count()).select_from(CustomerCredit).where(CustomerCredit.paid_at.is_not(None)))==0


def test_transition_failure_rolls_back_all_people_links_and_openings(monkeypatch):
    sources(); original=credits.link_legacy; calls=0
    def fail_later(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==2: raise RuntimeError('SIMULATED FAILURE')
        return original(*args,**kwargs)
    monkeypatch.setattr(credits,'link_legacy',fail_later)
    with pytest.raises(RuntimeError,match='SIMULATED'), engine.begin() as connection:
        with Session(bind=connection,join_transaction_mode='create_savepoint',expire_on_commit=False) as db:
            apply(db,prepare(source_rows(db)))
    with Session(engine) as db:
        for model in (CreditCustomer,CreditMovement,CreditLegacyLink):
            assert db.scalar(select(func.count()).select_from(model))==0


def test_changed_source_or_incomplete_plan_is_rejected_without_writes():
    sources()
    with Session(engine) as db:
        plan=prepare(source_rows(db));plan['assignments'].pop()
        with pytest.raises(RuntimeError,match='omite'):
            apply(db,plan)
        db.rollback()
        plan=prepare(source_rows(db));plan['source']['1']='bad'
        with pytest.raises(RuntimeError,match='originales cambiaron'):
            apply(db,plan)


def test_integrity_fingerprint_detects_changed_original():
    from scripts.verify_credit_transition import snapshot,verify
    sources(); before=snapshot()
    verify(before,snapshot())
    with Session(engine) as db:
        row=db.scalar(select(CustomerCredit).where(CustomerCredit.customer=='Persona Única'))
        row.observation='Cambio sintético';db.commit()
    with pytest.raises(RuntimeError,match='customer_credits'):
        verify(before,snapshot())
