# Estado de ejecución

Actualizado: 2026-10-16, America/Buenos_Aires.

## Estado vigente
H14 implementado: carga puntual por consola de los tres JSON y retiro del módulo
Importar Excel. Icono sencillo solo en el desplegable móvil, nombre activo y sin
flecha. La DB local fue respaldada, vaciada y cargada con los datos corregidos.
Publicado en main: cd59fb0301de2adbf9ae7c740a99d31fd52e2f31.
Suite local y CI completos aprobados (228 pruebas):
https://github.com/paezagustin/arca_dys/actions/runs/38992592914.

La carga y la limpieza NO se ejecutaron en la Raspberry. Los archivos privados
no se publican con el código; copiar normalizados/ por separado al SSD según
IMPORTACION_JSON.md. La exportación Excel sigue disponible en Resumen.

### Estado anterior publicado
H13: flecha retirada del desplegable móvil y nombre derivado del enlace activo.
Publicado en main: 406ab740acb95babb2cdcdc5df8af570963476bd.
Navegador local y suite de 211 pruebas aprobados. CI completo aprobado:
https://github.com/paezagustin/arca_dys/actions/runs/38988173690.

H12 verificado localmente: montos vacíos con placeholder, menú móvil desplegable,
marca Dulce y Salado centrada y acceso de administración al pie. Publicado en main:
6a03a2c40095add356a886872531e983f353d918. Evidencia local: 211 pruebas aprobadas,
sin omitidas. CI completo aprobado:
https://github.com/paezagustin/arca_dys/actions/runs/38986920971.

H11 implementado y verificado localmente: acciones centradas y fecha automática
de pago de Fiados. Publicado en main: befdcc104e3621e5d1324ce2280a9da919fb64f6.
CI completo aprobado: https://github.com/paezagustin/arca_dys/actions/runs/38980673926.

H10 implementado y verificado localmente: caja por efectivo/MP editable, Sueldos
con Francisco/Juan Cruz, Fiados, tablas centradas y ampliación de Resumen/Excel.
Publicado en main: 7c9840e647e6f3b43a19ba227e22e90fa7662e4b.
CI completo aprobado: https://github.com/paezagustin/arca_dys/actions/runs/38978324468.
Las secciones de hitos anteriores conservan sus resultados históricos.

H0-H8 publicados. H9 incorpora las correcciones solicitadas: gestión simple,
acceso local sin login, diseño según PDF de Figma, ayudas mediante diálogo,
exportación de Resumen y generación privada del INSERT de proveedores.
H9 completado y publicado: implementación 20c8acf y ensayo final b849534.
CI completo aprobado: https://github.com/paezagustin/arca_dys/actions/runs/38942781766.
La puesta en producción está separada y no fue ejecutada en la Raspberry.

## Evidencia H14
- Destino comprobado antes de limpiar: arca_dys_dev, servicio postgres, usuario
  arca_dev, volumen arca-dys-dev_pg_dev; sin /mnt ni DB productiva. Web detenida.
  Dump custom previo de 73807 bytes, catálogo pg_restore --list válido:
  artifacts/dev-before-json-reset.dump, SHA256
  7B150FD5232F8EE4F640095D97DB9784E3FCA5763B95DA3AB2E820946A090AEB.
  Se vaciaron 22 tablas conservando Alembic/esquema. No se entrega un reset productivo.
- Tres adjuntos preservados byte por byte (hash contra Downloads), originales y
  normalizados bajo data/private/importacion_negocio/. Una clave de proveedor con
  diferencia de acento y 18 referencias corregidas; no se fusionaron proveedores.
  Preparación privada con hashes y totales mensuales; git check-ignore aprobado.
- Carga local confirmada: 107 proveedores, 1349 ventas y 1764 egresos (743 En Blanco,
  1021 En Negro), 57 meses. Conciliación SQL por mes/tipo y comprobación posterior
  de los 3113 movimientos uno por uno contra los JSON. Repetición already_applied;
  resto de tablas vacío antes de arrancar web. Al iniciar se recrea solo la cuenta
  admin de simulación y las sesiones de navegación; no hay pagos/facturas ficticios.
- Ventas históricas con total, cash_amount/mp_amount NULL. No se inventaron medios,
  sueldos, fiados ni facturas. Proveedores vinculados por claves y IDs reales.
