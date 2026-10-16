# Estado de ejecución

Actualizado: 2026-10-16, America/Buenos_Aires.

## Estado vigente
H11 implementado y verificado localmente: acciones centradas y fecha automática
de pago de Fiados. Pendiente publicar y confirmar CI; resultados locales abajo.

H10 implementado y verificado localmente: caja por efectivo/MP editable, Sueldos
con Francisco/Juan Cruz, Fiados, tablas centradas y ampliación de Resumen/Excel.
Publicado en main: 7c9840e647e6f3b43a19ba227e22e90fa7662e4b.
CI completo aprobado: https://github.com/paezagustin/arca_dys/actions/runs/38978324468.
Las secciones H8/H9 siguientes conservan sus resultados históricos.

H0-H8 publicados. H9 incorpora las correcciones solicitadas: gestión simple,
acceso local sin login, diseño según PDF de Figma, ayudas mediante diálogo,
exportación de Resumen y generación privada del INSERT de proveedores.
H9 completado y publicado: implementación 20c8acf y ensayo final b849534.
CI completo aprobado: https://github.com/paezagustin/arca_dys/actions/runs/38942781766.
La puesta en producción está separada y no fue ejecutada en la Raspberry.

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
