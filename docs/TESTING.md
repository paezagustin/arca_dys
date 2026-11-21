# Pruebas y evidencia

## Windows 11 y CI
Docker Desktop con contenedores Linux, desde la raíz del repositorio:

```powershell
docker compose -f docker-compose.test.yml run --build --rm test
docker compose -f docker-compose.test.yml --profile backup-test run --rm backup-test
docker compose -f docker-compose.test.yml down --volumes --remove-orphans
```

El último comando elimina SOLO arca-dys-test, con datos ficticios. Nunca usar el
compose productivo o el de desarrollo para limpiar la suite. Si la DB test se
recreó, ejecutar primero la suite/migraciones antes del perfil backup-test.
El perfil x86 fija linux/amd64; ARM tiene archivo/proyecto separado.
Ejecutar suite y perfil de backup en secuencia: comparten la DB descartable y no
deben modificarla al mismo tiempo.

## Cobertura crítica
| Área | Verificación ejecutable |
| --- | --- |
| Aislamiento | Combinaciones de configuración rechazadas, clientes reales bloqueados, URLs test comprobadas y rutas dev ausentes en producción. |
| Esquema | Nueva base, adopción del export original, rechazo de drift, limpieza sin pérdida y rollback ante información inesperada. |
| Dinero | NUMERIC, representación Float original, conciliación por fila; rechazo de precisión inesperada/NaN/infinito/desborde, NULL conservado. |
| Fiscal | Cero/uno/varios IDs, doble envío, solapamiento/concurrencia, reserva exclusiva, respuesta perdida, caída del proceso y fallo/ACK perdido de COMMIT posterior al CAE. |
| Recuperación | Consulta coincidente, ausencia inequívoca, fallo de consulta sin reenvío, mismo número/payload, PDF fallido sin nueva factura y worker durable fuera de HTTP. |
| MP | Reentregas/concurrencia, reinicio/reintentos, firma y cuenta, contratos canónicos por producto, estados viejos/contradictorios y devoluciones sin emisión automática. |
| Acceso | Login real de TestClient, roles, sesión vencida/revocada, CSRF, nonce, acceso anónimo, propiedad de vista previa y versiones de configuración. |
| UI | Paginación SQL independiente, límites/filtros/fechas, TODO de todo el filtro, IDs fuera del filtro, confirmación vencida o con ajustes cambiados y errores HTML escapados. |
| PDF | Factura C, snapshot, 50/50 exacto, CAE y QR decodificado desde PDF rasterizado; simulación identificada. |
| Gestión | Venta diaria única concurrente, UUID, independencia de MP/facturas, correcciones/anulación/recuperación y proveedores archivados. |
| JSON | Validación estricta de tres archivos, proveedores/claves explícitas, cero/fechas/precisión, dry-run sin escritura, transacción, conciliación, reintento concurrente y rechazo de otro conjunto o período ocupado. |
| Métricas/Excel | Conciliación con detalle/JSON, sin desglose inventado, anulados, período vacío/cero, año bisiesto, timestamps; exportación reabierta, seis columnas y hojas Ventas/Sueldos. |
| Operación | Backup custom, SHA256, restauración en DB propia y revisión de esquema; imagen de ejecución con servidor/worker reales en modo simulado. |
| Fiados A | Identidad explícita, tildes/subcadenas, enteros exactos, pagos parciales/saldar, períodos, anulaciones, UUID/versiones y concurrencia real; preservación y vinculación humana de originales legados. |

La suite solo permite ENV=test, INTEGRATIONS_MODE=mock y base arca_dys_test en
postgres antes de TRUNCATE. Trunca exclusivamente tablas del ORM de ese destino.
pytest-socket y requests bloquean red Python; libpq en C usa únicamente PostgreSQL
en la red Docker interna. No se montan claves, certificados ni .env.prod.
El test de rutas productivas importa la app y hace GET de rutas inexistentes sin
iniciar lifespan; no construye clientes externos ni emite documentos.

