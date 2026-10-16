# Importación trazable del libro Negocio

Formato: XLSX con hojas ingresos y egresos y dashboard. Encabezados del detalle:
FECHA, VENTAS DEL DIA, COMPRAS EN BLANCO, MONTO, COMPRAS EN NEGRO, MONTO2.
Subir hasta 5 MB; límites internos de 50 MB descomprimidos, 500 entradas ZIP,
10000 filas y 30 columnas por hoja leída. Macros rechazadas. openpyxl read_only,
keep_links=false y defusedxml; no ejecución de fórmulas, enlaces o instrucciones.
Referencias: https://openpyxl.readthedocs.io/en/stable/ y sus notas de seguridad.

## Datos y revisión
- Se conserva lote/archivo/hash, identificador de libro, hoja/fila/columna,
  celdas originales tipadas, fórmulas y resultados guardados por Excel.
- Cada venta B y compra D/F tiene una propuesta independiente. Fechas/importes
  ambiguos van a revisión, sin reemplazarlos por cero. Una compra con importe válido
  sin descripción conserva el importe, la clasificación original y proveedor vacío.
- La clasificación COMPRAS EN BLANCO / COMPRAS EN NEGRO se conserva en las celdas
  originales y determina el tipo de egreso white/black,
  sin inferir tratamiento fiscal. Ninguna importación genera pagos MP ni facturas.
- Preparar no escribe gestión. Confirmar importa solo filas listas; conflictos de
  fecha/origen regresan a revisión. Revisión/omisión no piden motivo ni guardan historial de cambios. Los valores originales nunca se sobrescriben.
- Las etiquetas sugieren nombres parecidos de proveedores, sin asignaciones ni
  fusiones automáticas. Elegir explícitamente el proveedor, o conservar descripción.
  La asignación solo aplica a filas que se importen después; las ya importadas se
  corrigen desde Gestión. Un proveedor archivado bloquea esa asignación futura.

La identidad del archivo es dataset + SHA256. La de una celda es dataset + hoja +
fila + columna. Usar el mismo identificador para versiones del mismo libro y uno
distinto para otro libro/año. Un archivo repetido abre su lote existente. En una
versión nueva, un origen idéntico no vuelve a sumarse; si cambió, se conserva en
revisión con enlace al registro anterior. No insertar/eliminar/reordenar filas del
libro entre versiones sin revisar los conflictos: las coordenadas son su identidad.
Las confirmaciones se serializan con bloqueo PostgreSQL y las restricciones de
gestión protegen carreras con cargas manuales. Un reintento no duplica registros.

## Dashboard y conciliación
El control mensual suma por FECHA el detalle numérico válido y compara ventas,
compras D/F, compras totales y diferencia con resultados guardados del dashboard.
No recalcula fórmulas Excel ni atribuye cero a un resultado ausente. Los conteos por
rangos fijos del libro pueden estar desplazados; el sistema cuenta por fecha.
Los dos bloques manuales de filas 65 en adelante (C:F y H:K) se muestran como series
separadas RECIBIDO/EMITIDO, con blancos y diferencias originales disponibles. No
son ventas/gastos ni reemplazan los comprobantes emitidos por el sistema. El resto
de celdas del dashboard sigue consultable en Originales e históricos del lote.
Sueldos/adelantos no se leen ni almacenan; el original queda fuera de Git.

`scripts/verify_excel.py` permite contrastar un archivo privado en el Compose test:
crea una base efímera propia, migra, importa, concilia por mes/clasificación, repite
importación, compara celdas y elimina solo su base temporal. No imprime importes.

```powershell
docker compose -f docker-compose.test.yml run --build --rm -v C:/ruta/Negocio2026.xlsx:/private/original.xlsx:ro test python -m scripts.verify_excel /private/original.xlsx
```

Evidencia con el original adjunto: 9 meses, 493 registros válidos y 30 filas para
revisión; sumas mensuales numéricas exactas, reimportación sin duplicados, históricos
íntegros, sueldos excluidos y hash original sin cambios. No se incorporó ese contenido
a fixtures, Git ni al entorno dev. La base de verificación se eliminó al terminar.
