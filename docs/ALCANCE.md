# Alcance acordado

Actualizado: 2026-10-16, con simplificación explícita posterior al roadmap H0-H8. Las anotaciones finales del usuario reemplazan la propuesta
intermedia que incluía facturación parcial y sueldos.

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
| G01 | Ventas diarias manuales con total MP+efectivo; independientes de cobros y facturas. Edición simple por lápiz, sin motivos ni historial de cambios. |
| G02 | Solo ventas diarias y egresos En Blanco/En Negro; proveedores buscables. Sin otros ingresos ni medios/categorías adicionales. |
| G03 | Importar ingresos/egresos y datos históricos del dashboard; conservar origen y resolver problemas mediante vista previa. |
| G04 | Reportes separan ventas, cobros MP y emisión fiscal. Mostrar Ganancia = Ventas − Total Egresos como estimación; exportar el período a Excel. |
| U01 | Logo existente, navegación y diseño responsive; mensajes de éxito/error comprensibles y enlaces de descarga. |
| U02 | Paginación SQL de todos los listados, incluido reports-stadistics. Filtros y orden estable. |
| O01 | Desarrollo Windows 11 con Docker Desktop: simulación sin servicios externos, datos de ejemplo y tests repetibles. |
| O02 | Compose separados dev/test/prod; PostgreSQL 17.8 de referencia, sin upgrade mayor en este trabajo. |
| O03 | Alembic y adopción comprobada del esquema existente; backup manual en SSD antes de migrar. |
| O04 | Facturación/Gestión/Resumen sin login con sesión local y CSRF. Otras secciones solo admin; webhook con contrato propio. |
| D01 | Roadmap, estado reanudable, documentación técnica y guía de uso actualizados; commits/push directos con evidencia. |

## Exclusiones
Facturación parcial, importes aplicados y saldos de pagos; métricas de pendientes
de facturar/cobrar en dashboard; sueldos y adelantos; stock, catálogo/POS, contabilidad
integral, múltiples negocios, cuentas corrientes de proveedores y compras a crédito.
CRON, copia externa de backups y rotación de claves los resolverá el usuario después.

## Datos y definiciones
Una venta diaria no se deriva de facturas ni de MP. Se pueden comparar períodos de
esas fuentes, sin exigir igualdad ni bloquear operaciones por una diferencia.
Conservar clasificaciones del Excel; no reinterpretar "en blanco/en negro" sin
documentar el significado original. Un día vacío significa sin registrar, no cero.
El archivo Excel queda fuera del repositorio y no se usa como fixture de datos reales.

## Pendientes de información que no bloquean el entorno local
- Condición fiscal exacta del emisor (no asumir monotributista ni exento).
- Configuración efectiva de Portainer/Compose, montajes, arquitectura y locale de la Raspberry.
- Ejemplos anonimizados de cada notificación real recibida; particularidades de transferencias.
- Decisiones de mapeo para filas ambiguas del Excel y bloques históricos manuales.