## ARM64
```powershell
docker compose -f docker-compose.arm64-test.yml run --build --rm test
docker compose -f docker-compose.arm64-test.yml --profile backup-test run --rm backup-test
docker compose -f docker-compose.arm64-test.yml down --volumes --remove-orphans
```

En Windows se ejecuta bajo emulación Docker/QEMU, incluyendo PostgreSQL ARM64.
No equivale a certificar rendimiento, montajes o locale de la Raspberry física.
Ver OPERACION_RASPBERRY.md y EXECUTION_STATUS.md para resultados medidos.

## Imagen de ejecución y archivo privado
`scripts/smoke_runtime.py`, dentro de una imagen de ejecución, exige el entorno test
aislado. Crea su propia DB temporal, migra y arranca Uvicorn sin reload en mock:
login/CSRF, factura independiente, confirmación, worker, PDF y dashboard vía HTTP
loopback. Comprueba una factura y cero pagos; cierra servidor y elimina solo su DB.
Registra RSS máximo del proceso y tiempo de health del entorno de ensayo.
No es un comando para ejecutar contra producción.

Los JSON reales permanecen en data/private/, excluidos de fixtures, Git e imágenes.
La carga local se concilia por mes/tipo contra sus originales; la suite utiliza
únicamente JSON sintéticos. El anterior verify_excel.py se retiró junto con el módulo.

## Navegador y PDF
La verificación visual utiliza un navegador real con perfil temporal:
login, selección móvil, TODO desde otra página, emisión/descarga, configuración,
gestión/proveedor, exportación y filtros del dashboard. Se inspecciona
el resultado visible, consola y persistencia. PDF simulado renderizado y revisado
sin superposiciones. Capturas/resultados locales en artifacts/, fuera de Git.
TestClient y comprobar HTML no se denominan validación visual.

## Dependencias y límites
requirements.in declara dependencias directas y requirements.txt fija la resolución
comprobada. CI ejecuta pip check y pip-audit sobre dependencias públicas, sin datos
de la app ni credenciales. Una auditoría sin hallazgos describe ese momento, no una
garantía futura. La advertencia de deprecación del TestClient HTTPX no afecta el
servidor ni se oculta en pytest; no es una prueba omitida.

No se certifican servicios productivos ni homologación. Los contratos MP necesitan
contraste con ejemplos anonimizados de la cuenta efectiva antes de publicar el
webhook. Homologación futura debe ser un perfil distinto, con certificados/URLs de
prueba. Nunca usar facturas productivas pequeñas, dinero real ni devoluciones reales
para probar código. La puesta en producción se coordina después del backup y ensayo.

## Ajustes H9
tests/test_simple_business.py comprueba uso anónimo y menú, CSRF, aislamiento entre
navegadores, emisión simulada idempotente, edición sin motivo, clasificación,
búsqueda literal de proveedores y borrado restringido,
migración sin pérdida y rechazo de income heredado. La exportación se reabre y
concilia al centavo: fechas, seis columnas, varias compras, cero/blanco, fórmulas
tratadas como texto y precisión de Excel. Navegador separado para diseño, búsqueda,
ayudas, descarga y móvil. Los datos privados no son fixtures ni se publican.

## Ampliación H10
test_closing_registers.py cubre suma en servidor ignorando un total manipulado,
desglose editable, límites de día/aprobados/sin facturar, importe guardado estable,
precisión/negativos/desborde, ENUM nativos y migración sin inventar históricos.
Verifica acceso anónimo/CSRF, mes actual y filtros/paginación de sueldos, empleados,
doble envío/edición obsoleta, Fiados antiguos no pagados/marcado idempotente/texto
escapado, métricas por empleado, Ganancia con sueldos sin doble cómputo y rangos
cruzando años. Reabre el Excel de tres hojas y concilia importes. Las pruebas
anteriores se conservan con el contrato nuevo del cierre de caja.

