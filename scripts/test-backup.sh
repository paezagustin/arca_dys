#!/bin/sh
set -eu
[ "$PGDATABASE" = "arca_dys_test" ] && [ "$PGHOST" = "postgres" ] || exit 2
source_db="backup_source_test_$(date -u +%Y%m%d%H%M%S)_$$"
restore_db="restore_test_$(date -u +%Y%m%d%H%M%S)_$$"
sentinel="SIM-BACKUP-$$"
cleanup() {
  PGDATABASE=postgres dropdb --if-exists "$restore_db"
  PGDATABASE=postgres dropdb --if-exists "$source_db"
}
trap cleanup EXIT
source_revision="$(psql -At -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version')"
case "$source_revision" in ''|*[!a-z0-9_]*) exit 2 ;; esac
createdb "$source_db"
pg_dump --schema-only --no-owner --no-acl | psql -d "$source_db" -v ON_ERROR_STOP=1 >/dev/null
export PGDATABASE="$source_db"
psql -v ON_ERROR_STOP=1 <<SQL >/dev/null
INSERT INTO alembic_version(version_num) VALUES ('$source_revision');
INSERT INTO payments(id_payment_mp,status,mont,registered_arca) VALUES ('$sentinel','approved',12345.67,false);
INSERT INTO credit_customers(entry_key,name,search_text,phone,version,last_seq)
  VALUES (md5('$sentinel-person')::uuid::text,'Cliente ficticio de restauración','cliente ficticio de restauracion','1100000000',3,2);
INSERT INTO credit_movements(customer_id,account_seq,entry_key,payload_hash,kind,delta,entry_date,actor)
  SELECT id,1,md5('$sentinel-purchase')::uuid::text,repeat('a',64),'purchase',10000,'2026-11-01','backup-test' FROM credit_customers;
INSERT INTO credit_movements(customer_id,account_seq,entry_key,payload_hash,kind,delta,entry_date,actor)
  SELECT id,2,md5('$sentinel-payment')::uuid::text,repeat('b',64),'payment',-2500,'2026-11-10','backup-test' FROM credit_customers;
INSERT INTO customer_credits(entry_key,customer,amount,observation,entry_date,paid,version)
  VALUES (md5('$sentinel-legacy')::uuid::text,'Nombre anterior ficticio',5000,'Original sin fecha de pago','2020-01-01',true,1);
INSERT INTO credit_legacy_links(legacy_credit_id,entry_key,payload_hash,customer_id,source_hash,actor)
  SELECT old.id,md5('$sentinel-link')::uuid::text,repeat('c',64),person.id,repeat('d',64),'backup-test'
  FROM customer_credits old CROSS JOIN credit_customers person;
UPDATE credit_movements SET observation='Torta ficticia corregida',version=version+1,
  change_key=md5('$sentinel-edit')::uuid::text,change_hash=repeat('e',64),changed_by='backup-test'
  WHERE kind='purchase';
INSERT INTO salary_payments(entry_key,entry_date,employee,amount,medium,version,deleted_at)
  VALUES (md5('$sentinel-salary-deleted')::uuid::text,'2026-11-01','Francisco',1200,'efectivo',2,now()),
         (md5('$sentinel-salary-active')::uuid::text,'2026-11-02','Juan Cruz',500,'mercado pago',1,NULL);
SQL
output="$(sh /scripts/backup-db.sh)"
printf '%s\n' "$output"
dump_file="$(printf '%s\n' "$output" | sed -n 's/^Backup guardado: //p')"
sha256sum -c "$dump_file.sha256"
createdb "$restore_db"
pg_restore --exit-on-error --no-owner --no-acl --dbname="$restore_db" "$dump_file"
restored="$(psql -d "$restore_db" -At -v ON_ERROR_STOP=1 -c "SELECT mont::numeric(12,2) FROM payments WHERE id_payment_mp = '$sentinel'")"
[ "$restored" = "12345.67" ]
revision="$(psql -d "$restore_db" -At -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version')"
[ "$revision" = "$source_revision" ]
credit_balance="$(psql -d "$restore_db" -At -v ON_ERROR_STOP=1 -c 'SELECT sum(delta)::numeric(18,0) FROM credit_movements')"
[ "$credit_balance" = "7500" ]
[ "$(psql -d "$restore_db" -At -v ON_ERROR_STOP=1 -c 'SELECT phone FROM credit_customers')" = "1100000000" ]
[ "$(psql -d "$restore_db" -At -v ON_ERROR_STOP=1 -c 'SELECT count(*) FROM credit_movement_changes')" = "1" ]
[ "$(psql -d "$restore_db" -At -v ON_ERROR_STOP=1 -c 'SELECT count(*) FROM credit_movements')" = "2" ]
[ "$(psql -d "$restore_db" -At -v ON_ERROR_STOP=1 -c 'SELECT count(*) FROM credit_legacy_links WHERE opening_movement_id IS NULL')" = "1" ]
[ "$(psql -d "$restore_db" -At -v ON_ERROR_STOP=1 -c 'SELECT count(*) FROM customer_credits WHERE paid AND paid_date IS NULL AND paid_at IS NULL')" = "1" ]
if psql -d "$restore_db" -v ON_ERROR_STOP=1 -c "UPDATE credit_movements SET observation='SIM-CHANGED'" >/dev/null 2>&1; then
  printf 'Error: faltan protecciones del historial restaurado\n' >&2
  exit 1
fi
if psql -d "$restore_db" -v ON_ERROR_STOP=1 -c "UPDATE customer_credits SET observation='SIM-CHANGED'" >/dev/null 2>&1; then
  printf 'Error: el registro anterior vinculado perdió su protección\n' >&2
  exit 1
fi
if psql -d "$restore_db" -v ON_ERROR_STOP=1 -c 'DELETE FROM credit_movement_changes' >/dev/null 2>&1; then
  printf 'Error: el historial de correcciones restaurado perdió su protección\n' >&2
  exit 1
fi
[ "$(psql -d "$restore_db" -At -v ON_ERROR_STOP=1 -c 'SELECT count(*) FROM salary_payments')" = "2" ]
[ "$(psql -d "$restore_db" -At -v ON_ERROR_STOP=1 -c 'SELECT sum(amount)::numeric(18,0) FROM salary_payments WHERE deleted_at IS NULL')" = "500" ]
[ "$(psql -d "$restore_db" -At -v ON_ERROR_STOP=1 -c 'SELECT count(*) FROM salary_payments WHERE deleted_at IS NOT NULL AND amount=1200 AND version=2')" = "1" ]
printf 'Sueldos restaurados: pago eliminado conservado, saldo vigente 500\n'
printf 'Restauración comprobada: importe 12345.67 y revisión %s\n' "$revision"
printf 'Fiados restaurados: saldo 7500, 2 movimientos, archivo anterior sin fecha inventada e inmutabilidad activa\n'
