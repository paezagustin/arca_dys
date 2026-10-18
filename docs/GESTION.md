# Gestión del negocio

Se usa sin login en la red local. Ventas y egresos son independientes de MP y de
las facturas. No se crean ventas al emitir un comprobante ni al recibir un pago.

## Ventas del día
Fecha (hoy en Buenos Aires, editable), monto en efectivo y monto de Mercado Pago.
MP se sugiere desde los cobros locales aprobados sin facturar de esa fecha y se
puede modificar. No realiza llamadas externas. El servidor suma ambos importes;
el total visible es de solo lectura. Al cambiar la fecha vuelve a sugerir MP.
Una edición ya abierta conserva los importes guardados, sin recalcularlos por
posteriores facturas o cambios de estado del pago.
En altas, efectivo queda vacío con placeholder 0,00; MP también queda vacío si
la sugerencia es cero. Un componente vacío equivale a cero cuando se completó
el otro. Los dos vacíos se rechazan; escribir 0 explícito registra una caja de cero.
La edición conserva los importes guardados, incluidos ceros y totales históricos.
Una venta por fecha; cero es válido, un día sin registrar sigue sin información.
El icono de lápiz abre Editar con fecha y ambos importes. No exige motivo.
Eliminar permite retirar una carga equivocada, por ejemplo un domingo sin ventas.
Después se puede registrar nuevamente esa fecha con un formulario nuevo.

## Egresos
Fecha, importe positivo, tipo En Blanco o En Negro, proveedor opcional y descripción
opcional. La búsqueda consulta hasta 20 coincidencias por nombre; permite escribir,
seleccionar con clic o flechas/Enter y borrar para dejar Sin proveedor.
No hay medios, categorías adicionales, estados de registro ni otros ingresos.

## Filtrar y eliminar cargas equivocadas
Los filtros quedan siempre visibles encima de Ventas y Total Egresos. Se combinan
Mostrar, proveedor y fechas; Buscar actualiza listado y totales de todo el filtro,
incluidas sus otras páginas. El proveedor se aplica a egresos: si se combina con
Mostrar ventas, no habrá coincidencias. Sin proveedor busca solo egresos sin asignar.
Los proveedores archivados siguen disponibles para consultar sus registros anteriores.

En el listado o al editar una venta/egreso, pulsar Eliminar. La confirmación muestra
fecha e importe; Cancelar no cambia nada. Al confirmar se retira de Gestión,
Resumen y Excel. Se conservan internamente la fila, ID, importes, desglose,
proveedor, descripción, origen y referencias de importación mediante active=false.
No se borran pagos MP, facturas, vínculos ni evidencia fiscal. No se ofrece borrado
fiscal ni eliminación de Sueldos/Fiados en esta pantalla.
Si otra ventana editó el registro, la eliminación se rechaza y hay que revisar la
versión actual. Repetir una eliminación no vuelve a modificarlo; reenviar un alta
antigua no lo reactiva. No hay recuperación desde la interfaz: revisar antes de
confirmar y usar una carga nueva para reemplazar un registro equivocado.

## Proveedores
Nombre, contacto y notas. Editar no pide motivo. Se puede archivar para quitarlo del
selector sin afectar egresos anteriores. El botón ? abre la ayuda correspondiente.
Eliminar está disponible para proveedores sin egresos ni asignaciones de importación.
Los proveedores vinculados se editan o archivan para conservar sus referencias.
Los nombres comparan mayúsculas y espacios; dos nombres parecidos no se fusionan solos.

## Garantías internas
UUID de formulario e índice único impiden duplicados. El bloqueo y número de versión
evitan sobrescribir una edición de otra ventana. Los importes siguen en NUMERIC(18,2).
No se guardan historiales de cambios, motivos ni copias anterior/posterior de gestión
o configuración. El historial fiscal de solicitudes permanece intacto.
El indicador interno active conserva excluidas las anulaciones heredadas y las
eliminaciones confirmadas; no se expone como campo editable del formulario.

