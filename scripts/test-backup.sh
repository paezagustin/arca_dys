#!/bin/sh
set -eu
[ "$PGDATABASE" = "arca_dys_test" ] && [ "$PGHOST" = "postgres" ] || exit 2
restore_db="restore_test_$(date -u +%Y%m%d%H%M%S)_$$"
sentinel="SIM-BACKUP-$$"
cleanup() {
  psql -v ON_ERROR_STOP=1 -c "DELETE FROM payments WHERE id_payment_mp = '$sentinel'" >/dev/null
  dropdb --if-exists "$restore_db"
}
trap cleanup EXIT
psql -v ON_ERROR_STOP=1 -c "INSERT INTO payments(id_payment_mp,status,mont,registered_arca) VALUES ('$sentinel','approved',12345.67,false)" >/dev/null
output="$(sh /scripts/backup-db.sh)"
printf '%s\n' "$output"
dump_file="$(printf '%s\n' "$output" | sed -n 's/^Backup guardado: //p')"
sha256sum -c "$dump_file.sha256"
createdb "$restore_db"
pg_restore --exit-on-error --no-owner --no-acl --dbname="$restore_db" "$dump_file"
restored="$(psql -d "$restore_db" -At -v ON_ERROR_STOP=1 -c "SELECT mont::numeric(12,2) FROM payments WHERE id_payment_mp = '$sentinel'")"
[ "$restored" = "12345.67" ]
revision="$(psql -d "$restore_db" -At -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version')"
[ "$revision" = "0001_legacy" ]
printf 'Restauración comprobada: importe 12345.67 y baseline %s\n' "$revision"
