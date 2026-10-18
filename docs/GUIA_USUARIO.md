# Guía de uso

## Abrir en Windows
Con Docker Desktop iniciado, desde la carpeta del proyecto:

```powershell
docker compose -f docker-compose.dev.yml up --build -d
```

Abrir http://localhost:8001. Facturación, Gestión, Resumen, Sueldos y Fiados funcionan sin ingresar.
Para ver el menú completo, pulsar Administración e ingresar con admin / pruebas-locales
solo en este entorno simulado. La cuenta de prueba no se crea en producción.
Pruebas permite cargar cobros ficticios sin NGROK, claves ni operaciones reales.
El banner de simulación y los PDF indican SIN VALIDEZ FISCAL.

## Navegación y montos
El encabezado muestra el logo centrado y Dulce y Salado debajo. En el celular,
pulsar el icono de tres líneas junto al nombre de la sección para desplegar las opciones; no tiene flecha.
Al entrar a otra pantalla se cierra y muestra el nombre de la sección elegida.
En escritorio las secciones quedan visibles en la barra lateral. Administración
está abajo a la izquierda en esa barra, con margen y encima de ARCA DYS; al ingresar,
Salir queda allí. En celular estos controles aparecen al desplegar el menú.

Los montos nuevos empiezan vacíos y muestran 0,00 como ayuda. Los importes guardados
siguen visibles al editar. En ventas puede completarse efectivo, Mercado Pago o
ambos; el que se deja vacío se toma como cero. No puede guardarse una caja con
ambos vacíos: para registrar cero hay que escribir 0 en uno de los campos. MP
continúa sugiriendo el importe de cobros de la fecha cuando hay un total positivo.

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
cambiar. Ingresar el monto en efectivo. Mercado Pago propone los cobros aprobados
sin facturar de esa fecha; se puede modificar. Total vendido muestra la suma. Guardar.
Para modificarlo, pulsar el lápiz y cambiar fecha/efectivo/MP. Al abrir una edición
se conservan los importes guardados. Los cierres anteriores sin desglose requieren
completar ambos importes reales para editarlos.
No se pide motivo ni se muestra historial. Solo hay una venta por día; cero es
válido y un día sin registrar no se interpreta como cero.
Si cargaste un día por error, usá Eliminar desde Gestión o desde su edición y
revisá fecha e importe antes de confirmar. Cancelar conserva el registro.

## Registrar egresos y proveedores
En Gestión pulsar Registrar egreso. Completar fecha, importe y En Blanco o En Negro.
Buscar el proveedor escribiendo su nombre y elegirlo de la lista; también se puede
dejar vacío. La descripción es opcional. Guardar.
Para un egreso cargado por error, usar Eliminar y confirmar. Se retira de los
listados y reportes; los datos originales se conservan internamente.
Los filtros de Gestión siempre están visibles, arriba de los totales. Elegir tipo,
proveedor y fechas y pulsar Buscar; los totales abarcan todas las coincidencias.
Elegir un proveedor muestra sus egresos, incluidos los de proveedores archivados.
Desde Proveedores se puede registrar/editar nombre, contacto y notas. Eliminar sirve
si no hay registros vinculados; en caso contrario se puede archivar para que deje
de aparecer al cargar nuevos egresos. Las ayudas se abren pulsando ?.

Los proveedores y movimientos anteriores se incorporan una sola vez por consola,
según [la guía técnica de carga JSON](IMPORTACION_JSON.md). No hay pantalla de
importación ni hace falta ejecutar SQL en Adminer. Después se modifican proveedores
y registros desde sus formularios habituales.

## Resumen
Elegir año/mes, Todo el año o completar ambas fechas para consultar un día/período. Se muestran Ventas, Egresos en blanco, Egresos en negro,
Total Egresos, Pago de sueldos y Ganancia (ventas menos egresos y sueldos).
También muestra efectivo/MP y cuánto se pagó a cada empleado. Promedio diario,
gráfico y detalle mensual ayudan a comparar. Los cobros y facturas están separados.
Las tarjetas mantienen el signo de peso junto al importe. Colores y separadores
distinguen efectivo, MP, históricos sin desglose y sueldos; las tablas alternan
filas y destacan las columnas de totales para facilitar la lectura.
Exportar Excel descarga la hoja de ingresos y egresos del período, con sus seis
columnas originales, además de las hojas Ventas y Sueldos del mismo período. Varias compras de un día ocupan filas adicionales sin repetir
la venta. Si un egreso antiguo no tiene tipo, editarlo antes de exportar.

## Administración
Solo admin ve Cobros MP, Auditoría, Configuración, Conexión MP y Pruebas (esta última
solo en simulación). Al salir vuelve el menú de cinco secciones de uso diario.
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

## Sueldos
Elegir fecha, empleado y monto. Tipo empieza en Mercado Pago y se puede cambiar
a Efectivo. Guardar. El reporte debajo muestra el mes actual; modificar empleado,
Fecha desde y Fecha hasta y pulsar Buscar para ver otro período. El total incluye
todas las páginas del filtro. Usar el lápiz para editar. Se descuenta en Ganancia.

## Fiados
Ingresar nombre, monto y, si hace falta, observación. Fecha empieza en hoy y Pagó
en No. Guardar. El listado muestra todos los no pagados; permite buscar por nombre,
fechas o pago. Pulsar Marcar pagado cuando corresponda; el lápiz permite corregir
cualquiera de los campos. Al marcar Sí se guarda y muestra automáticamente la
Fecha de pago del día. Editar otros datos no cambia esa fecha; volver a No la
quita. Los fiados pagados antes de esta mejora conservan la fecha vacía cuando
no se conoce. El registro no suma ventas ni modifica la caja automáticamente.
