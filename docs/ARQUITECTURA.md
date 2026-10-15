# Arquitectura

## Base actual y objetivo
Python 3.11, FastAPI, SQLAlchemy 2, Jinja2 y PostgreSQL 17. Un monolito modular con
adaptadores sustituibles, sin infraestructura de colas ni frontend compilado.
Rutas web -> casos de uso -> repositorios/adaptadores. El caso de uso no retorna HTML.
BillingService implementa los casos de uso fiscales sin HTML; las rutas presentan el resultado.

Módulos: facturación; cobros/integración MP; gestión (ventas y movimientos);
proveedores; reportes; web; configuración. Compartir transacciones de PostgreSQL
cuando una operación local lo requiera. Separar emisión fiscal de generación de PDF.
Si se necesita trabajo persistente fuera de HTTP, usar el mismo proyecto y PostgreSQL
antes de introducir otro servicio de infraestructura.

## Entornos implementados
`development` y `test` solo aceptan `INTEGRATIONS_MODE=mock`. La combinación de modo
productivo y entorno local se rechaza aunque exista una variable de permiso.
Producción requiere ENV=production, modo production y ALLOW_LIVE_OPERATIONS=true.
La configuración no descubre .env automáticamente: Compose inyecta variables;
APP_ENV_FILE solo se usa si se indica explícitamente.
Dev/test no tienen NGROK, tokens ni certificados. API y PostgreSQL en red Docker
`internal: true`. Docker Desktop no publica el puerto de un contenedor conectado
solo a esa red: dev incorpora un proxy de entrada mínimo con el puerto 127.0.0.1:8001.
Solo el proxy (y Adminer opcional) toca la red de entrada; API no tiene ruta de salida.
No es un proxy HTTP genérico: su único destino es fastapi:8000. No se agrega a producción.
TestClient no abre un servidor externo. pytest-socket bloquea sockets Python de red
y las solicitudes HTTP de requests se interceptan. psycopg2 usa libpq en C, por lo
que el aislamiento de Docker y el destino PostgreSQL comprobado siguen siendo necesarios.

Simulación: respuestas de pagos con prefijo SIM; comprobantes SIM y CAE textual de
prueba; PDF mínimo con aviso de falta de validez fiscal. El PDF de simulación verifica
el recorrido, no el diseño ni la validez del comprobante productivo.

## Esquema heredado
La exportación Adminer adjunta informa PostgreSQL 17.8 y cinco tablas; no incluye filas.
Baseline `0001_legacy`: payments, invoices, payment_invoice, error_logs, logs_invoice.
El baseline conserva tipos, columnas, vínculos e índices originales.
Los metadatos de adopción en migrations/baseline.py están congelados e independientes
del ORM futuro. El arranque no usa create_all ni adopta/migra bases productivas.

## Revisión de campos y limpieza autorizada
El usuario confirmó qué estructuras no contienen información útil. 0002_cleanup
las retira del esquema y de los modelos/repositorios/creadores de pagos, comprobando
primero el contenido real bajo bloqueo transaccional. El baseline sigue intacto.

| Campo/tabla | Evidencia en código | Decisión vigente |
| --- | --- | --- |
| payments.bill | Se escribe; un filtro heredado lo usa. El listado principal usa status/registered_arca. | Candidato a simplificación tras revisar valores y retirar dependencias. |
| payments.id_arca | El vínculo real está en payment_invoice. | Retirado en 0002; relaciones conservadas. |
| logs_invoice | El flujo activo usa error_logs. | Retirada en 0002 junto con helper e importaciones. |
| error_logs.resolved/resolved_at/resolved_by/resolution_notes | Sin uso confirmado; resolution_by no existe. | Retirados en 0002; historial de errores conservado. |
| invoices.raw_afip_response | El adaptador pide el resultado completo del SDK. | Conservado y poblado en nuevas facturas; simulación identificada. |
| invoices.error_message | Sin escritura actual relevante. | Evaluar dentro del nuevo modelo de estados. |
| imports de módulos/schemas vacíos | Sin responsabilidad definida. | Limpiar durante extracción de casos de uso. |

La ausencia de filas en el dump no demuestra ausencia de uso de ninguna columna.
`scripts/audit-legacy.sql` devuelve cantidades antes de la limpieza, sin exponer
contenidos de clientes. Las facturas históricas no se rellenan con datos inventados.

## Facturación duradera (H2)
0003_billing agrega solicitudes, reservas exclusivas de pagos y proveedor simulado
persistente. Un bloqueo de sesión PostgreSQL por punto/tipo se conserva entre commits
y llamadas externas; se libera explícitamente antes de devolver la conexión al pool.
Antes del envío se confirman identidad, snapshot, reservas, payload y número intentado.
Una respuesta incierta/sending bloquea nuevas emisiones del mismo punto/tipo.
Una transacción confirma factura, JSON fiscal, vínculos, todas las marcas sí/no y
estado autorizado. Si falla después del CAE, conserva el intento y se consulta el
número original. Un reintento explícito consulta primero y reutiliza número/payload;
no se asigna otro número por un timeout. Una consulta fallida jamás habilita reenvío.
No se cambian pagos o importes de solicitudes existentes. Los rechazos inequívocos
se distinguen de errores de red/infraestructura. No se descartan reservas de intentos.
El PDF se genera bajo demanda desde una factura persistida, sin volver al proveedor.
Se retiraron el pipeline fiscal con HTML/commits parciales y el generador PDF remoto.

El adaptador usa WebService de afip.py con extensiones de transporte acotadas:
conexión 5s, lectura 45s, sin retries POST ni redirects. Lee certificados existentes;
no ejecuta automatizaciones de autenticación de cuenta ni necesita su contraseña.
Emisión/consulta retornan respuestas estructuradas antes del chequeo textual del helper.
La consulta exige identidad fiscal e importe coincidentes; solo el código 602 se
interpreta como ausencia. No se certificó homologación ni acceso productivo.

## Garantías posteriores
H3 implementa inbox/worker y actualización idempotente, incluido historial de
devoluciones sin cambios fiscales automáticos. Ver MERCADO_PAGO.md para contratos
y limitaciones del contraste contra la cuenta efectiva.
Los límites centralizados no son una interpretación de la normativa fiscal.
