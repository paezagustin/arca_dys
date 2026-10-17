# Resumen y exportación

El período admite año completo, un mes o ambas fechas Desde/Hasta (inclusive),
incluido un único día. Las fechas explícitas prevalecen sobre año/mes; el gráfico
y detalle mensual siguen mostrando el año seleccionado. Los cálculos SQL usan NUMERIC:

- Ventas: suma del total vendido ingresado manualmente, incluyendo efectivo y MP.
- Egresos en blanco y Egresos en negro: sumas por el tipo seleccionado.
- Total Egresos: todos los egresos del período, incluidos los heredados aún sin tipo.
- Efectivo/Mercado Pago: sumas del desglose guardado de cada cierre. Los totales
  históricos sin desglose se muestran aparte y no se atribuyen a un medio.
- Pago de sueldos: suma del período y totales de Francisco y Juan Cruz.
- Ganancia: Ventas − Total Egresos − Pago de sueldos, estimación con los registros cargados.

Un día sin carga no cuenta en promedio/mínimo/máximo; una venta cero sí cuenta.
Un período vacío muestra Sin registros. Comparaciones entre períodos se consultan
con ?. El gráfico SVG muestra ventas/egresos/sueldos por mes; la tabla también contiene
efectivo y Mercado Pago. Fiados se consulta por separado y no modifica Ganancia. Los egresos se
agrupan por proveedor y tipo; cada tabla conserva paginación independiente.

MP (aprobados según estado actual y fecha de aprobación) y facturas con CAE guardado
(por fecha de emisión) se muestran separados. Nunca se suman otra vez a Ventas.
No hay saldos pendientes ni facturación parcial. Las ventas/egresos de la carga
JSON participan en estos mismos cálculos. Las ventas sin desglose permanecen
separadas de efectivo/MP. No se importan bloques manuales del dashboard del Excel.

## Exportar Excel
El botón de Resumen descarga el período seleccionado completo, sin paginación.
La hoja ingresos y egresos tiene las seis columnas originales: FECHA, VENTAS DEL DIA,
COMPRAS EN BLANCO, MONTO, COMPRAS EN NEGRO, MONTO2. Conserva encabezado azul, tabla
con bandas, fechas y moneda numéricas, filtro y cabecera inmovilizada. Se ajustan
anchos para que los nombres y valores se lean completos.

Se incluye cada fecha del período. Las fechas sin ventas conservan la celda vacía.
Con varias compras por día se agregan filas y la venta aparece una sola vez.
El concepto conserva proveedor y descripción. Nombres que comienzan con = se
exportan como texto, sin ejecutar fórmulas. Los importes que exceden las 15 cifras
significativas de Excel se rechazan con un mensaje, sin truncar centavos.
Antes de exportar deben clasificarse los egresos heredados sin tipo: de ese modo
los montos de MONTO/MONTO2 concilian con Total Egresos.

Las hojas adicionales Ventas (fecha, efectivo, Mercado Pago, total) y Sueldos
(fecha, empleado, monto, tipo) contienen solo registros del mismo período exportado.
No duplican pagos de sueldos dentro de las compras de la primera hoja. Los cierres
anteriores conservan efectivo/MP vacíos. Los importes continúan siendo numéricos y
se verifica la precisión también en estas hojas. Comparar fechas usa el intervalo
anterior de la misma duración; las comparaciones se consultan con el botón ?.