- Script aislado de app.main/worker/gateways, dry-run sin escrituras, transacción y
  bloqueo PostgreSQL, rechazo de otro conjunto/período ocupado y recibo idempotente.
  Conserva proveedores existentes, rechaza ambiguos y revierte todo ante fallo.
- Eliminadas API, plantillas, lectores y scripts de importación Excel. Rutas viejas
  y /dashboard/history devuelven 404. Tablas legadas se conservan por integridad;
  recibo JSON reutiliza import_batches, sin migraciones nuevas ni cambios de dependencias.
- Edge headless/Playwright con perfil temporal: cinco secciones públicas en
  390x844, icono de tres líneas visible con nombre activo, cerrado tras navegar,
  teclado Enter, sin flecha ni desborde. En 1280x850 el icono/summary están ocultos.
  Sin errores JavaScript. Captura privada revisada: artifacts/h14-menu.png.
- Navegador: 107 proveedores paginados, ausencia de enlaces del módulo retirado,
  Resumen septiembre 2026 conciliado con JSON (ventas/tipos/ganancia y Sin desglose).
  Descarga real de Excel, reapertura y sumas exactas de las tres columnas monetarias;
  tres hojas conservadas, efectivo/MP vacíos y Sueldos sin datos inventados.
- Suite final: 228 passed, 1 warning conocido de TestClient, 64.52s; sin omitidas.
  Incluye invocación real de CLI (validar/aplicar/repetir/error) y conservación de
  referencias legadas al eliminar proveedores. Backup/restauración descartable
  aprobados después de la suite con revisión 0012_credit_paid_date e importe
  ficticio 12345.67. CI del commit funcional también aprobó los 228 casos (62.00s),
  backup/restauración, pip check e imagen final con servidor/worker en simulación.
  pip-audit: sin vulnerabilidades conocidas al ejecutar este hito. Ensayo CI:
  RSS máximo hijo 109108 KiB y health promedio 2.6ms; no mide la Raspberry física.
- Imagen Docker comprobada sin data/private ni artifacts y sin lector/API Excel
  retirados. El script JSON sí está incluido. Enlaces locales de las guías válidos;
  git diff --check aprobado. No se publican registros privados ni resultados monetarios.
- Guía IMPORTACION_JSON con Windows/Raspberry, comandos sin/con --apply, archivos
  privados fuera de imágenes/Git, transferencia al SSD, respaldo y recuperación.
  Sin ARCA/MP real, despliegue físico ni repetición ARM64 en este ajuste.

## Evidencia H13
- Suite completa: 211 passed, 1 warning conocido de TestClient, 61.72s; sin omitidas.
- Backup/restauración descartable aprobados: checksum, importe 12345.67 y revisión
  0012_credit_paid_date. El esquema no cambió en este ajuste.
- Eliminados el icono y sus estilos; el rótulo usa el enlace con aria-current,
  sin duplicar reglas de rutas ni modificar permisos o navegación de escritorio.
- Edge headless con Playwright y perfil temporal, viewport 390x844: navegación
  por las cinco secciones públicas, rótulo coincidente, cerrado tras navegar,
  apertura/cierre con Enter y ausencia de flecha/icono. Escritorio 1280x850:
  navegación visible y rótulo móvil oculto. Sin errores JavaScript ni datos alterados.
  Captura privada revisada: artifacts/h13-menu.png. Sin nuevas pruebas unitarias
  que repliquen este ajuste visual; se ejecuta la suite existente exigida por AGENTS.
- Sin cambios de esquema o dependencias, pruebas productivas ni despliegue Raspberry.
- CI del código publicado aprobó suite, backup/restauración, imagen de ejecución
  en simulación y auditoría de dependencias. Documentación y roadmap cerrados.

## Evidencia H12
- Suite completa: 211 passed, 1 warning conocido de TestClient, 61.21s. Incluye
  cierre con sólo efectivo/MP, ceros explícitos y rechazo de ambos componentes
  vacíos. Se conservaron las pruebas fiscales, acceso, migraciones, importación,
  sueldos y fechas de pago. El simulador también rechaza un importe vacío.
- Backup/restore descartable aprobado: checksum, importe 12345.67 y revisión
  0012_credit_paid_date. No hay cambios de esquema en H12.
