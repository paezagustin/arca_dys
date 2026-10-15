# Datos, backups y operación

## Referencia de esquema
El SQL entregado es una exportación de estructura Adminer de PostgreSQL 17.8, con
cinco tablas y sin INSERT/COPY. El fixture versionado contiene solo esa estructura
y omite el comando de selección de base. Se usa únicamente en bases de prueba.
No es un backup de las ventas/cobros actuales y nunca debe importarse sobre producción:
incluye DROP TABLE propios de una exportación destinada a restauración.

`0001_legacy` reproduce el esquema inicial y permanece congelada. `0002_cleanup`
retira los campos sin uso confirmados por el usuario: error_logs.resolved,
resolved_at, resolved_by, resolution_notes; la tabla logs_invoice y payments.id_arca.
El nombre resolution_by no existe en el esquema exportado.

La migración bloquea brevemente las tres tablas dentro de la misma transacción,
comprueba su contenido y recién entonces modifica el esquema. Acepta null/blancos
y resolved=false; si hay resoluciones, IDs o registros en logs_invoice, se detiene
sin modificar el esquema ni borrar esa información. No vaciarla para forzar el paso:
conservarla y revisar el caso. Ensayar con la web detenida para no bloquear operaciones.
Requiere conexión a PostgreSQL: no se permite generar SQL offline que omita el control.
scripts/audit-legacy.sql es una consulta previa para el esquema original/0001_legacy;
no ejecutarla luego de 0002 porque esas columnas ya no existen.

El downgrade a 0001 repone estructuras vacías, sin reconstruir valores antiguos.
No cambia pagos, facturas ni relaciones. Se probó también volver a subir a head.
Un rollback de aplicación/esquema debe ser coordinado, no con la web funcionando.

## Base nueva de desarrollo
Compose dev aplica `alembic upgrade head` antes de iniciar. El arranque web solo
verifica conexión y revisión; no modifica tablas con create_all.

## Adopción de una base existente
Ensayar primero sobre una copia restaurada, con datos anonimizados cuando corresponda.
El comando `python -m app.manage adopt-legacy` compara tablas, tipos, nullability,
índices y relaciones contra el baseline congelado. Si coincide, crea únicamente
alembic_version y marca 0001_legacy; no ejecuta el CREATE inicial sobre tablas existentes.
Si hay diferencias o ya existe versionado, se detiene. No usar stamp manual para
silenciar una diferencia. Después de adoptar, aplicar `alembic upgrade head` en la
copia de ensayo: ejecuta 0002_cleanup y conserva registros y relaciones. Una base
ya versionada en 0001 se actualiza directamente, sin repetir adopt-legacy.
Todas las siguientes migraciones también deben ser incrementales.

## Respuesta fiscal conservada
invoices.raw_afip_response almacena FECAESolicitarResult completo retornado por
afip.py 1.2.0 con return_response=True: cabecera, detalle, CAE, vencimiento y
observaciones disponibles. No es el sobre HTTP/SOAP ni incluye la solicitud de
autenticación. No imprimirlo íntegro en logs o mensajes de usuario.
Las simulaciones guardan un resultado con simulation=true y CAE textual de prueba.
Las facturas históricas sin respuesta permanecen así; no se consulta al proveedor
ni se inventa una respuesta para completarlas. La respuesta por sí sola no resuelve
timeouts, pérdida de respuesta o fallos de DB posteriores a una autorización: H2
sigue pendiente. Los errores que el SDK lanza antes de retornar tampoco aparecen
automáticamente en este campo de una factura autorizada.

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
