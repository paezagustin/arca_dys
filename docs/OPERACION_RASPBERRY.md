# Despliegue manual en Raspberry Pi

Procedimiento para ejecutar posteriormente en la Raspberry, en una terminal Bash.
No se ejecuta desde Windows, CI ni por un push. Reutiliza el SSD montado en /mnt,
el directorio /mnt/datos/docker/arca_dys y PostgreSQL existente.

**Decisión confirmada:** conservar el control de facturación y limpiar el resto
de los datos de Gestión. No vaciar toda la base. Se migrará primero el esquema y
después se limpiarán únicamente las tablas conocidas de Gestión; hacerlo antes
no evita conflictos de esquema y puede borrar el estado fiscal que queremos conservar.

| Se elimina al ejecutar la limpieza | Se conserva |
| --- | --- |
| Ventas y egresos de Gestión, proveedores, lotes/filas/asignaciones de importación, Sueldos y Fiados. | Cobros MP y registered_arca, facturas/CAE/respuestas, vínculos pago-factura, solicitudes/reservas fiscales, notificaciones/historial MP, emisor, usuarios, sesiones, auditoría monetaria, logs y versión Alembic. |

No se cambian CUIT, punto de venta, certificado, clave, aplicación MP, cuenta ni
dominio NGROK. La limpieza es un comando **puntual**, nunca un paso de cada actualización.

## 1. Identificar la instalación y preparar archivos

Entrar por SSH y ubicarse en el repositorio de código que usa la instalación
actual. Su ruta no se deduce de la carpeta de volúmenes; reemplazar este ejemplo:

```sh
cd /ruta/al/repositorio/arca_dys
findmnt -T /mnt/datos/docker
mountpoint -q /mnt || { echo 'El SSD no está montado en /mnt'; exit 1; }
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
```

Los ejemplos siguientes usan pg_dys, fastapi_app, arca_user y arca_dys. Ajustar estas
cuatro variables si el inventario actual indica otros nombres:

```sh
PG_CONTAINER=pg_dys
APP_CONTAINER=fastapi_app
PG_USER=arca_user
PG_DB=arca_dys
docker inspect "$PG_CONTAINER" --format 'imagen={{.Config.Image}} proyecto={{index .Config.Labels "com.docker.compose.project"}} servicio={{index .Config.Labels "com.docker.compose.service"}}'
docker inspect "$PG_CONTAINER" --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
docker inspect "$APP_CONTAINER" --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
docker inspect "$PG_CONTAINER" --format '{{range $name,$value := .NetworkSettings.Networks}}{{println $name}}{{end}}'
docker exec "$PG_CONTAINER" psql -X -U "$PG_USER" -d "$PG_DB" -c 'SELECT current_database(), current_user, version(); SHOW lc_collate;'
```

No mostrar docker inspect completo ni variables de entorno: contienen claves.
Comprobar la ruta real del cluster, la imagen/distribución PostgreSQL, red y nombres
de servicio. La referencia es PostgreSQL 17.8 Debian; no cambiar a Alpine ni subir
de versión mayor sobre ese directorio. No iniciar otro servidor sobre el mismo SSD.

Usar el mismo proyecto Compose que administra la DB, para compartir su red:

```sh
DEPLOY_PROJECT="$(docker inspect "$PG_CONTAINER" --format '{{index .Config.Labels "com.docker.compose.project"}}')"
test -n "$DEPLOY_PROJECT" || { echo 'Identificar primero el proyecto Compose/Portainer'; exit 1; }
```

Esta guía presupone que sus servicios son postgres/fastapi y usan la red default
de ese proyecto. Si la red es externa, los servicios tienen otros nombres o es un
stack Swarm de Portainer, adaptar el manifiesto a ese inventario antes de continuar.
No crear otro stack para esquivar un conflicto de nombres. Administrar el despliegue
desde un único lugar (Compose o el stack existente de Portainer).

Registrar de forma privada la URL HTTPS actual de NGROK, el destino interno del
agente y las URL completas de notificación MP, incluidos paths/query. Conservar
la configuración del agente/Traffic Policy si tiene una. Mantener el mismo token
MP, collector y secreto de firma; no crear otra aplicación para desplegar.

