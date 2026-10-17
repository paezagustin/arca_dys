# Roadmap y condiciones de salida

## H14 · Carga inicial JSON y menú móvil
- [x] Icono de tres líneas solo en móvil; nombre de sección y ausencia de flecha conservados.
- [x] Respaldo y limpieza completa de datos SOLO en la DB dev local.
- [x] Tres JSON privados analizados/normalizados; originales intactos.
- [x] Script de consola con dry-run, transacción, conciliación e idempotencia.
- [x] Carga local: 107 proveedores, 1349 ventas y 1764 egresos, 57 meses conciliados.
- [x] Retirado el módulo web Importar Excel y sus scripts; exportación conservada.
- [x] Navegador móvil/escritorio, métricas y Excel descargado comprobados.
- [x] Guías actualizadas para Windows y carga manual posterior en Raspberry.
- [ ] Cierre de suite final, backup/restore y publicación/CI.

H14 reemplaza el importador de H7 y la precarga SQL de H9. Las secciones inferiores
conservan la evidencia y las decisiones de cada hito anterior, no el alcance vigente.

## H13 · Nombre de sección en el menú móvil
- [x] Sin flecha; el texto del desplegable sigue la sección activa.
- [x] Navegación móvil y teclado comprobados en navegador real.
- [x] Suite completa, documentación y publicación verificadas.
Completado: 406ab74, CI 38988173690 aprobado; 211 pruebas y navegador móvil/escritorio.

## H12 · Montos vacíos, menú móvil y marca
- [x] Montos manuales sin valores iniciales, placeholder y edición conservada.
- [x] Menú móvil desplegable, logo/nombre centrados y Administración al pie.
- [x] Pruebas aisladas, navegador y documentación.
- [x] Publicación y evidencia final de CI.
Completado: 6a03a2c, CI 38986920971 aprobado; 211 pruebas y navegador en móvil y
escritorio. Sin nuevas dependencias ni cambios de esquema.

## H11 · Acciones centradas y fecha de pago de Fiados
- [x] Controles de acciones centrados sin margen superior en tablas.
- [x] Fecha de pago automática, conservada al editar y vacía si no está pagado.
- [x] Migración sin fechas históricas inventadas, pruebas y navegador.
- [x] Documentación y publicación con evidencia.
Completado: befdcc1, CI 38980673926 aprobado; 207 pruebas, backup/restore y revisión
en navegador. La migración conserva sin fecha los pagos históricos desconocidos.

## H10 · Caja desglosada, Sueldos y Fiados
- [x] Alineación centrada de las tablas.
- [x] Efectivo/MP sugerido editable, suma validada, conservación de históricos.
- [x] Sueldos con ENUM PostgreSQL, reporte mensual, filtros y métricas por empleado.
- [x] Fiados con formulario simple, listado y marcado de pago.
- [x] Resumen/exportación, migración, pruebas, navegador, documentación y push.
Completado: 7c9840e, CI 38978324468 aprobado con 203 casos, backup/restore e imagen
final; evidencia detallada en EXECUTION_STATUS.md. No despliega la Raspberry.

## H9 · Ajustes solicitados el 16/10/2026
- [x] Formularios simples de ventas y egresos, proveedores buscables y sin cambios auditados.
- [x] Acceso local anónimo con CSRF; resto de módulos solo para admin.
- [x] Resumen por tipo de egreso y exportación Excel equivalente a la primera hoja.
- [x] Script privado de proveedores normalizados y equivalencias.
- [x] Diseño según PDF de Figma, ayudas al pulsar y logo sin recorte.
- [x] Migración, pruebas aisladas, navegador, documentación y publicación comprobada.

Trabajar en este orden. Un casillero requiere evidencia ejecutada en EXECUTION_STATUS;
no marcarlo por existir código. Se permiten commits pequeños dentro de cada hito.

## H0 · Alcance y base de trabajo
- [x] Registrar todas las decisiones de ALCANCE y reglas de AGENTS.
- [x] Documentar modelo, campos candidatos y exclusiones.
- [x] Publicar README, guías y estado reanudable.

## H1 · Entorno seguro y versionado inicial (primer entregable)
- [x] Compose dev/test/prod separados y datos locales aislados.
- [x] Simulación de MP y ARCA sin SDKs externos ni claves; pantalla para crear pagos.
- [x] Recorrido pagos -> selección -> factura simulada -> PDF verificable.
- [x] Baseline Alembic desde exportación 17.8; adopción de esquema existente validada.
- [x] Ensayo de adopción con datos ficticios, rechazo de drift y conservación de registros.
- [x] Backup lógico y restauración comprobados en entorno descartable.
- [x] Suite aislada, verificación de navegador y CI; push directo a GitHub.


