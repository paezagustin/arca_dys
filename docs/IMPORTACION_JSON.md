# Carga inicial de proveedores, ventas y egresos

Operación puntual por consola, una vez en desarrollo y otra en la Raspberry.
No existe pantalla Importar Excel. El botón Exportar Excel de Resumen se conserva.
El importador solo usa PostgreSQL: no inicia FastAPI, worker, ARCA ni Mercado Pago.

## Archivos privados preparados

En este checkout, los adjuntos originales están en
`data/private/importacion_negocio/originales/`; las copias listas para cargar están
en `data/private/importacion_negocio/normalizados/`. Ambas carpetas quedan fuera
de Git y de las imágenes Docker. Un clone o git pull NO trae esos archivos.
`preparacion.json`, junto a esas carpetas, conserva hashes, conteos y conciliación
mensual de la preparación. Los adjuntos de Downloads no se modificaron.

La carpeta que recibe --directory debe contener estos tres nombres exactos:

| Archivo | Registros | Destino |
| --- | ---: | --- |
| proveedores_normalizados_corregidos.json | 107 | suppliers |
| ingresos_corregidos.json | 1349 | business_entries, kind=sale |
| egresos_corregidos.json | 1764 | business_entries, kind=expense |

- Proveedores: name → nombre, name_key → clave normalizada por minúsculas y espacios.
  Se corrigió una clave con diferencia de acento y sus 18 referencias de egresos.
  No se fusionaron proveedores por parecido. `ya_presente_en_sql` es informativo:
  no es un ID ni una orden para omitir proveedores; se consulta la DB real.
- Ventas: fecha → entry_date; monto → amount. Una venta por fecha. El archivo
  contiene totales, por lo que efectivo/MP se conservan NULL, como Sin desglose.
  No se atribuyen todos los históricos a efectivo ni a Mercado Pago.
- Egresos: fecha, monto, EN_BLANCO → white / EN_NEGRO → black; proveedor_name_key
  se resuelve al ID real del proveedor. Se comprueba también el nombre. Las etiquetas
  originales se conservan en los archivos privados; descripción queda vacía.
- No se crean cobros MP, facturas, sueldos, fiados ni otros ingresos. Las métricas
  y la exportación toman los movimientos cargados de las tablas habituales.

Se preservan centavos con Decimal/NUMERIC(18,2). Se rechazan fechas inválidas,
importes negativos/no finitos/con más de dos decimales, egresos cero, ventas
repetidas por fecha y proveedores sin correspondencia. Venta cero explícita es válida.
Dos egresos con igual fecha/proveedor/importe se conservan como registros distintos.

## Windows 11: validar y cargar

Desde la raíz del proyecto, con Docker Desktop y PostgreSQL dev funcionando y
la imagen actualizada:

```powershell
docker compose -f docker-compose.dev.yml up -d postgres
docker compose -f docker-compose.dev.yml build fastapi
docker compose -f docker-compose.dev.yml run --rm --no-deps fastapi alembic upgrade head
docker compose -f docker-compose.dev.yml stop web fastapi
```

Validar sin escribir (incluye comprobación de la DB y posibles conflictos):

```powershell
docker compose -f docker-compose.dev.yml run --rm --no-deps fastapi python -m scripts.import_business_json --directory /app/data/private/importacion_negocio/normalizados
```

La salida JSON debe indicar `status: dry_run` y los conteos esperados. Luego cargar:

```powershell
docker compose -f docker-compose.dev.yml run --rm --no-deps fastapi python -m scripts.import_business_json --directory /app/data/private/importacion_negocio/normalizados --apply
docker compose -f docker-compose.dev.yml up -d fastapi web
```

Se espera `status: applied`. Abrir http://localhost:8001/business y /dashboard.
Seleccionar el año/mes o rango de los históricos; el mes actual puede estar vacío.
La cuenta admin de simulación vuelve a crearse al iniciar; no carga pagos ficticios.

El 16/10/2026 se vació exclusivamente la DB dev a petición del usuario, después
de un backup completo `artifacts/dev-before-json-reset.dump` y de verificar su
catálogo. Se conservaron el esquema y Alembic head. El script de importación
NO incluye limpieza de tablas ni opciones de borrar/sobrescribir datos.

## Raspberry: ejecutar una sola vez

