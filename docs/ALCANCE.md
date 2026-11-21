# Alcance acordado

Actualizado: 2026-11-21. Se conserva la simplificación posterior al roadmap H0-H8
y la ampliación H10 de Sueldos. Para Fiados, la opción A solicitada el 20/11
reemplaza el formulario de pagó sí/no por cuentas de personas, primero en desarrollo y con despliegue autorizado explícitamente el 21/11.

| ID | Requisito y aceptación |
| --- | --- |
| F01 | Facturar el total de cada pago MP; conservar registrado sí/no. |
| F02 | FACTURAR TODO aplica al filtro completo, aun con paginación; mostrar cantidad e importe antes de emitir. |
| F03 | FACTURAR SELECCIONADOS admite uno o varios IDs y revalida elegibilidad en servidor. |
| F04 | Factura independiente por importe ingresado; sin crear pagos MP ni ventas diarias. |
| F05 | Factura C tipo 11; condición de venta fija actual; reparto 50/50 conservado con suma exacta al centavo. |
| F06 | QR por comprobante y plantilla coherente con datos fiscales configurados. |
| F07 | Mínimo/máximo centralizados; edición administrativa y validación de rango. Valores iniciales conservados, sin atribuir origen legal. |
| F08 | Solicitudes persistentes y recuperación de resultados fiscales inciertos; no reemitir por error de PDF. |
| M01 | MP idempotente por ID externo; repetir notificaciones no duplica pagos. Importes iguales no implican duplicado. |
| M02 | Actualizar estados y conservar historial de eventos; devolución no emite nota de crédito automáticamente. |
| M03 | Identificar formatos reales de Point, QR y transferencias con ejemplos anonimizados; validar firma cuando corresponda al producto. |
| G01 | Ventas diarias independientes de cobros y facturas, con efectivo y MP editable. Se sugieren los cobros MP locales aprobados de la fecha, incluidos los facturados, y se suman ambos importes en el servidor. Edición simple por lápiz, sin motivos ni historial de cambios. |
| G02 | Solo ventas diarias y egresos En Blanco/En Negro; proveedores buscables. Sin otros ingresos ni medios/categorías adicionales. |
| G03 | Carga inicial puntual por consola de los tres JSON corregidos: proveedores, ventas y egresos, validación, transacción, conciliación e idempotencia. Sin módulo web Importar Excel ni importación de bloques manuales del dashboard. |
| G04 | Reportes separan ventas, cobros MP y emisión fiscal. Desglose efectivo/MP, Sueldos por empleado y Ganancia = Ventas − Total Egresos − Sueldos; filtros día/período y Excel. |
| G07 | Eliminar cargas equivocadas de ventas/egresos mediante baja lógica confirmada, sin perder datos originales ni afectar evidencia fiscal. Gestión con filtros permanentes por proveedor, tipo y fechas arriba de los totales. |
| G05 | Sueldos simples: fecha, Francisco/Juan Cruz, monto y efectivo/mercado pago; reporte mensual por defecto filtrable. Eliminación confirmada al editar mediante baja lógica, conservando el original y excluyéndolo de listados/Resumen/Excel. |
| G06 | Fiados por persona con ID estable, compras y pagos independientes, saldo global y períodos saldados conservados. Opción A: buscador sin tildes en cualquier palabra, lista superpuesta accesible e importes enteros con miles automáticos. Pagos con revisión/confirmación, sin sobrepagos; edición precargada y baja lógica confirmada con evidencia original, sin pagos mayores a la deuda. Celular argentino opcional (área+número, 10 dígitos; 549 solo al preparar el enlace) y mensaje de WhatsApp con fechas/montos/detalle/saldo, revisión y apertura del chat sin envío automático. Registros anteriores intactos: transición ensayada solo para nombres únicos; los repetidos requieren vinculación humana, sin fusionar ni inventar pagos/fechas. Nombres capitalizados por palabra. Ver FIADOS.md. |
| U01 | Logo centrado y nombre Dulce y Salado debajo, menú móvil desplegable con icono sencillo y nombre de sección, sin flecha; Administración y ARCA DYS abajo de la barra lateral con margen; Resumen con importes unidos, colores y separadores; montos nuevos vacíos con placeholder y datos guardados conservados; mensajes de éxito/error flotantes centrados arriba, cierre manual y duración de 2 segundos, y enlaces de descarga. |
| U02 | Paginación SQL de todos los listados, incluido reports-stadistics. Filtros y orden estable. |
| O01 | Desarrollo Windows 11 con Docker Desktop: simulación sin servicios externos, datos de ejemplo y tests repetibles. |
| O02 | Compose separados dev/test/prod; PostgreSQL 17.8 de referencia, sin upgrade mayor en este trabajo. |
| O03 | Alembic y adopción comprobada del esquema existente; backup manual en SSD antes de migrar. |
| O04 | Facturación/Gestión/Resumen/Sueldos/Fiados sin login con sesión local y CSRF. Otras secciones solo admin; webhook con contrato propio. |
| O05 | Despliegue manual con inventario y respaldo restaurado antes de migrar; conservar control fiscal/MP/configuración, SSD y dominio NGROK actuales. H15 es una limpieza inicial puntual limitada a 0013, no una actualización ordinaria. No repetirla en la refactorización 0017: conservar y conciliar Fiados anteriores. El usuario autorizó el despliegue del 21/11/2026 con respaldo y ensayo, preservando todos los Fiados existentes. |
| O06 | PWA en línea con inicio en Facturación. HTTPS privado por DNS local y DNS-01, con restricción de red, sin acceso público a la interfaz. Despliegue manual después del inventario. |
| D01 | Seguimiento vigente en Lific; documentación técnica y guía de uso al día con la versión; commits/push directos con evidencia. |

## Exclusiones
Facturación parcial, importes aplicados y saldos de pagos; métricas de pendientes
de facturar/cobrar en dashboard; cálculo de nómina e importación del Excel de sueldos/adelantos; stock, catálogo/POS, contabilidad
integral, múltiples negocios, cuentas corrientes de proveedores y compras a crédito.
CRON, copia externa de backups y rotación de claves los resolverá el usuario después.

## Datos y definiciones
Una venta diaria conserva importes manuales. MP solo sugiere un importe inicial
editable; no cambia cierres guardados al facturar. Totales históricos sin desglose
se preservan y no se atribuyen a efectivo/MP. Se pueden comparar períodos de
esas fuentes, sin exigir igualdad ni bloquear operaciones por una diferencia.
Conservar En Blanco/En Negro de los JSON; no inferir tratamiento fiscal.
Un día vacío significa sin registrar, no cero. Los originales y copias normalizadas
se guardan en data/private/, fuera de Git, imágenes y fixtures. El script no limpia
la DB: la limpieza local solicitada fue una operación previa con respaldo.

## Pendientes de información que no bloquean el entorno local
- Condición fiscal exacta del emisor (no asumir monotributista ni exento).
- Configuración efectiva de Portainer/Compose, montajes, arquitectura y locale de la Raspberry.
- Ejemplos anonimizados de cada notificación real recibida; particularidades de transferencias.