## H2 · Facturación confiable y separación de casos de uso
- [x] Preparación: limpieza autorizada mediante 0002_cleanup y respuesta completa
  del SDK guardada; pruebas de conservación/rollback y restauración ejecutadas.
- [x] Completar el caso de uso y las garantías fiscales que se describen a continuación.

Requisitos F01-F03/F08. Extraer lógica de las rutas; unificar resultado y errores;
operación local atómica; solicitud persistente antes de emisión; identidad y snapshot
de solicitud; serialización por punto/tipo y exclusión del mismo pago concurrente.
Estados que distingan rechazo, autorización y resultado incierto. Consultar el
comprobante intentado antes de reemitir. PDF recuperable sin nueva factura.
Pruebas: doble envío, concurrencia, respuesta perdida, DB falla después del CAE,
rechazo y PDF fallido. Sin entorno productivo. Conservar facturado sí/no.

## H3 · Integración MP idempotente
- [x] Inbox persistente, worker local, identidad única con auditoría previa,
  historial/orden temporal, firmas y adaptadores de lectura probados con fixtures.

M01-M03. Contratos por origen basados en ejemplos anonimizados; recepción persistente,
validación por producto y respuestas HTTP correctas. Restricción de identidad externa
solo después de auditar duplicados heredados. No borrar por importe repetido.
Actualizar estados y conservar cambios; ignorar eventos viejos de manera definida.
Pruebas de reentrega/concurrencia/fallos/reinicio y refunds sin emisión automática.

## H4 · Configuración y comprobantes
- [x] Sesiones/roles/CSRF, configuración auditable, factura independiente con
  confirmación, snapshot inmutable, PDF local sin Chromium y QR leído desde PDF.

F04-F07/O04. Acceso autenticado y formularios protegidos; emisor configurable y límites
editables con validación; mantener Factura C y condición de venta fija. Factura
independiente por importe, sin vínculo obligatorio con ventas/MP. Conservar 50/50
con reparto al centavo. QR dinámico, snapshot fiscal e histórico inmutable.
Unificar generadores PDF; medir costo de Chromium y elegir la alternativa más simple
que conserve impresión y QR. Validación visual y lectura del QR en pruebas.

## H5 · UI y paginación
- [x] Listados SQL, filtros independientes, confirmación del filtro completo,
  cola fiscal persistente, mensajes y selección verificados en navegador móvil.
U01-U02/F02. Logo en navegación, formularios accesibles/mobile, mensajes claros,
POST/redirect/GET y enlaces de descarga. Filtros, totales del filtro y paginación SQL
estable independiente por listado; TODO mantiene alcance completo del filtro.
Pruebas de selección, navegación y errores desde navegador. Mantener URL heredada
reports-stadistics compatible si se corrige el nombre público.

## H6 · Gestión y proveedores
- [x] Gestión independiente, proveedores, correcciones/anulación recuperable y
  conversión monetaria auditada; suite, navegador y restauración ejecutados.
G01-G02. Ventas diarias manuales independientes; movimientos con categorías y medio,
proveedor opcional/seleccionable y altas simples. Fechas e importes validados,
correcciones trazables. Decimal/NUMERIC; migración del Float heredado con conciliación.
No introducir stock, deuda de proveedores, sueldos ni cuenta corriente.

## H7 · Importación del Excel
- [x] Vista previa/revisión/orígenes, proveedores explícitos, históricos separados,
  idempotencia y conciliación del archivo original en base efímera comprobados.
G03. Ingresos/egresos + dashboard. Preservar originales, lote/hoja/fila, clasificación,
históricos manuales y valores ambiguos. Vista previa, errores revisables, sugerencias
de proveedores sin fusiones silenciosas, lote repetido sin duplicación y totales por
mes coincidentes. No importar sueldos. No convertir blancos/errores a cero.

## H8 · Métricas y operación
- [x] Dashboard conciliado, fuentes separadas, suite x86/ARM64, imágenes de ejecución,
  consumo de ensayo, backup/restore y publicación coordinada documentados.
G04/O03. Ventas, egresos, resultado registrado, proveedores y comparación entre meses.
Separar cobros MP y facturas; sin métricas de saldos pendientes. No afirmar ganancia
neta si faltan costos. Verificar consultas contra detalle/importación.
Ensayar build/funcionamiento en ARM, consumo, backup/restore y migraciones en copia;
documentar publicación coordinada para Raspberry sin dos PostgreSQL sobre un volumen.
No automatizar despliegue, CRON ni rotación de claves.
