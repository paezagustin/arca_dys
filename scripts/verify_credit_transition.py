"""Huellas privadas de tablas y secuencias legadas, sin imprimir datos personales."""
import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
from sqlalchemy import inspect, text
from app.core.database import engine

NEW_TABLES = {'credit_customers','credit_movements','credit_legacy_links','credit_movement_changes'}
NEW_SEQUENCES = {table+'_id_seq' for table in NEW_TABLES}


def encode(value):
    if isinstance(value,Decimal): return {'decimal':str(value)}
    if isinstance(value,datetime):
        if value.tzinfo: value=value.astimezone(timezone.utc)
        return {'datetime':value.isoformat()}
    if isinstance(value,date): return {'date':value.isoformat()}
    if isinstance(value,bytes): return {'bytes':value.hex()}
    if isinstance(value,dict): return {key:encode(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)): return [encode(item) for item in value]
    return value


def snapshot(target=engine):
    result={'tables':{},'sequences':{}}
    with target.connect() as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        quote=db.dialect.identifier_preparer.quote
        for name in sorted(set(inspect(db).get_table_names())-NEW_TABLES-{'alembic_version'}):
            hashes=[]
            for row in db.execute(text('SELECT * FROM '+quote(name))).mappings():
                value=json.dumps(encode(dict(row)),sort_keys=True,ensure_ascii=False,separators=(',',':'))
                hashes.append(hashlib.sha256(value.encode()).hexdigest())
            digest=hashlib.sha256(''.join(sorted(hashes)).encode()).hexdigest()
            result['tables'][name]={'rows':len(hashes),'sha256':digest}
        for name in db.scalars(text("SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema='public' ORDER BY sequence_name")):
            if name not in NEW_SEQUENCES:
                row=db.execute(text('SELECT last_value,is_called FROM '+quote(name))).one()
                result['sequences'][name]=list(row)
    return result


def verify(before,after):
    differences=[name for name,value in before['tables'].items() if after['tables'].get(name)!=value]
    differences += ['sequence:'+name for name,value in before['sequences'].items() if after['sequences'].get(name)!=value]
    if differences:
        raise RuntimeError('No coincide la evidencia original: '+', '.join(differences))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--record',action='store_true')
    parser.add_argument('--expected-database',required=True)
    args=parser.parse_args()
    if engine.url.database!=args.expected_database:
        raise RuntimeError('Base de destino distinta de la indicada')
    current=snapshot()
    if args.record:
        descriptor=os.open(args.baseline,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'w',encoding='utf-8') as output: json.dump(current,output,sort_keys=True)
    else:
        verify(json.loads(args.baseline.read_text(encoding='utf-8')),current)
    print(json.dumps({'original_tables':len(current['tables']),'original_sequences':len(current['sequences']),'verified':not args.record}))


if __name__=='__main__': main()