Copiar por Samba/SCP los tres JSON de normalizados/ al directorio
`/mnt/datos/docker/arca_dys/importacion_json/` y comprobar hashes según
[IMPORTACION_JSON.md](IMPORTACION_JSON.md). Git no trae esos archivos.

## 2. Respaldar y detener la aplicación anterior

Si la versión actual tiene Historial de solicitudes, revisar antes las pendientes
y Por verificar. Una solicitud confirmada puede retomarse al arrancar; no borrar
su evidencia ni crear otra factura para resolverla. Elegir una ventana sin cobros
si es posible; las reentregas MP dependen del producto y no reemplazan conciliación.

Crear una carpeta privada de mantenimiento y conservar código/configuración/imagen:

```sh
umask 077
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
MAINT_DIR="/mnt/datos/docker/arca_dys/backups/deploy_$STAMP"
mkdir -p "$MAINT_DIR"
git rev-parse HEAD > "$MAINT_DIR/commit.before"
for file in .env .env.prod docker-compose.yml docker-compose.yaml docker-compose.prod.yml; do
  if [ -f "$file" ]; then cp -p "$file" "$MAINT_DIR/$(basename "$file").before"; fi
done
OLD_IMAGE="$(docker inspect "$APP_CONTAINER" --format '{{.Image}}')"
docker image tag "$OLD_IMAGE" "arca-dys-before:$STAMP"
```

Guardar además una copia privada de los dos archivos de certificado/clave y de
la configuración NGROK desde sus rutas reales identificadas. No copiar una carpeta
de certificados vacía ni sustituirlos por los de desarrollo. El dump no los incluye.

Detener SOLO el contenedor web/worker anterior (si usa otro worker externo,
detenerlo también). PostgreSQL, Adminer y Kuma quedan funcionando. No usar down:

```sh
docker stop "$APP_CONTAINER"
BACKUP_FILE="$MAINT_DIR/arca_dys.before.dump"
docker exec "$PG_CONTAINER" pg_dump -U "$PG_USER" -d "$PG_DB" --format=custom --no-owner --no-acl -f /tmp/arca_dys_predeploy.dump
docker exec "$PG_CONTAINER" pg_restore --list /tmp/arca_dys_predeploy.dump > /dev/null
docker cp "$PG_CONTAINER":/tmp/arca_dys_predeploy.dump "$BACKUP_FILE"
chmod 600 "$BACKUP_FILE"
sha256sum "$BACKUP_FILE" > "$BACKUP_FILE.sha256"
sha256sum -c "$BACKUP_FILE.sha256"
docker exec "$PG_CONTAINER" psql -X -U "$PG_USER" -d "$PG_DB" -c 'SELECT count(*) AS cobros, count(*) FILTER (WHERE registered_arca) AS facturados FROM payments; SELECT count(*) AS facturas FROM invoices; SELECT count(*) AS vinculos FROM payment_invoice;' > "$MAINT_DIR/fiscal.before.txt"
```

Cada comando debe terminar sin error. Si falla backup, no migrar ni limpiar.
El archivo es un dump de DATOS, no la exportación Adminer de solo estructura.

## 3. Actualizar código, configurar y ensayar sobre una copia

```sh
git pull --ff-only origin main
```

Si hay cambios locales/conflictos, conservarlos y resolverlos; no usar reset --hard.
Preparar `.env.prod` desde el ejemplo solo si aún no existe. Si ya existe,
conservarlo y completar únicamente lo necesario con los valores actuales:

```sh
if [ ! -f .env.prod ]; then cp .env.prod.example .env.prod; fi
chmod 600 .env.prod
```