## Migración 0010_simple_business
Agrega expense_type y copia solo clasificaciones inequívocas del Excel a white/black.
Los egresos heredados sin tipo conservan importe y proveedor, se incluyen en Total
Egresos/Ganancia y se editan para clasificarlos antes de exportar. Nunca se les asigna
un tipo por defecto. Las categorías anteriores significativas pasan a la descripción.
Retira medium, category, classification, business_changes y settings_changes.
Si hay registros income, la migración se detiene sin perderlos: deben reclasificarse
en una copia revisada antes de actualizar. No elimina importes para ajustar el esquema.
Antes de actualizar producción, respaldo y ensayo en copia según DATOS_Y_OPERACION.
No hay downgrade destructivo; para retroceder se restaura el backup y su código.

0007_business conserva la conversión Float → NUMERIC y money_migration_audit para
conciliar importes originales. No se eliminan snapshots fiscales, respuestas ARCA,
identidades MP ni celdas originales del Excel.

## Carga inicial por consola
scripts/import_business_json.py carga los tres JSON corregidos en una transacción.
No hay módulo Importar Excel. Reutiliza proveedores por clave explícita, conserva
sus campos existentes y rechaza coincidencias ambiguas; no fusiona por similitud.
Las ventas históricas conservan total y desglose desconocido. El recibo interno
evita duplicados al repetir el mismo conjunto; los originales privados se conservan.
Comandos y procedimiento: [IMPORTACION_JSON.md](IMPORTACION_JSON.md).

## Sueldos
Acceso local sin login. Fecha (hoy por defecto), empleado Francisco/Juan Cruz,
monto positivo y tipo Efectivo/Mercado Pago (Mercado Pago por defecto). El reporte
debajo empieza en el mes actual; permite filtrar empleado, desde y hasta y pagina
25 filas. El total corresponde a todo el filtro. El lápiz permite editar sin motivo.
Los pagos reducen Ganancia una sola vez; no crean también un egreso en Gestión.
No calcula nóminas ni importa la hoja de sueldos/adelantos del Excel.

## Fiados
Nombre, monto positivo, observación opcional, fecha (hoy) y Pagó (No por defecto).
Se listan primero los no pagados de cualquier fecha para no perder los anteriores.
Se puede buscar por nombre, pago y fechas. Marcar pagado sirve para resolverlo de
un clic y guarda automáticamente la fecha del día en Buenos Aires. La columna
Fecha de pago muestra ese valor. Cambiar Pagó a Sí en el formulario tiene el
mismo efecto. Editar otros datos conserva la fecha; repetir el marcado no la
actualiza. El lápiz permite volver a No si hubo un error y quitar la fecha. No genera un
ingreso ni modifica ventas, caja, MP o Ganancia automáticamente.

## Migración 0011_sales_payroll_credits
Agrega cash_amount/mp_amount NUMERIC nullable y exige pares completos cuya suma
coincida con amount. Conserva los totales anteriores con ambos campos NULL; se
muestran como Sin desglose en Resumen y celdas vacías en Excel. Al editarlos se
completan importes reales; no se inventan proporciones. La carga JSON también
conserva el total sin desglose. Crea salary_payments con ENUM nativos
salary_employee (Francisco, Juan Cruz) y salary_medium (efectivo, mercado pago),
y customer_credits con paid booleano. UUID/versión/bloqueos impiden duplicados y
ediciones perdidas; no hay historial ni motivos. Respaldo antes de migrar y ensayo
en copia; para retroceder se restaura el backup con su código compatible.

## Migración 0012_credit_paid_date
Agrega paid_date DATE nullable. Los fiados anteriores conservan importes, estado
y fecha de origen; no se asigna una fecha de pago ficticia. Un pagado histórico
sin fecha sigue sin fecha al editar otros campos o repetir Marcar pagado. La
restricción ck_credit_payment_date impide tener fecha en un fiado no pagado.
Requiere backup y ensayo en copia igual que las otras migraciones; no hay
downgrade que descarte fechas registradas.