Este procedimiento es manual y no se ejecuta al publicar en GitHub. Antes,
identificar el proyecto PostgreSQL efectivo, respaldar en el SSD y ensayar en
una copia, según [OPERACION_RASPBERRY.md](OPERACION_RASPBERRY.md). No crear otra
instancia sobre el volumen existente ni vaciar la base productiva.

1. Actualizar el código e imagen en la ventana de mantenimiento acordada, con
   web/worker/túnel detenidos y DB existente funcionando. Aplicar las migraciones
   de la guía de operación; el importador exige head. Si hay Gestión anterior,
   ejecutar UNA VEZ su limpieza restringida según OPERACION_RASPBERRY.md, después
   del backup/ensayo/migración. No borrar datos fiscales ni limpiar tras importar.
2. Copiar los tres JSON de `normalizados/` desde Windows al SSD por Samba/SCP,
   por ejemplo a `/mnt/datos/docker/arca_dys/importacion_json`. Mantenerlos privados;
   no dependen de Git. Verificar los SHA256 contra `preparacion.json`.
3. Desde la raíz del proyecto en la Raspberry, comprobar backup y validar:

```sh
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile backup run --rm --no-deps backup
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm --no-deps \
  -e ENV=development -e ENVIRONMENT=development -e INTEGRATIONS_MODE=mock -e ALLOW_LIVE_OPERATIONS=false \
  -v /mnt/datos/docker/arca_dys/importacion_json:/import:ro \
  fastapi python -m scripts.import_business_json --directory /import
```

El comando conserva DATABASE_URL de .env.prod como destino; verificar que apunta
a la DB existente. Las variables de esta ejecución bloquean integraciones reales
y no modifican .env.prod ni la configuración posterior de la web. No ejecuta el
servidor ni abre las credenciales de ARCA. Ajustar únicamente la ruta privada del SSD
si se eligió otra. --no-deps impide iniciar/recrear servidores auxiliares.

4. Si devuelve `dry_run`, cargar con el mismo comando y --apply:

```sh
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm --no-deps \
  -e ENV=development -e ENVIRONMENT=development -e INTEGRATIONS_MODE=mock -e ALLOW_LIVE_OPERATIONS=false \
  -v /mnt/datos/docker/arca_dys/importacion_json:/import:ro \
  fastapi python -m scripts.import_business_json --directory /import --apply
```

5. Guardar la salida privada de conciliación y verificar conteos/meses en Resumen.
   Reanudar la instalación según la guía de operación. No emitir una factura real
   para probar esta importación. Conservar originales, copias y respaldo.

## Repetición, conflictos y recuperación

- Sin --apply: solo lee/valida; no crea proveedores, registros ni recibos.
- Con --apply: bloqueo PostgreSQL, inserciones, conciliación mensual y recibo se
  confirman en una única transacción. Un fallo revierte todo. No hay cargas parciales.
- El mismo conjunto devuelve `already_applied`, incluso después de editar datos
  desde la web; no los restaura ni sobrescribe. Dos ejecuciones simultáneas se
  serializan. Se puede repetir tras perder la salida de consola.
- Otra versión tras la primera carga se rechaza. No editar los archivos para
  intentar cargar de nuevo ni borrar el recibo interno. Las correcciones posteriores
  se realizan desde Gestión/Proveedores.
- Si hay movimientos de Gestión dentro del intervalo de los archivos, se rechaza
  la carga completa para evitar duplicaciones. Incluye movimientos inactivos. Los
  cobros/facturas no causan ese conflicto y nunca se borran. Revisar sobre una copia;
  no borrar el control fiscal para forzar la importación. La limpieza inicial
  restringida de Gestión se ejecuta solo en el procedimiento acordado, no en reintentos.
- Proveedores existentes por clave se reutilizan sin cambiar nombre/contacto/notas
  ni su estado archivado. Dos coincidencias ambiguas bloquean toda la operación.
- El JSON de salida informa estado, nombre de DB, conteos, proveedores creados/reusados
  y totales por mes/tipo. Contiene información del negocio: guardarlo fuera de Git.
  Error de validación/conexión devuelve código 2. Después de corregir el problema,
  repetir la validación. No usar --apply hasta entender un conflicto de datos.
- El recibo está en import_batches; se conserva la estructura existente y los
  metadatos Excel legados por integridad. No quedan funciones ni rutas de importación
  Excel. No se requiere una nueva migración para esta carga.
