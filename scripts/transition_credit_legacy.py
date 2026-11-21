"""Plan privado y aplicación atómica de Fiados anteriores, sin inferir homónimos.

No inicia la web ni el worker. El plan se guarda en el mismo equipo que la DB.
Las coincidencias repetidas requieren vinculación humana desde la interfaz.
"""
import argparse
from collections import defaultdict
from decimal import Decimal
import json
import os
from pathlib import Path
import unicodedata
from uuid import NAMESPACE_URL, uuid5
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.core.config import ENV, INTEGRATIONS_MODE
from app.core.database import engine
from app.models.registers import CustomerCredit
from app.models.credits import CreditLegacyLink, CreditMovement
from app.services import credits


def command_key(kind, identifier):
    return str(uuid5(NAMESPACE_URL, f"arca-dys:credit-legacy-v1:{kind}:{identifier}"))


def source_rows(db):
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    return list(db.scalars(select(CustomerCredit).order_by(CustomerCredit.id).with_for_update()))


def fingerprints(rows):
    return {str(row.id): credits.legacy_hash(row) for row in rows}


def prepare(rows):
    groups = defaultdict(list)
    for row in rows:
        if row.deleted_at is None:
            key = " ".join(unicodedata.normalize("NFC",row.customer).split()).casefold()
            groups[key].append(row)
    assignments, deferred = [], []
    for name, members in groups.items():
        if not name or len(members)>1:
            deferred.extend({"id":row.id,"reason":"Revisar identidad: nombre repetido o vacío"} for row in members)
        else:
            row = members[0]
            if not row.paid and row.amount != row.amount.to_integral_value():
                deferred.append({"id":row.id,"reason":"Conciliar importe anterior con fracción"})
            else:
                assignments.append({"id":row.id,"name":" ".join(word.capitalize() for word in row.customer.split())})
    return {"format":1,"source":fingerprints(rows),"assignments":sorted(assignments,key=lambda item:item['id']),
            "deferred":sorted(deferred,key=lambda item:item['id'])}


def apply(db, plan):
    rows = source_rows(db)
    if plan.get('format')!=1 or plan.get('source')!=fingerprints(rows):
        raise RuntimeError("Los originales cambiaron; repetir el ensayo privado antes de aplicar")
    active = {row.id for row in rows if row.deleted_at is None}
    mapped = [item['id'] for item in plan['assignments']]
    deferred = [item['id'] for item in plan['deferred']]
    if len(mapped+deferred)!=len(set(mapped+deferred)) or set(mapped+deferred)!=active:
        raise RuntimeError("El plan omite o repite registros anteriores")
    by_id = {row.id:row for row in rows}
    opening_ids = []
    for item in plan['assignments']:
        row = by_id[item['id']]
        previous = db.get(CreditLegacyLink,row.id)
        if previous:
            if previous.entry_key != command_key('link',row.id):
                raise RuntimeError("Existe una vinculación ajena al plan; revisar sin sobrescribir")
            if previous.opening_movement_id:
                opening_ids.append(previous.opening_movement_id)
            continue
        person = credits.save_customer(db, {'entry_key':command_key('person',row.id),
            'name':item['name'],'alias':'','phone':'','distinct_person':'1'})
        link = credits.link_legacy(db,row.id,{'entry_key':command_key('link',row.id),
            'source_hash':credits.legacy_hash(row),'customer_id':str(person.id),'version':str(person.version)},'Transición inicial')
        if link.opening_movement_id:
            opening_ids.append(link.opening_movement_id)
    if fingerprints(source_rows(db))!=plan['source']:
        raise RuntimeError("Un original cambió durante la transición; se revierte todo")
    expected = sum((by_id[identifier].amount for identifier in mapped if not by_id[identifier].paid),Decimal(0))
    actual = sum(db.scalars(select(CreditMovement.delta).where(CreditMovement.id.in_(opening_ids))),Decimal(0))
    if expected!=actual:
        raise RuntimeError("No concilia el saldo trasladado; se revierte todo")
    return summary(rows,plan)


def summary(rows,plan):
    mapped = {item['id'] for item in plan['assignments']}
    debt = lambda include: str(sum((row.amount for row in rows if row.id in include and not row.paid),Decimal(0)))
    return {'original_rows':len(rows),'mapped_rows':len(mapped),'deferred_rows':len(plan['deferred']),
            'deleted_untouched':sum(row.deleted_at is not None for row in rows),
            'mapped_debt':debt(mapped),'deferred_debt':debt({item['id'] for item in plan['deferred']})}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--expected-database',required=True)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--allow-production',action='store_true')
    args=parser.parse_args()
    if args.prepare==args.apply:
        parser.error('Elegir --prepare o --apply')
    if engine.url.database!=args.expected_database:
        raise RuntimeError('La base de destino no coincide con la indicada explícitamente')
    if (ENV=='production' or INTEGRATIONS_MODE!='mock') and not args.allow_production:
        raise RuntimeError('La operación productiva requiere --allow-production explícito')
    with engine.begin() as connection:
        # Los commit de servicios liberan savepoints; el conjunto conserva una sola transacción exterior.
        with Session(bind=connection,join_transaction_mode='create_savepoint',expire_on_commit=False) as db:
            if db.scalar(text('SELECT version_num FROM alembic_version')) not in {'0020_credit_person_names','0021_salary_deletion'}:
                raise RuntimeError('Requiere el esquema 0020 o 0021 verificado')
            if args.prepare:
                rows=source_rows(db);plan=prepare(rows)
                descriptor=os.open(args.plan,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(descriptor,'w',encoding='utf-8') as output:
                    json.dump(plan,output,ensure_ascii=False,indent=2)
                result=summary(rows,plan)
            else:
                result=apply(db,json.loads(args.plan.read_text(encoding='utf-8')))
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':
    main()
