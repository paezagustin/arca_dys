# Roadmap y condiciones de salida

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
M01-M03. Contratos por origen basados en ejemplos anonimizados; recepción persistente,
validación por producto y respuestas HTTP correctas. Restricción de identidad externa
solo después de auditar duplicados heredados. No borrar por importe repetido.
Actualizar estados y conservar cambios; ignorar eventos viejos de manera definida.
Pruebas de reentrega/concurrencia/fallos/reinicio y refunds sin emisión automática.

## H4 · Configuración y comprobantes
F04-F07/O04. Acceso autenticado y formularios protegidos; emisor configurable y límites
editables con validación; mantener Factura C y condición de venta fija. Factura
independiente por importe, sin vínculo obligatorio con ventas/MP. Conservar 50/50
con reparto al centavo. QR dinámico, snapshot fiscal e histórico inmutable.
Unificar generadores PDF; medir costo de Chromium y elegir la alternativa más simple
que conserve impresión y QR. Validación visual y lectura del QR en pruebas.

## H5 · UI y paginación
U01-U02/F02. Logo en navegación, formularios accesibles/mobile, mensajes claros,
POST/redirect/GET y enlaces de descarga. Filtros, totales del filtro y paginación SQL
estable independiente por listado; TODO mantiene alcance completo del filtro.
Pruebas de selección, navegación y errores desde navegador. Mantener URL heredada
reports-stadistics compatible si se corrige el nombre público.

## H6 · Gestión y proveedores
G01-G02. Ventas diarias manuales independientes; movimientos con categorías y medio,
proveedor opcional/seleccionable y altas simples. Fechas e importes validados,
correcciones trazables. Decimal/NUMERIC; migración del Float heredado con conciliación.
No introducir stock, deuda de proveedores, sueldos ni cuenta corriente.

## H7 · Importación del Excel
G03. Ingresos/egresos + dashboard. Preservar originales, lote/hoja/fila, clasificación,
históricos manuales y valores ambiguos. Vista previa, errores revisables, sugerencias
de proveedores sin fusiones silenciosas, lote repetido sin duplicación y totales por
mes coincidentes. No importar sueldos. No convertir blancos/errores a cero.

## H8 · Métricas y operación
G04/O03. Ventas, egresos, resultado registrado, proveedores y comparación entre meses.
Separar cobros MP y facturas; sin métricas de saldos pendientes. No afirmar ganancia
neta si faltan costos. Verificar consultas contra detalle/importación.
Ensayar build/funcionamiento en ARM, consumo, backup/restore y migraciones en copia;
documentar publicación coordinada para Raspberry sin dos PostgreSQL sobre un volumen.
No automatizar despliegue, CRON ni rotación de claves.
