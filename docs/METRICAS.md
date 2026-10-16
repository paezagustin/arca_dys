# Métricas del negocio

El resumen filtra por año y mes, con comparación contra el mes anterior (enero
contra diciembre anterior) o contra el año anterior. Usa agregaciones SQL y NUMERIC,
sin cargar el historial completo ni agregar servicios o librerías de gráficos.
El gráfico SVG tiene descripción accesible y tabla con importes exactos.

- Ventas: total manual de ventas vigentes por fecha. Incluye lo cobrado en efectivo
  y MP según la carga de la usuaria. Una venta cero cuenta como día registrado;
  un día sin carga no participa en promedio, mínimo ni máximo.
- Otros ingresos: movimientos income vigentes; no incluyen ventas ya registradas.
- Egresos: movimientos expense vigentes, con desglose paginado independiente por
  proveedor y categoría. Los pagos sin proveedor siguen formando parte del total.
- Resultado registrado: ventas + otros ingresos − egresos. Usa únicamente registros
  existentes, sin estimar días faltantes ni calcular costo de mercadería/stock/sueldos.
  No se presenta como ganancia neta contable. Un período sin gestión muestra ausencia
  de registros, conservando los ceros que sí fueron cargados.
- MP: pagos de estado actual approved, positivos, por fecha de aprobación en Buenos
  Aires. Devoluciones posteriores cambian ese agregado; no es un histórico de saldo
  ni un informe de liquidaciones, comisiones o ingresos netos de Mercado Pago.
- Facturación: comprobantes con número, fecha, total y CAE guardados, por fecha de
  emisión. Una factura independiente se cuenta aquí y nunca crea otra venta.

Cobros y facturas se muestran separados y no se suman a ventas. No hay métricas de
saldos pendientes ni parciales. Los bloques manuales del dashboard Excel se consultan
por lote en Históricos; no se mezclan con estas fuentes. Sus fórmulas y blancos
originales se conservan.

Variación: diferencia entre importes comparables; porcentaje solo si la base es
positiva. Si falta un período o la base es cero, el porcentaje queda no disponible.
Los límites de mes incluyen todo el último día, incluidos timestamps de MP.
El año bisiesto, el cruce diciembre/enero, las anulaciones, la importación y los
desgloses paginados están cubiertos por tests de conciliación.