- Navegador real Edge en modo headless con Playwright local: montos vacíos y
  placeholder, sugerencia cero vacía al cambiar fecha, cálculo de ambos lados,
  total vacío al borrar todo y valores anteriores conservados al editar.
  Móvil 390x844: menú inicialmente cerrado, abrir/cerrar y navegación a Sueldos
  vuelven al estado esperado. Al redimensionar a escritorio queda visible.
  Logo y nombre centrados (diferencia 0px), nombre debajo, Administración fuera
  del encabezado e inmediatamente antes del footer. Sin errores JavaScript;
  clientWidth=scrollWidth=390. No se guardaron ni alteraron registros de negocio.
- Capturas privadas revisadas: h12-mobile.png, h12-menu-abierto.png y
  h12-escritorio.png, dentro de artifacts/. El navegador de pruebas usa un perfil
  temporal separado. No se usó el navegador embebido de entregas anteriores.
- Sin dependencias, servicios o migraciones nuevas. ARM64 no se repitió; no se
  desplegó en Raspberry ni se operó contra ARCA o MP productivos.
- CI 38986920971 del código publicado aprobó suite, backup/restauración, imagen
  de ejecución en simulación y auditoría de dependencias. Roadmap y guías cerrados.

## Evidencia H11
- Suite completa: 207 passed, 1 warning conocido de Starlette/TestClient, 63.00s;
  sin omitidos. Prueba fecha en marcado/formulario, idempotencia incluso al día
  siguiente, edición conservando fecha, vuelta a No y nuevo pago; histórico pagado
  sin fecha conservado y migración desde 0011 sin alterar importes/estado.
- 0012_credit_paid_date agrega paid_date DATE nullable y restricción para impedir
  fecha en fiados no pagados. No modifica las migraciones 0001-0011 publicadas.
- Backup previo de desarrollo: artifacts/dev-before-h11.dump, privado e ignorado.
  Desarrollo migrado sin borrar su volumen. Backup/restore de DB descartable:
  checksum, importe 12345.67 y revisión 0012_credit_paid_date aprobados.
- Navegador anónimo en simulación: crear un fiado ficticio, marcar pagado y ver
  fecha 16/10/2026. Fiados y Sueldos tienen acciones con margen 0; diferencia entre
  centro de botones y celda menor a 0.01px horizontal, 0px vertical. Consola sin
  errores. Capturas privadas h11-acciones.png, h11-fecha-pago.png y h11-sueldos.png.
- Sin dependencias/servicios nuevos, pruebas productivas ni despliegue Raspberry.
  ARM64 no se repitió; sigue disponible la evidencia H8 para ese entorno.
- CI del commit befdcc1: suite completa, backup/restore, imagen de ejecución en
  simulación y auditoría de dependencias aprobados. Documentación y roadmap cerrados.
  En móvil, Sueldos conserva margen 0 y acciones centradas; ancho y scrollWidth
  de 375px en viewport 390x844, sin desborde exterior.

## Evidencia H10
- Suite completa: 203 passed, 1 warning conocido de Starlette/TestClient, 60.94s,
  sin pruebas omitidas. Incluye migración desde 0010 con total conservado y
  efectivo/MP NULL, comparación ORM/Alembic y ENUM nativos; suite fiscal/MP intacta.
  Tras ajustar el error ante un total manipulado, los 58 casos de caja/gestión/
  exportación/métricas afectados volvieron a aprobar (17.73s). CI del código final
  aprobó 203 casos en 54.23s, backup/restore, imagen runtime y auditoría sin
  vulnerabilidades conocidas. No se omitieron pruebas.
- Caja: sugerencia local limitada a aprobados sin facturar de la fecha, límites
  de día, edición manual, suma exclusivamente en servidor, negativos/precisión/
  desborde rechazados y cierre guardado independiente de la facturación posterior.
- Sueldos: acceso anónimo/CSRF, mes actual, empleado/fechas/paginación, valores ENUM,
  doble envío y ediciones obsoletas; Ganancia resta sueldos una sola vez incluso
  con un período sin ventas. Totales por Francisco y Juan Cruz en Resumen.
- Fiados: todos los no pagados sin límite de fecha por defecto; nombre, monto,
  observación, fecha y pagó. Doble envío, marcado repetido, versiones y texto
  escapado comprobados. No crea ventas ni egresos ni altera Ganancia.
