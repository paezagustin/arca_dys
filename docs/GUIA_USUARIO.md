# Guía de uso

## Abrir en Windows
Con Docker Desktop iniciado, desde la carpeta del proyecto:

```powershell
docker compose -f docker-compose.dev.yml up --build -d
```

Abrir http://localhost:8001. Facturación, Gestión y Resumen funcionan sin ingresar.
Para ver el menú completo, pulsar Administración e ingresar con admin / pruebas-locales
solo en este entorno simulado. La cuenta de prueba no se crea en producción.
Pruebas permite cargar cobros ficticios sin NGROK, claves ni operaciones reales.
El banner de simulación y los PDF indican SIN VALIDEZ FISCAL.

## Facturar
En Facturación elegir cobros y FACTURAR SELECCIONADOS, o FACTURAR TODO para los pagos
disponibles del filtro completo, incluso en otras páginas. Revisar importe/cantidad
y confirmar. Factura por importe permite ingresar un total independiente de MP.
La confirmación vence a los 15 minutos. El comprobante sigue siendo Factura C,
Efectivo, con reparto de cotillón y repostería 50/50.

La solicitud queda guardada y la pantalla actualiza el resultado. Descargar el PDF
de la misma factura tantas veces como haga falta. Si queda Por verificar, usar
Consultar comprobante y, si corresponde, Reintentar esta solicitud. No crear otro
intento para resolver una descarga o respuesta perdida. Historial de solicitudes
permite volver al resultado. No se cargan ventas ni egresos al facturar.

## Registrar ventas del día
En Gestión pulsar Registrar ventas del día. La fecha empieza en hoy y se puede
cambiar. Ingresar el total de la caja: efectivo más Mercado Pago. Guardar.
Para modificarlo, pulsar el lápiz de ese registro, cambiar fecha/total y guardar.
No se pide motivo ni se muestra historial. Solo hay una venta por día; cero es
válido y un día sin registrar no se interpreta como cero.

## Registrar egresos y proveedores
En Gestión pulsar Registrar egreso. Completar fecha, importe y En Blanco o En Negro.
Buscar el proveedor escribiendo su nombre y elegirlo de la lista; también se puede
dejar vacío. La descripción es opcional. Guardar.
Desde Proveedores se puede registrar/editar nombre, contacto y notas. Eliminar sirve
si no hay registros vinculados; en caso contrario se puede archivar para que deje
de aparecer al cargar nuevos egresos. Las ayudas se abren pulsando ?.

El script de proveedores entregado se pega y ejecuta en la consulta SQL de Adminer,
en la base del negocio ya migrada. No reemplaza nombres existentes y repetirlo no
duplica proveedores. El CSV adjunto muestra cada referencia del Excel y el nombre
normalizado. Los nombres dudosos se dejan separados para corregirlos en Proveedores.

## Importar los registros del Excel
Gestión → Importar Excel. Conservar el original y usar el mismo identificador de
libro para sus versiones. Subir, revisar la vista previa y elegir Importar filas
listas. Se leen ingresos y egresos y dashboard; sueldos/adelantos quedan excluidos.
Las celdas ambiguas quedan para revisar. Completar los datos o elegir Omitir, sin
inventar importes. Guardar revisión no importa: después confirmar las filas listas.
Las celdas originales permanecen disponibles. Repetir un archivo no duplica datos.
Los proveedores se pueden asociar a las etiquetas antes de confirmar.
No reordenar filas del libro entre versiones: el origen usa hoja, fila y columna.

## Resumen
Elegir año/mes o Todo el año. Se muestran Ventas, Egresos en blanco, Egresos en negro,
Total Egresos y Ganancia (ventas menos egresos, como estimación). Promedio diario,
gráfico y detalle mensual ayudan a comparar. Los cobros y facturas están separados.
Exportar Excel descarga la hoja de ingresos y egresos del período, con sus seis
columnas originales. Varias compras de un día ocupan filas adicionales sin repetir
la venta. Si un egreso antiguo no tiene tipo, editarlo antes de exportar.

## Administración
Solo admin ve Cobros MP, Auditoría, Configuración, Conexión MP y Pruebas (esta última
solo en simulación). Al salir vuelve el menú de tres secciones de uso diario.
Cambios del emisor/límites afectan nuevas facturas; las emitidas conservan sus datos.
Las notificaciones MP se revisan/reintentan sin facturación automática.

## Detener o resolver un arranque
Para detener sin perder datos locales:

```powershell
docker compose -f docker-compose.dev.yml stop
docker compose -f docker-compose.dev.yml up -d
```

No usar down --volumes para detener desarrollo. Si no abre, comprobar Docker y el
puerto 8001 y consultar los logs de fastapi. La actualización de la Raspberry se
hace por separado siguiendo OPERACION_RASPBERRY.md; ningún push la despliega.