## Ajustes H11
test_credit_paid_date.py comprueba fecha automática en marcado y formulario,
reintentos incluso al día siguiente, edición conservando fecha, vuelta a No y
nuevo pago, fechas anteriores desconocidas y migración sin pérdida desde 0011.
La alineación de acciones se verifica en navegador con botones reales y tamaño
de sus celdas, tanto en Sueldos como en Fiados.

## Carga JSON y retiro de importación web H14
test_json_import.py usa archivos sintéticos para comprobar validación previa,
dry-run sin escritura, mapeo de clave con acento, proveedores existentes/archivados,
ambigüedad, total histórico con NULL, igualdad legítima de egresos, repetición sin
pisar ediciones y ejecución concurrente. Fuerza una conciliación fallida para
demostrar rollback de proveedores, movimientos y recibo juntos. Comprueba métricas,
exportación conservada y respuestas 404 de las rutas de importación retiradas.
La suite de migraciones contrasta el esquema ORM con head: no se modifican tablas
legadas al retirar las funciones. El icono móvil se comprueba en navegador, con
el nombre activo preservado al navegar y oculto en escritorio.

## Preparación manual de despliegue H15
test_deploy_cleanup.py ejecuta el SQL de mantenimiento en la DB descartable:
elimina únicamente las siete tablas de Gestión y compara todas las demás antes y
después, incluidas secuencias de pagos/facturas, CAE/respuestas, marca facturado,
solicitud incierta/reserva, inbox/historial MP, usuario y emisor. Repetir el SQL en
ese ensayo no altera el control fiscal. Una revisión incorrecta o una FK externa
inesperada bloquean la limpieza completa sin pérdida; no se usa CASCADE.
Esto NO convierte la limpieza en un comando para repetir tras importar datos.

Se comprueban estáticamente los bloques shell de OPERACION_RASPBERRY.md con sh -n,
sin ejecutarlos, y los enlaces locales. docker compose config con valores ficticios
comprueba el override NGROK, URL requerida y montaje de certificado read-only; no
se inicia un agente NGROK ni se contactan proveedores. La restauración/migración del
respaldo real y el despliegue físico quedan como comandos manuales del usuario.

## Equivalencia de adopción legacy H16
test_migrations.py reproduce en PostgreSQL descartable la restricción UNIQUE
invoices_invoice_number_key en invoices(invoice_number). Primero comprueba que
Alembic detecta remove_constraint/add_index contra el baseline congelado; luego
ensaya adopción y upgrade hasta head tanto por API interna como mediante los
comandos python -m app.manage adopt-legacy y alembic upgrade head.

Datos exclusivamente sintéticos reproducen 3876 cobros, 3625 facturados, 181
facturas y 3624 vínculos. Se comparan todas las columnas originales conservadas
fila por fila, incluidas marcas, importes, CAE, respuestas JSON, fechas y vínculos,
y el estado de las secuencias antes/después de adoptar y migrar. El OID de la
restricción y su índice asociado permanecen iguales; los duplicados se rechazan.
La migración monetaria publicada conserva sus auditorías y controles existentes.

Dieciocho variantes negativas comprueban nombres/tablas/columnas incorrectos,
unicidad ausente, restricciones diferibles, NULLS NOT DISTINCT, columnas incluidas
y drift adicional de tablas, columnas, tipos, nullability, índices, restricciones
o FK. Se rechazan sin alembic_version ni alteraciones de registros/secuencias.
No se incluyó ni restauró un backup productivo: los conteos equivalentes no son
evidencia de integridad de los registros reales. Ese ensayo sigue siendo manual
en la copia aislada indicada en OPERACION_RASPBERRY.md.

## Transición MP histórica H17
test_mp_legacy_transition.py agrega 17 casos sintéticos: 40 grupos/88 filas/48
adicionales, 74 miembros facturados y vinculados a 31 facturas sin cruces entre
facturas por identidad; diferencias 0/1/1/5/29 de importes/estados/fechas/marcas/JSON.
Conserva 3876 pagos, 3625 marcas, 181 facturas, 3624 vínculos y 175 errores, además
de secuencias, IDs, CAE y JSON. No se suministró el respaldo real.

