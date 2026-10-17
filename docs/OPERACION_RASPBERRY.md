# Operación y publicación coordinada

El desarrollo se verifica en Windows/Docker y ARM64 emulado. Ningún push despliega
la Raspberry, modifica sus volúmenes o emite en ARCA. No se accedió al equipo físico.
Esta guía concreta la actualización posterior sin mezclar ensayo y operación real.

## Antes de cambiar la instalación
En el equipo real, identificar el proyecto Compose/Portainer que administra los
contenedores existentes. Registrar versiones y montajes de pg_dys/fastapi_app, ruta
real del SSD, directorio PostgreSQL, arquitectura, locales/collation y certificados.
Usar `docker inspect` con formatos que muestren solo montajes e imagen; no publicar
un inspect completo porque contiene variables privadas. `findmnt /mnt` permite
comprobar que el SSD está montado antes de crear directorios o contenedores.

Conservar PostgreSQL 17.8 y el mismo directorio. El compose de referencia usa Debian
para producción; comprobar la distribución/locale efectiva antes de sustituir una
imagen. No levantar otro PostgreSQL sobre ese directorio, no ejecutar down --volumes
y no usar la exportación de estructura como restauración de datos.

## Respaldo inicial en el SSD
Verificar POSTGRES_DATA_PATH y BACKUP_PATH de .env.prod; el destino predeterminado
es /mnt/datos/docker/arca_dys/backups. El archivo de variables permanece fuera de Git.
Usando el proyecto/instancia existentes ya identificados:

```sh
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile backup run --rm --no-deps backup
```

La base debe estar funcionando; --no-deps evita iniciar/recrear otro servidor para
hacer el respaldo. El script guarda custom dump, verifica catálogo y SHA256. Un
nombre terminado en .dump y el mensaje de verificación confirman el resultado;
conservar también el SHA256. Ensayar pg_restore en un servidor separado, con otra
ruta/volumen y red aislada. La prueba automatizada usa datos ficticios, no sustituye
la restauración del respaldo real. CRON/copia externa/rotación de claves quedan para
el usuario; no se crean en este trabajo.

## Ensayo de esquema sobre una copia
Restaurar el respaldo en una DB de ensayo sin compartir directorio con producción.
Mantenerla sin túnel público ni credenciales de proveedores. Contrastar cantidades,
totales, vínculos y estado antes/después. Si el esquema original no está versionado,
adoptar el baseline con `python -m app.manage adopt-legacy` y luego Alembic head.
Si ya tiene revisión, continuar desde ella; no hacer stamp para saltar discrepancias.

Las guardas de 0002, 0004 y 0007 frenan información inesperada, duplicados externos
y dinero no convertible. No borrar datos para forzarlas. Revisar el caso sobre copia
y preparar una migración adicional si fuera necesario. Nunca editar revisiones
publicadas. La auditoría monetaria permite comparar cada valor original con NUMERIC.

## Ventana de actualización
1. Con respaldo restaurable y ensayo aprobados, detener la web/worker anteriores y
   el túnel. Conservar el servidor PostgreSQL identificado y evitar operaciones en
   Adminer durante la migración. Registrar el commit anterior para recuperación.
2. Descargar el commit validado de main con avance normal y construir la imagen para
   ARM64. Mantener .env.prod/certificados fuera del repositorio y sus montajes reales.
3. Ejecutar solo los comandos de mantenimiento contra esa DB, sin dependencias ni
   servidor web. La configuración exige un permiso explícito incluso al cargar
   modelos productivos; los siguientes comandos no llaman proveedores:

```sh
# Solo si el esquema original todavía NO tiene alembic_version:
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm --no-deps -e ALLOW_LIVE_OPERATIONS=true fastapi python -m app.manage adopt-legacy
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm --no-deps -e ALLOW_LIVE_OPERATIONS=true fastapi alembic upgrade head
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm --no-deps -e ALLOW_LIVE_OPERATIONS=true fastapi python -m app.manage create-user --username administracion --role admin
```

4. Comparar las cantidades/totales/vínculos con el respaldo y consultar la revisión.
   Para la carga histórica puntual de los tres archivos corregidos, seguir
   [IMPORTACION_JSON.md](IMPORTACION_JSON.md) antes de iniciar la web. Copiar los JSON
   privados al SSD por separado de Git; validar primero sin --apply. No vaciar la DB.
   Iniciar la web con configuración productiva explícita; crear primero la cuenta,
   comprobar acceso y configurar datos reales del emisor/punto/límites antes de
   habilitar el túnel. No existe la cuenta local de prueba en producción.
5. Comprobar health, login, listados, configuración y descargas de registros ya
   existentes. No emitir una factura real como prueba de arranque. La web solo
   factura por una confirmación de la usuaria; el inbox MP no lo hace automáticamente.
6. Contrastar ejemplos anonimizados de Point/QR/transferencias con MERCADO_PAGO.md,
   configurar firma/entrada legacy según el producto y comprobar la cuenta receptora
   y el dominio efectivo de NGROK antes de publicar el webhook.

No hay migración automática en el CMD productivo. Si el esquema no está en head,
el inicio falla de forma explícita. No ejecutar dos versiones de la web a la vez
durante adopción/cambio de esquema. No automatizar este procedimiento desde GitHub.

## Recuperación
Si la migración falla, su transacción se revierte; investigar antes de reintentar.
Después de migraciones que agregan evidencia fiscal/gestión no se ofrece un downgrade
destructivo. Restaurar el respaldo probado y el código correspondiente en una
instalación aislada, verificar y coordinar el cambio de instancia. Nunca restaurar
encima de una base activa. Una solicitud fiscal incierta se consulta por su número;
no se repite con otra selección ni se borra para continuar.

## Ensayos reproducibles sin la Raspberry
`docker-compose.arm64-test.yml` ejecuta aplicación y PostgreSQL ARM64 en red interna,
con datos descartables. La imagen production se construye también para ARM64 y
`scripts/smoke_runtime.py` verifica su servidor HTTP y worker en modo simulado.
Las mediciones RSS/health corresponden al entorno emulado, no al equipo físico.
Las evidencias y tamaños exactos se registran en EXECUTION_STATUS.md.

Persisten únicamente como tareas de puesta en producción: montajes/locale efectivos,
restauración del respaldo real, configuración fiscal y contraste de notificaciones
de la cuenta. No hay pruebas con dinero real ni una certificación de ARCA/MP.
