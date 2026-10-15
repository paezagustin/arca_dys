#!/bin/sh
set -eu
umask 077
mkdir -p /backups
backup_file="$(mktemp "/backups/arca_dys_$(date -u +%Y%m%dT%H%M%SZ)_XXXXXX")"
pg_dump --format=custom --no-owner --no-acl --file="$backup_file"
pg_restore --list "$backup_file" >/dev/null
completed_file="${backup_file}.dump"
mv "$backup_file" "$completed_file"
sha256sum "$completed_file" > "$completed_file.sha256"
printf 'Backup guardado: %s\n' "$completed_file"