- Resumen diario/rango que cruza años y Excel de tres hojas reabierto y conciliado;
  primera hoja conserva seis columnas. Históricos sin desglose no se distribuyen.
- Backup previo de desarrollo: artifacts/dev-before-h10.dump (privado e ignorado).
  Migración local aplicada sin borrar el volumen. Backup/restore descartable aprobó
  checksum, importe 12345.67 y revisión 0011_sales_payroll_credits.
- Imagen final amd64: pip check aprobado; HTTP real en mock con caja, sueldos,
  fiados, Resumen anónimo, login/CSRF, confirmación, worker, factura simulada y PDF.
  DB temporal propia eliminada; RSS máximo hijo 112588 KiB y health promedio 3.0ms
  en este equipo, sin certificar rendimiento físico de Raspberry.
- Navegador anónimo: crear/editar caja 21000.10+10000.20=31000.30; sueldos de ambos
  empleados por 8000.07, filtro por empleado/fechas y Ganancia diaria 23000.23.
  Crear Fiado y marcar pagado, ayuda de Ganancia, navegación de cinco secciones.
  Las tres tablas fiscales tienen cabeceras/celdas centradas; consola sin errores.
  Móvil 390x844: Fiados y Resumen con clientWidth=scrollWidth=375, sin desborde.
  Capturas privadas h10-resumen.png, h10-sueldos.png, h10-fiados.png, h10-movil.png
  y h10-tablas.png en artifacts/. No se descargó por navegador el Excel en H10:
  se verificó su contenido con pruebas automatizadas; H9 conserva su prueba visual.
- Sin nuevas dependencias ni servicios. ARM64 no se repitió para este cambio de
  aplicación; se conserva la evidencia H8, sin afirmar otra prueba ARM aquí.
  No hubo acceso a servicios productivos ni despliegue o backup de la Raspberry.

## Evidencia H9
- Suite completa de 182 casos: 182 passed, 1 warning, 49.69s, sin omitidos.
  El warning conocido de Starlette/TestClient no afecta la ejecución y no se oculta.
  Los módulos afectados aprobaron de nuevo después del último ajuste de ayudas.
- Primer CI de 20c8acf: suite 182 passed en 46.09s y backup/restauración aprobados.
  El ensayo runtime detectó una aserción desactualizada del título anterior; se
  corrigió y amplió para recorrer las tres secciones sin login. Imagen final amd64
  ensayada localmente: acceso anónimo, admin, CSRF, confirmación, worker, factura
  simulada, PDF y Resumen aprobados; pip check aprobado. CI de b849534 completó con
  éxito suite, respaldo/restauración, imagen final y auditoría de dependencias.
- Migración 0010_simple_business probada desde cero/esquema original y desde 0009
  con egresos existentes: importes conservados, tipos inequívocos migrados, egresos
  sin tipo preservados y rechazo atómico si hay otros ingresos. Historiales de cambios
  de gestión/configuración eliminados; solicitudes y snapshots fiscales conservados.
- Backup/restore descartable: checksum y valor 12345.67, revisión 0010_simple_business.
  Antes de actualizar dev se guardó un dump local privado dev-before-h9.dump.
- Original Excel montado read-only: 9 meses, 493 registros, 30 revisiones, conciliación
  exacta y reimportación sin duplicados. Originales/históricos intactos, sueldos excluidos.
  Su hash permaneció intacto; la base privada efímera se eliminó después del ensayo.
- INSERT privado: 53 proveedores normalizados, 292 referencias conservadas en CSV.
  Ejecutado dos veces en DB efímera: 53 proveedores, ningún movimiento. No se cargó
  en producción ni se publicaron nombres, Excel, SQL o equivalencias privadas.
- Navegador local sin login: crear/editar venta con fecha/total, guardar egresos de
  ambos tipos, búsqueda y selección de proveedor, resumen, diálogo de ayuda y descarga.
  Archivo descargado reabierto y conciliado; render de seis columnas revisado, sin
  fórmulas ejecutables ni importes como texto. Encabezado azul y texto oscuro legible.
- Admin muestra ocho secciones en mock; al salir vuelve el menú de tres secciones.
  El historial de solicitudes sigue accesible sin login; otro navegador no puede
  confirmar una vista previa ajena. CSRF y doble confirmación fiscal cubiertos por tests.