Prueba desde 0001, 0002 y 0003 por API y CLI, índice/UNIQUE original de facturas,
solicitudes autorizadas y reservas conservadas, rechazo de solicitudes activas,
drift, precisión monetaria e integridad forzada con rollback de DDL/versionado.
Verifica snapshots y recibos, protección de UPDATE/DELETE/INSERT duplicado,
notificaciones y escrituras concurrentes, JSON anterior y respuestas consultadas,
ausencia de proveedor ante entrega bloqueada y rechazo en preview/issue/cola.
El comando de auditoría se comprueba en una transacción READ ONLY que rechaza UPDATE.
Instalaciones ya en 0004/0012 y bases nuevas mantienen el upgrade Alembic ordinario.

test_mp_inbox.py agrega además un caso de reintento que conserva cada respuesta
canónica con número de intento, fecha y resultado, sin reemplazar la anterior.
Suite local final completa: 269 passed, 1 warning conocido, sin omitidas, 111.96s.
Perfil backup-test: dump custom, checksum y restauración en 0013 aprobados.
Adicionalmente se respaldó/restauró el conjunto sintético completo en otra DB:
huellas/secuencias y esquema iguales; 3876 snapshots, 40 grupos bloqueados,
invalid_groups=0 y dos triggers activos. El SQL READ ONLY de la guía devolvió
88/74/74/31 y diferencias 0/1/1/5/29 en esa restauración sintética.

Navegador real sobre web QA mock y datos sintéticos: aviso de 40 referencias,
filas repetidas con casillas deshabilitadas y marcas intactas, filas normales
habilitadas, advertencia de 87 registros repetidos aprobados en Resumen; sin
desborde horizontal de documento en escritorio ni errores de consola en esa vista.
La red Docker interna se mantuvo; la revisión GET pasó por un visor local de solo
lectura. No se enviaron formularios fiscales ni se probó una emisión productiva.
No se repitió ARM64: no cambiaron dependencias ni se certifica esta Raspberry.

## Fiados A · revisión de desarrollo del 20/11/2026

Suite completa: **364 passed en 139,71 s**, sin omitidas y con una advertencia
conocida de Starlette/httpx. `test_credit_accounts.py` comprueba compras, pagos
parciales/saldar, nuevos períodos, anulaciones, nombres similares, renombres sin
perder identidad, búsqueda sin tildes/subcadenas y filtros/paginación/totales SQL.
Incluye dos conexiones concurrentes, UUID con payload distinto, versiones
obsoletas, rollback antes de commit, respuesta perdida después de commit,
fracciones/rango por SQL sin redondeo y migración sin modificar originales.
Los tests de fechas/bajas anteriores conservan el contrato de la fuente legada,
sin mantener endpoints de pagó sí/no en la nueva interfaz.

Backup-test aprobado en 0017: respaldo custom/checksum/restauración, saldo 7.500,
dos movimientos, vínculo pagado sin fecha inventada y triggers que impiden editar
el diario y la fuente vinculada. Cada ensayo usa sus propias bases efímeras.
`node tests/credit-money.cjs` comprueba agrupación exacta, rechazo de comas y
valores ambiguos y posiciones de cursor. Ambos JS pasan `node --check`.

Imagen local con target production: `scripts.smoke_runtime` aprobado en modo mock,
red interna y DB efímera propia; incluye el nuevo POST de persona+fiado, sesión,
CSRF, Gestión/Sueldos/Resumen, cola y PDF simulados. Sin proveedores externos.

Navegador real a 1366×900 y 390×844: altas/pagos/saldar/nuevo período/anulación,
historial, selección con teclado, búsqueda `perez`, advertencia de homónimos,
filtros y vinculación de dos originales ficticios. La lista se superpone con
desplazamiento medido del importe de 0 px; no hay desborde de documento en las
vistas revisadas. Escritura/pegado `10.000`, cambio a `100.000`, rechazo de coma
y borrado junto al punto comprobados. Capturas locales: `artifacts/fiados-dev/`.
Instancia/guía: [FIADOS.md](FIADOS.md). Pendiente el teléfono físico, aceptación de
la usuaria y ensayo con respaldo real. Sin ARM64, CI ni despliegue en Raspberry.

