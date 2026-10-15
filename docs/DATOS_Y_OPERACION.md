# Datos, backups y operación

## Referencia de esquema
El SQL entregado es una exportación de estructura Adminer de PostgreSQL 17.8, con
cinco tablas y sin INSERT/COPY. El fixture versionado contiene solo esa estructura
y omite el comando de selección de base. Se usa únicamente en bases de prueba.
No es un backup de las ventas/cobros actuales y nunca debe importarse sobre producción:
incluye DROP TABLE propios de una exportación destinada a restauración.

`0001_legacy` reproduce el esquema inicial y conserva TODOS los campos. Los posibles
campos obsoletos se documentan en ARQUITECTURA y se auditan con scripts/audit-legacy.sql.
No eliminar hasta comprobar el contenido real, referencias y forma de preservar histórico.

## Base nueva de desarrollo
Compose dev aplica `alembic upgrade head` antes de iniciar. El arranque web solo
verifica conexión y revisión; no modifica tablas con create_all.

## Adopción de una base existente
Ensayar primero sobre una copia restaurada, con datos anonimizados cuando corresponda.
El comando `python -m app.manage adopt-legacy` compara tablas, tipos, nullability,
índices y relaciones contra el baseline congelado. Si coincide, crea únicamente
alembic_version y marca 0001_legacy; no ejecuta el CREATE inicial sobre tablas existentes.
Si hay diferencias o ya existe versionado, se detiene. No usar stamp manual para
silenciar una diferencia. Las futuras migraciones deben ser incrementales.

## Backup manual solicitado en el SSD
Se prepara el respaldo lógico en /mnt/datos/docker/arca_dys/backups por defecto.
No existe acceso a la Raspberry desde esta sesión: el script preparado no implica
que el respaldo productivo ya se haya realizado.

En la Raspberry, usando la configuración que identifica su PostgreSQL existente:

```sh
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile backup run --rm backup
```

Se usa pg_dump custom con snapshot consistente, permisos restrictivos, verificación
de catálogo con pg_restore --list y SHA256. Solo se anuncia completado después de
esas comprobaciones; un archivo sin extensión .dump indica una operación no terminada. El perfil de test
verifica además la restauración real y el contenido de un registro ficticio.
No se agregó CRON, política de borrado ni copia a otro dispositivo.

## Antes de usar el nuevo Compose en producción
Este primer hito habilita desarrollo; H2-H5 tienen correcciones fiscales/de acceso
pendientes. No actualizar la Raspberry por el solo hecho de recibir un commit.
No ejecutar este compose contra producción para probarlo.

1. Identificar compose/proyecto de Portainer efectivos, nombres, mountpoints,
   rutas de certificados, versión/arquitectura y locale existentes.
2. Preparar .env.prod desde .env.prod.example, fuera de Git. Nunca usarlo en Windows/test.
   Su permiso de operaciones reales está desactivado de origen.
3. Confirmar que postgres es la instancia existente. No levantar dos servidores
   PostgreSQL sobre el mismo directorio. Se conservan nombres conocidos para evitar
   crear silenciosamente otra instancia sobre /mnt.
4. Respaldar, restaurar en copia y ensayar adopt-legacy + futuras migraciones.
5. En publicación coordinada, detener web anterior, aplicar la adopción/migraciones
   comprobadas y levantar la nueva web. No usar down --volumes ni recrear la base.
6. Revisar integridad/estado sin emitir una factura real como prueba automática.

Se conserva PostgreSQL major 17. Prod usa imagen Debian, evitando cambiar a Alpine
sobre un volumen existente con locale glibc. Los entornos descartables usan Alpine.
Comprobar locales/collations reales antes de cambiar la imagen, aun dentro del major.
NGROK, Adminer y Uptime Kuma son perfiles opcionales del compose productivo;
Adminer/Kuma se publican por loopback y requieren el acceso de mantenimiento previsto.
El túnel puede exponer todas las rutas de la aplicación: el control de acceso de H4
debe quedar resuelto antes de habilitarlo con esta refactorización.

## Configuración de producción
`docker compose --env-file .env.prod -f docker-compose.prod.yml config --quiet`
valida el archivo sin imprimir valores sensibles. ENV=production, modo production
y ALLOW_LIVE_OPERATIONS=true son necesarios para operar realmente. El nombre de
la base productiva no es arca_dys_test ni arca_dys_dev.
El usuario realizará la rotación de claves después; este trabajo no la ejecuta.
