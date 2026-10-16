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
| Excel | Vista previa, ambigüedades, blanco/cero, fórmula sin ejecución, XML protegido, orígenes, repetición concurrente, nueva versión en conflicto y proveedor explícito. |
| Métricas | Conciliación con detalle/importación, históricos separados, anulados, período vacío/cero, año bisiesto, diciembre/enero, timestamps y desgloses paginados. |
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

`scripts/verify_excel.py` contrasta un original privado montado read-only en DB
efímera, sin imprimir importes ni incorporarlos a fixtures. Se probó el adjunto real:
9 meses conciliados, 493 registros y 30 filas ambiguas conservadas; repetición sin
duplicados. Esa verificación NO forma parte de CI porque el archivo es privado.

## Navegador y PDF
La verificación visual usa el navegador de la aplicación, con datos ficticios:
login, selección móvil, TODO desde otra página, emisión/descarga, configuración,
gestión/proveedor, carga/revisión del Excel y filtros del dashboard. Se inspecciona
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
búsqueda literal de proveedores, borrado restringido, normalización/INSERT repetido,
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