## Edición, celular y WhatsApp · ARCA-29

380 pruebas completas aprobadas en 149,91 s, una advertencia conocida, sin omitidas.
`test_credit_updates.py` comprueba detalle precargado en cuenta saldada, evidencia
original, cambios de importes, bajas sin pérdida, saldos/listados/mensajes coherentes,
UUID y versiones, CSRF, protección SQL, dos ediciones concurrentes, formatos de
celular y URL/mensaje WhatsApp completos. La prueba de edición de celular incluye
homónimos para no pedir confirmar otra identidad si no se cambió el nombre.

Backup-test 0018 aprobado con una corrección antes/después y comprobación de que
su evidencia no se puede eliminar tras restaurar. Imagen de ejecución y smoke HTTP
mock aprobados. Navegador sobre datos ficticios propios: edición de productos,
ficha/celular, revisión WhatsApp (sin abrir chat), cancelar/confirmar baja, nuevo
listado y breadcrumbs de Fiados/Proveedores/Factura por importe. 1366×900 y
390×844, sin desborde en las vistas revisadas. Capturas locales en artifacts/fiados-dev.
Pendiente WhatsApp y teclado en teléfono físico; no se hizo envío real ni despliegue.

## Celular nacional, reportes y avisos · ARCA-30


Validación final ARCA-30: **390 passed, 152,66 s**, una advertencia conocida y sin
omitidas. Las pruebas de integración cubren teléfono nacional/URL 549 una sola
vez, conversión de datos previos, bloqueo sin pérdida ante formatos ambiguos,
restricción SQL, orden de carga retroactiva, períodos saldados y contenido de
WhatsApp. Las comprobaciones anteriores de conteos/históricos se adaptaron al
nuevo reporte sin retirar sus garantías de saldo y conservación.

Backup-test 0019 aprobado con checksum/restauración, celular nacional conservado,
saldo 7.500, dos movimientos y evidencia inmutable de correcciones. Imagen target
production y smoke HTTP mock/red interna/DB efímera propia aprobados. Sintaxis de
credits.js, notifications.js y reports.js y formato/cursor de dinero con Node
aprobados. git diff --check y enlaces locales de documentación revisados.
Sin cambios de dependencias ni ARM64. Pendiente ARCA-28: teléfono físico y apertura
real de WhatsApp; no se abrió chat ni se envió mensaje durante estas verificaciones.


## Cierre de Fiados · 21/11/2026

396 pruebas completas aprobadas en 156,17 s, sin omitidas. Se agregan normalización
de nombre, migración 0020, transición atómica/repetible con homónimos diferidos y
verificación de huellas que detecta un cambio en observaciones originales.
Backup-test restaura 0020 y conserva correcciones/vínculos. Navegador real validó
cabeceras, referencia en línea, acciones CRUD y columnas en escritorio/móvil.
El ensayo real en Raspberry se limita a migración/conciliación, con todos los datos
privados allí; el smoke usa un PostgreSQL vacío distinto y únicamente mock.


## Baja lógica de Sueldos y CRUD · ARCA-39

402 pruebas completas aprobadas en166,47s, sin omitidas. Se agregan conservación
de todas las columnas, repetición de baja, rechazo de edición/reenvío, permisos
anónimos con CSRF, versiones, filtros/paginación compartidos, conciliación de
Resumen/Excel, concurrencia edición-baja y migración/downgrade protegido.
Backup-test0021 conserva un pago eliminado y total vigente500, junto a las
protecciones existentes de Fiados. No se usan proveedores reales.
Navegador real: cancelación y baja de un sueldo ficticio321, egreso ficticio123,
listado de Gestión sin Eliminar y botones compartidos blancos/azules/rojos.
Las pruebas de navegador solo alteran sus registros ficticios propios.