Editar .env.prod: DATABASE_URL/POSTGRES_PASSWORD deben apuntar al PostgreSQL y rol
existentes; POSTGRES_DATA_PATH a su montaje real. Certificado y clave deben quedar
montados en /run/arca con los nombres correctos. Conservar CUIT/token Afip SDK/punto
de venta/token y collector MP/secreto de firma. Para la web real se requieren
ENV=production, INTEGRATIONS_MODE=production y ALLOW_LIVE_OPERATIONS=true.
No se puede poner una web productiva en pausa cambiando solo ese flag a false.
No cambiar una contraseña PostgreSQL mediante una variable sobre el volumen existente.
Ver [el catálogo completo de configuración](TECNOLOGIAS_Y_CONFIGURACION.md).

Definir estas funciones en la misma terminal; dc siempre nombra el proyecto actual
y maintenance solo ejecuta comandos de DB con integraciones bloqueadas:

```sh
dc() { docker compose -p "$DEPLOY_PROJECT" --env-file .env.prod -f docker-compose.prod.yml "$@"; }
maintenance() { dc run --rm --no-deps -e ENV=development -e ENVIRONMENT=development -e INTEGRATIONS_MODE=mock -e ALLOW_LIVE_OPERATIONS=false fastapi "$@"; }
dc config --quiet
dc build fastapi
DEPLOY_IMAGE="${DEPLOY_PROJECT}-fastapi:latest"
docker image inspect "$DEPLOY_IMAGE" --format '{{.Os}}/{{.Architecture}}'
```

La construcción nativa en Raspberry Pi OS de 64 bits debe mostrar linux/arm64.
No se arrancó todavía la nueva web ni se recreó PostgreSQL. Si se adaptó el
manifiesto para poner un image explícito, usar ese nombre como DEPLOY_IMAGE.

Restaurar el respaldo en un PostgreSQL temporal sin red, sin volumen productivo y
sin credenciales de proveedores. Los siguientes nombres son exclusivamente de ensayo;
si ya existen, investigar su origen antes de reutilizarlos:

```sh
docker run -d --name arca-dys-restorecheck --network none \
  --tmpfs /var/lib/postgresql/data:rw,size=1g \
  -e POSTGRES_HOST_AUTH_METHOD=trust postgres:17.8
```

Esperar hasta que el comando siguiente responda accepting connections:

```sh
docker exec arca-dys-restorecheck pg_isready -U postgres
```

```sh
docker cp "$BACKUP_FILE" arca-dys-restorecheck:/tmp/before.dump
docker exec arca-dys-restorecheck createdb -U postgres restore_check
docker exec arca-dys-restorecheck pg_restore -U postgres -d restore_check --exit-on-error --no-owner --no-acl /tmp/before.dump
copycmd() { docker run --rm --network container:arca-dys-restorecheck -e ENV=development -e INTEGRATIONS_MODE=mock -e ALLOW_LIVE_OPERATIONS=false -e DATABASE_URL=postgresql://postgres@127.0.0.1:5432/restore_check "$DEPLOY_IMAGE" "$@"; }
docker exec arca-dys-restorecheck psql -X -U postgres -d restore_check -Atc "SELECT to_regclass('public.alembic_version');"
```

Si la última consulta no muestra alembic_version, adoptar el esquema ORIGINAL
conocido (no aplicarlo a una base ya versionada):

```sh
copycmd python -m app.manage adopt-legacy
```

Si ya tiene alembic_version, omitir adopt-legacy.
**Respaldo con IDs MP repetidos:** seguir primero el ensayo completo de
[MIGRACION_MP_LEGACY.md](MIGRACION_MP_LEGACY.md), con auditoría antes/después,
`copycmd python -m app.manage migrate-legacy-mp` y control de identidades.
El upgrade ordinario sigue bloqueándose en 0004 para esos datos; no usar stamp
manual ni consolidar filas. No pasar a producción hasta aprobar ese ensayo.
Para bases sin duplicados, o una copia que ya terminó el puente y está en head:

