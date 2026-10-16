# Gestión del negocio

Se usa sin login en la red local. Ventas y egresos son independientes de MP y de
las facturas. No se crean ventas al emitir un comprobante ni al recibir un pago.

## Ventas del día
Fecha (hoy en Buenos Aires, editable) y total vendido, incluyendo efectivo y MP.
Una venta por fecha; cero es válido, un día sin registrar sigue sin información.
El icono de lápiz abre Editar con los mismos dos campos. No exige motivo.

## Egresos
Fecha, importe positivo, tipo En Blanco o En Negro, proveedor opcional y descripción
opcional. La búsqueda consulta hasta 20 coincidencias por nombre; permite escribir,
seleccionar con clic o flechas/Enter y borrar para dejar Sin proveedor.
No hay medios, categorías adicionales, estados de registro ni otros ingresos.

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
El indicador interno active conserva excluidas las anulaciones heredadas; no se
expone como un campo ni se admite su modificación desde el formulario de registros.

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

## Precarga desde Excel
scripts/supplier_seed.py genera un INSERT y CSV de equivalencias, sin conectar a la DB.
Acepta --aliases para variantes confirmadas; las abreviaturas o conceptos dudosos
se conservan separados para que la usuaria los edite/elimine. El INSERT usa
ON CONFLICT (name_key) DO NOTHING, no pisa proveedores existentes. Originales,
equivalencias privadas y SQL generado permanecen fuera de Git.
