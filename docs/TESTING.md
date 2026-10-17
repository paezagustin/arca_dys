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