- Móvil 390x844: ancho de documento 375px y scrollWidth 375px, sin desborde exterior.
  Logo completo, barra lateral en escritorio y navegación compacta en móvil.
  Capturas privadas: artifacts/h9-resumen.png, h9-movil.png y h9-export.png.
- Sin cambios de dependencias ni infraestructura. ARM no se volvió a ejecutar en
  esta entrega; H8 conserva su evidencia ARM. No se certifican operaciones productivas.

No quedan tareas funcionales pendientes de H9. La adopción productiva es una
operación separada con respaldo y ensayo en copia; no fue ejecutada en esta sesión.
El SQL privado se entrega con su CSV; no está en GitHub. Usarlo sobre suppliers ya
creado por las migraciones. Los nombres dudosos se mantuvieron separados.

## Entregas publicadas
| Hito | Commit de código | Evidencia |
| --- | --- | --- |
| H0/H1 | bc5ef9c2c33d06ff5f1e8bfa7334c0ac90377fa6 | Entorno aislado, baseline/adopción, 50 pruebas, backup/restore y navegador. CI 38810887827 success. |
| Preparación H2 | ddb345b803fff2910605ce796b2fbb4f63f5c750 | Limpieza autorizada 0002 y respuesta fiscal completa. CI 38814927347 success. |
| H2 | d7eb9a8253024cd008b13dd6840faab28494c0f5 | 76 pruebas; concurrencia, pérdida de respuesta/CAE/commit, recuperación y PDF sin reemisión. CI 38817262006 success. |
| H3 | 8bc2a3f8200c68354d95046cd7ff5b0b7ffedd19 | 94 pruebas; inbox, firmas, identidad, estados, reintentos y contratos MP. CI 38818564439 success. |
| H4 | e3228d77c75633ed4de40c4869bdcdb9964f4ff3 | 112 pruebas; acceso/roles/CSRF, ajustes/snapshot, factura independiente y QR leído desde PDF. CI 38820685646 success. |
| H5 | 89dc110c087495520e86c700eb4561526c53454c | 132 pruebas; paginación/filtros/TODO, confirmación estable y cola fuera de HTTP. CI 38823737655 success. |
| H6 | e6dde32fa171c2fab645ec88926d81053c0d7c67 | 150 pruebas; gestión/proveedores, auditoría y Float→NUMERIC conciliado. CI 38824494125 success. |
| H7 | 8d0e384555a1b85771c92874516fac5dfa11a87b | 161 pruebas + ampliación dirigida de 13 casos; Excel trazable y conflicto/XML. CI 38844309749 success. |
| H8 | 4febc14ecc7a397b018e7b36bbf9b72a64922ca6 | Métricas/operación/dependencias. CI 38846641742 success, incluidos suite, backup, imagen runtime y auditoría. |
| H9 | 20c8acf5bea4241ce7af666f6f26a393e34d9e5a + b849534533910812d907b091c21f61556acf8718 | Gestión simple, diseño, acceso local, exportación y SQL privado de proveedores. CI 38942781766 success; 182 pruebas y navegador. |
| H10 | 7c9840e647e6f3b43a19ba227e22e90fa7662e4b | Caja efectivo/MP, Sueldos, Fiados, Resumen/Excel y tablas centradas. CI 38978324468 success; 203 pruebas, backup/restore, imagen final y navegador. |
| H11 | befdcc104e3621e5d1324ce2280a9da919fb64f6 | Acciones centradas y fecha de pago automática de Fiados. CI 38980673926 success; 207 pruebas, restauración, imagen final y navegador. |
| H12 | 6a03a2c40095add356a886872531e983f353d918 | Montos sin ceros iniciales, menú móvil desplegable, marca centrada y Administración al pie. CI 38986920971 success; 211 pruebas, backup/restauración y navegador real. |
| H14 | cd59fb0301de2adbf9ae7c740a99d31fd52e2f31 | Carga JSON privada por consola, 107 proveedores/3113 movimientos conciliados en dev, retiro del módulo Excel e icono móvil. CI 38992592914 success; 228 pruebas, backup/restauración, imagen final y navegador. |