```sh
copycmd alembic upgrade head
docker exec arca-dys-restorecheck psql -X -U postgres -d restore_check -c 'SELECT count(*) AS cobros, count(*) FILTER (WHERE registered_arca) AS facturados FROM payments; SELECT count(*) AS facturas FROM invoices; SELECT count(*) AS vinculos FROM payment_invoice;'
docker exec -i arca-dys-restorecheck psql -X --single-transaction -v ON_ERROR_STOP=1 -U postgres -d restore_check -f - < scripts/reset-business-data.sql
docker exec arca-dys-restorecheck psql -X -U postgres -d restore_check -c 'SELECT count(*) AS cobros, count(*) FILTER (WHERE registered_arca) AS facturados FROM payments; SELECT count(*) AS facturas FROM invoices; SELECT count(*) AS vinculos FROM payment_invoice;'
```

Los conteos fiscales deben coincidir con fiscal.before.txt antes y después de la
limpieza de ensayo. Una guarda de migración que detecte datos inesperados se revisa
en esta copia; no saltarla con stamp ni borrar información fiscal. La capacidad
temporal es 1 GB: si no alcanza, ampliar SOLO el tmpfs de ensayo y repetir desde
el respaldo. No probar el servidor web/worker con esta copia de solicitudes reales.

La adopción admite la variante PostgreSQL conocida del respaldo: UNIQUE
invoices_invoice_number_key sobre invoices(invoice_number), equivalente al índice
único explícito del baseline. Comprueba nombre, tabla, única columna y semántica
de unicidad inmediata con NULLs distintos; conserva la restricción y su índice
asociado. No hace falta convertirlos ni editar migraciones históricas.
Otra diferencia, incluso junto con esa equivalencia, sigue deteniendo la adopción.
No usar stamp manual ni eliminar restricciones para evitar el rechazo.

## 4. Migrar la DB real y limpiar únicamente Gestión

Solo tras el ensayo correcto, todavía con web detenida:

```sh
docker exec "$PG_CONTAINER" psql -X -U "$PG_USER" -d "$PG_DB" -Atc "SELECT to_regclass('public.alembic_version');"
```

Solo si no existe alembic_version:

```sh
maintenance python -m app.manage adopt-legacy
```

Si ya está versionada, omitir esa adopción. Para el respaldo con duplicados,
ejecutar en su lugar la sección de producción de
[MIGRACION_MP_LEGACY.md](MIGRACION_MP_LEGACY.md), solo después del ensayo correcto
en restore_check. Incluye maintenance python -m app.manage migrate-legacy-mp y
comparación completa antes/después. Para bases sin duplicados, o tras terminar
el puente, aplicar migraciones ordinarias y comprobar head:

```sh
maintenance alembic upgrade head
maintenance alembic current
```

Head esperado: **0013_mp_identity**. Después ejecutar UNA VEZ la limpieza
solicitada, en transacción y sobre el nombre de base comprobado al principio:

```sh
docker exec -i "$PG_CONTAINER" psql -X --single-transaction -v ON_ERROR_STOP=1 -U "$PG_USER" -d "$PG_DB" -f - < scripts/reset-business-data.sql
docker exec "$PG_CONTAINER" psql -X -U "$PG_USER" -d "$PG_DB" -c 'SELECT count(*) AS cobros, count(*) FILTER (WHERE registered_arca) AS facturados FROM payments; SELECT count(*) AS facturas FROM invoices; SELECT count(*) AS vinculos FROM payment_invoice;' > "$MAINT_DIR/fiscal.after.txt"
diff -u "$MAINT_DIR/fiscal.before.txt" "$MAINT_DIR/fiscal.after.txt"
```

Sin diferencias. El SQL borra exactamente siete tablas de Gestión, exige head y
usa RESTRICT, sin CASCADE: una relación inesperada bloquea la operación en vez de
borrar más datos. Reinicia solo IDs de esas tablas. No borrar directorios PostgreSQL,
no ejecutar DROP DATABASE/SCHEMA y no truncar payments/invoices/billing_requests.

Validar los JSON y después insertarlos. Para el montaje privado usar estas dos
invocaciones completas; no pasan por la función maintenance:

