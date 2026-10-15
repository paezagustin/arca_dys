# Registro de gestión

`BusinessEntry` guarda ventas, otros ingresos y egresos. Cada importe usa NUMERIC(18,2).
Una venta vigente por fecha se garantiza mediante índice parcial PostgreSQL; cero
significa una venta registrada sin actividad y un blanco no crea registros. Los
otros ingresos no son ventas adicionales. No hay dependencia de servicios fiscales
ni MP: esos subsistemas jamás generan automáticamente registros de gestión.

Cada formulario nuevo tiene UUID único. Repetir el mismo contenido devuelve el
registro existente; un UUID reutilizado con datos distintos se rechaza. La unicidad
protege también solicitudes concurrentes. Las correcciones bloquean la fila y exigen
versión vigente y motivo; auditoría anterior/posterior y actor se guardan en la misma
transacción. Anular/recuperar no elimina información. La recuperación de una venta
no puede desplazar otra venta vigente para esa fecha.

Proveedores: nombre, contacto, notas y estado. Su clave compara espacios y mayúsculas;
no se fusionan nombres parecidos. Solo se vinculan a egresos. Archivar impide elegirlo
en pagos nuevos, conserva los anteriores y permite recuperarlo. Categoría y descripción
son simples textos, sin catálogo contable, deuda ni stock.

## Conversión de importes heredados
0007_business bloquea payments/invoices. Rechaza NaN, infinito, desbordes y valores
con decimales inesperados; tolera solo ruido binario de hasta 0.000001 peso. Conserva
por fila el texto original y el decimal convertido en money_migration_audit. Convierte
mont/total_amount, compara todas las filas con la auditoría y confirma en una sola
transacción. NULL se conserva como NULL. No modifica raw_json, respuestas fiscales,
identidades ni vínculos. Un fallo deja el esquema en la revisión anterior.

No hay downgrade destructivo de gestión/NUMERIC. Para volver a una versión anterior
restaurar el respaldo comprobado y el código correspondiente en una instalación
aislada. Antes de producción seguir DATOS_Y_OPERACION.md.