## Evidencia vigente de H8
- Suite x86/Windows: 173 passed, 1 warning, 48.15s; cero pruebas omitidas. Se amplió
  después la protección de precisión fiscal para límites administrativos elevados;
  los 40 casos de métricas/operación/seguridad afectados aprobaron tras ese ajuste,
  y CI aprobó la suite completa de 174 casos del commit H8.
- Auditoría pip-audit 2.10.1: sin vulnerabilidades conocidas en requirements.txt.
  Resolución instalada con pip check aprobado. Sin pymysql/SDK MP innecesarios;
  SQLAlchemy sigue en 2.0 y PostgreSQL sigue en 17.8.
- Backup custom, catálogo, SHA256 y restauración con importe 12345.67/revisión
  0009_reports aprobados tanto en x86 como en ARM64. Ejecutar después de migrar y
  sin otra suite sobre la misma DB; una recreación de tmpfs elimina su esquema.
- Original Excel montado read-only, verificado otra vez con dependencias nuevas:
  9 meses, 493 registros, 30 revisiones; totales mensuales numéricos exactos,
  reimportación idempotente, originales/históricos íntegros, sueldos excluidos y
  hash del archivo intacto. DB privada efímera eliminada, sin datos reales en Git/dev.
- Imagen de ejecución ARM64 construida: 379878247 bytes. Su servidor real en mock
  completó login/CSRF, confirmación, worker, factura independiente, PDF y dashboard.
  RSS máximo hijo 169400 KiB; 10 health promediaron 20.3 ms bajo emulación/QEMU.
- Imagen de ejecución amd64: 343873208 bytes; mismo recorrido aprobado, RSS máximo
  hijo 110708 KiB y health promedio 3.0 ms. Sin reload en ambos ensayos. Son muestras
  locales, no mediciones del hardware Raspberry. No se iniciaron servicios productivos.
- Suite ARM64 completa: 173 passed, 1 warning, 624.66s; cero pruebas omitidas.
  El límite de un proceso de inspección se amplió de 15s a 60s por emulación y se
  volvió a ejecutar la suite entera, con resultado aprobado.
  Después, los 11 casos del módulo de métricas/operación pasaron también en ARM64,
  incluida la nueva protección fiscal de precisión (174 casos distintos cubiertos).
- Navegador: venta/egreso/proveedor, importación ficticia y revisión con motivo,
  históricos separados y filtro mensual/tabla/gráfico. Documento móvil 375px de
  ancho sin desbordamiento exterior en viewport 390x844. Consola sin errores.
  CSS/JS se versionan para renovar la caché al actualizar; colores/estructura verificados.
- PDF simulado revisado: una página, logo, C, Efectivo, 50/50 exacto y SIN VALIDEZ
  FISCAL. No se emitió ninguna factura real ni se consultó el QR en ARCA.

Capturas/resultados ignorados en artifacts/: h2-facturacion.jpg,
h4-factura-independiente.jpg, h5-todo-filtro.jpg, h5-seleccion-movil.jpg,
h6-gestion.jpg, h7-historicos.jpg, h8-grafico.jpg, h8-movil.jpg y
comprobante-simulado.pdf. H3 se verificó por navegador/DB; no se afirma captura de H3.

## Alcance H0-H8 y publicación posterior (ampliado por H9/H10 arriba)
Factura C, Efectivo y reparto 50/50; cobros completos sí/no, factura independiente,
ventas manuales reales separadas, proveedores simples, Excel sin sueldos y métricas
sin saldos pendientes. No se agregaron stock, cuenta corriente, salarios ni SPA.
Los originales SQL/Excel se conservan; solo se retiran las estructuras autorizadas.

Ningún push despliega la Raspberry. No se accedió al dispositivo ni se hizo su backup
real en el SSD; se dejó el comando manual validado. Montajes/locale/configuración
efectivos, ensayo del respaldo real y ejemplos anonimizados de la cuenta MP se
verifican antes de publicar allí, según OPERACION_RASPBERRY.md y MERCADO_PAGO.md.
Los contratos MP actuales están basados en documentación oficial/fixtures, sin
certificar que todos los medios de la cuenta notifiquen igual. No se certificó
homologación ni conectividad productiva ARCA/MP. CRON y rotación de claves quedan
para el usuario. La sesión no ejecuta esas operaciones como parte de las pruebas.