```sh
dc run --rm --no-deps -e ENV=development -e ENVIRONMENT=development -e INTEGRATIONS_MODE=mock -e ALLOW_LIVE_OPERATIONS=false -v /mnt/datos/docker/arca_dys/importacion_json:/import:ro fastapi python -m scripts.import_business_json --directory /import
dc run --rm --no-deps -e ENV=development -e ENVIRONMENT=development -e INTEGRATIONS_MODE=mock -e ALLOW_LIVE_OPERATIONS=false -v /mnt/datos/docker/arca_dys/importacion_json:/import:ro fastapi python -m scripts.import_business_json --directory /import --apply
```

La primera debe devolver dry_run; la segunda applied: 107 proveedores (creados o
reusados), 1349 ventas y 1764 egresos. Guardar la salida de conciliación fuera de Git.
Repetir el mismo importador devuelve already_applied. **No volver a ejecutar el SQL
de limpieza después de importar**: es una acción destructiva puntual, no idempotencia
de negocio. Para correcciones posteriores usar los formularios.

## 5. Administrador, arranque y NGROK

Consultar si ya existe el administrador (sin mostrar contraseñas):

```sh
docker exec "$PG_CONTAINER" psql -X -U "$PG_USER" -d "$PG_DB" -c 'SELECT username,role FROM users;'
```

Si no hay cuenta admin, crear una. El comando pide contraseña dos veces; no lleva
claves por argumentos y no contacta proveedores:

```sh
maintenance python -m app.manage create-user --username administracion --role admin
```

Conservar la cuenta si ya existe. Revisar solicitudes antes de iniciar el worker:

```sh
docker exec "$PG_CONTAINER" psql -X -U "$PG_USER" -d "$PG_DB" -c "SELECT id,state,point,voucher_number FROM billing_requests WHERE state IN ('queued','sending','uncertain','check_queued','retry_queued');"
```

Si hay filas, revisar el estado operativo conservado antes de reanudar: una queued
ya fue confirmada y el worker puede emitir al arrancar; una uncertain debe consultarse
por su número. El despliegue no autoriza otra factura ni borra esas operaciones.
En una migración desde el sistema original, esta tabla será nueva y estará vacía.

Recrear únicamente la web, usando la imagen construida y la DB existente:

```sh
dc up -d --no-deps fastapi
dc ps fastapi
docker exec "$APP_CONTAINER" python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read().decode())"
```

Si el nombre/servicio anterior no coincide con fastapi_app/fastapi y Compose avisa
conflicto de nombre, no eliminar contenedores de infraestructura. Con imagen/config
anterior ya guardadas, adaptar el servicio y recrear únicamente el contenedor web.
No iniciar una segunda copia de la aplicación sobre la misma DB.

**NGROK existente:** conservar su configuración, authtoken, URL y Traffic Policy.
Si ya apunta al nombre fastapi:8000 en la misma red, no se cambia. Un agente del
host puede apuntar a 127.0.0.1:8001. Un contenedor independiente necesita la red
compartida/nombre correcto; su localhost no es la Raspberry. No arrancar el perfil
public si otro agente ya administra la misma URL.

**Solo si se decide administrar ese mismo agente desde este Compose:** detener
el anterior, guardar su manifiesto y configurar NGROK_URL con su URL HTTPS exacta
en .env.prod. El override evita depender de una URL asignada automáticamente:

```sh
dcpub() { docker compose -p "$DEPLOY_PROJECT" --env-file .env.prod -f docker-compose.prod.yml -f docker-compose.ngrok.yml "$@"; }
dcpub config --quiet
dcpub --profile public up -d --no-deps ngrok
```

No ejecutar esta alternativa si el agente existente se mantiene externo. Las
configuraciones adicionales de su Traffic Policy deben conservarse al adaptar el
servicio; el override solo fija URL/destino, no migra políticas del agente anterior.
Adminer, Kuma y Samba no necesitan reinstalarse ni actualizarse en esta operación.

## 6. Verificar funcionamiento sin emitir ni cobrar

1. Abrir el **mismo dominio HTTPS** y comprobar health, menú y formularios. El puerto
   8001 del host está ligado a loopback; HTTP por IP de LAN no es el acceso preparado.
   Cookies Secure de producción requieren HTTPS; /health por HTTP no prueba login.
2. Entrar con el admin existente/nuevo y revisar Configuración. Si es la primera
   migración, completar razón social, domicilio, condición fiscal real, IIBB, fecha
   de inicio y el MISMO CUIT/punto de venta. No usar datos ficticios. Configuración
   guardada en DB prevalece sobre defaults de entorno.
3. ARCA: conservar certificado/clave, ARCA_ACCESS_TOKEN, CUIT y punto. El código
   consulta el último número autorizado para ese CUIT/punto/tipo 11 antes de emitir;
   no reinicia la numeración al limpiar Gestión. No pulsar Confirmar para probar.
4. MP: en Conexión MP comprobar variables presentes y eventos; eso no certifica
   conexión externa. Comparar la URL de notificación configurada con la ruta válida:
   /mp/webhook requiere firma; productos sin firma usan /mp/webhook/legacy/<token>
   según MERCADO_PAGO.md. Conservar la misma aplicación/cuenta y tópicos. Un dominio
   idéntico no arregla un path o secreto incorrecto. No desactivar validaciones.
5. Si la URL antigua no cumple el contrato nuevo, ajustar manualmente el path de
   notificación en el producto correspondiente conservando dominio y credenciales.
   No inventar cobros de prueba productivos: usar evidencias anonimizadas anteriores
   y observar las operaciones normales posteriores. Un 401/404 exige revisar
   firma/path/red, no volver a facturar. Transferencias dependen de qué notifique MP.
6. En Resumen seleccionar el período importado y comprobar ventas/egresos/ganancia;
   efectivo/MP histórico permanece Sin desglose. Descargar el Excel. Facturas y
   cobros conservados se muestran separados y no duplican esas ventas.
7. Revisar logs con datos privados solo localmente y observar health en el Kuma
   existente. No lanzar seeds, simulaciones ni la suite contra esta DB.

Cuando se cierre el ensayo y no se necesite más su copia temporal:

```sh
docker rm -f arca-dys-restorecheck
```

Solo elimina el contenedor temporal con tmpfs; no hay un volumen productivo montado
allí. Conservar dump/checksum, configuración/imagen anteriores y certificado/clave.

## Recuperación y siguientes actualizaciones

Si un paso falla, no continuar con los siguientes ni limpiar de nuevo. Antes de
migrar puede volver a iniciarse el contenedor anterior si esquema/datos siguen
intactos. Después de migrar, el código viejo puede ser incompatible: restaurar el
dump en una DB aislada, verificarlo y coordinar el cambio con la imagen y manifiesto
anteriores. Nunca restaurar encima de una DB activa. Si hubo operaciones fiscales
después del backup, conciliarlas antes de retroceder; el backup no las deshace en ARCA.

En actualizaciones posteriores no se repite limpieza ni importación inicial:
respaldo, ensayo de migraciones, actualización de código/imagen, migración manual
y recreación solo de fastapi. NGROK/MP/certificados y volúmenes siguen iguales.
No se agrega auto-deploy, CRON ni rotación de claves.

## Evidencia y límites

La suite ensaya migración del esquema original conservando cobros/facturas y la
limpieza restringida con datos ficticios. El perfil backup-test restaura datos
descartables. ARM64 se ensayó bajo emulación en H8; no certifica esta Raspberry,
sus montajes, locales ni rendimiento. No se accedió al dispositivo ni se emitió
o cobró para preparar esta guía. El ensayo del respaldo real se ejecuta manualmente.
H17 incorpora el puente MP con 40 grupos/88 filas sintéticas divergentes y
preservación de 3876/3625/181/3624; no constituye una prueba del respaldo real.

Ver [TECNOLOGIAS_Y_CONFIGURACION.md](TECNOLOGIAS_Y_CONFIGURACION.md),
[DATOS_Y_OPERACION.md](DATOS_Y_OPERACION.md), [MERCADO_PAGO.md](MERCADO_PAGO.md) y
[EXECUTION_STATUS.md](EXECUTION_STATUS.md) para contratos/evidencia.
