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
El encabezado muestra el ícono de ARCA DYS centrado y Dulce y Salado debajo. En el celular,
pulsar el icono de tres líneas junto al nombre de la sección para desplegar las opciones; no tiene flecha.
Al entrar a otra pantalla se cierra y muestra el nombre de la sección elegida.
En escritorio, el botón con el panel y la flecha permite contraer y volver a abrir
la barra lateral. El navegador recuerda la elección. Administración
está abajo a la izquierda en esa barra, encima de ARCA DYS. Al ingresar,
Salir queda allí. En celular estos controles aparecen al desplegar el menú.

En la pantalla de inicio, el icono de la app dice **ARCA DYS** y muestra una
caja registradora. La misma caja identifica la pestaña del navegador. Para
instalar la app, seguí los [pasos para tu navegador](PWA_LAN.md#instalar-en-el-teléfono).

Ingresá importes en pesos enteros. Las pantallas descartan los centavos al mostrar
los montos, por ejemplo 123,99 se ve como 123. Los campos numéricos no tienen
flechas para sumar o restar. En ventas podés completar efectivo, Mercado Pago
o ambos. El que se deja vacío se toma como cero y debe completarse al menos uno.

## Facturar
En Facturación, cambiar Facturado, las fechas o las filas por página actualiza
los resultados y vuelve a la primera página del listado, manteniendo la posición
en la pantalla. Buscar aplica los mismos filtros.
En Facturación elegir cobros y FACTURAR SELECCIONADOS, o FACTURAR TODO para los pagos
disponibles del filtro completo, incluso en otras páginas. Revisar importe/cantidad
y confirmar. Factura por importe permite ingresar un total independiente de MP.
La confirmación vence a los 15 minutos. El comprobante sigue siendo Factura C,
Efectivo, con reparto de cotillón y repostería 50/50. La factura y su QR conservan
el importe exacto de los cobros, incluidos sus centavos cuando los tengan.

La solicitud queda guardada y la pantalla actualiza el resultado. Descargar el PDF
de la misma factura tantas veces como haga falta. Si queda Por verificar, usar
Consultar comprobante y, si corresponde, Reintentar esta solicitud. No crear otro
intento para resolver una descarga o respuesta perdida. Historial de solicitudes
permite volver al resultado. No se cargan ventas ni egresos al facturar.

## Registrar ventas del día
En Gestión pulsar Registrar ventas del día. La fecha empieza en hoy y se puede
cambiar. Ingresar el monto en efectivo. Mercado Pago propone la parte entera del
total aprobado de esa fecha, incluidos los cobros facturados. Podés editarla.
Total vendido muestra la suma. Para modificar un cierre, pulsar el lápiz.
Los cierres anteriores sin desglose requieren
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
Gestión abre con Mostrar en Todos y el rango desde el primer día del mes hasta hoy.
Los filtros siempre están visibles, arriba de los totales. Cambiar el tipo o
proveedor actualiza los resultados. Para cambiar el rango, completá fechas
en orden; si querés filtrar con una sola fecha, usá Buscar. Los totales abarcan
todas las coincidencias.
Elegir un proveedor muestra sus egresos, incluidos los de proveedores inactivos.
Desde el botón Proveedores, a la derecha encima de los filtros, se puede registrar
o editar nombre, contacto, notas, CBU y alias. Para dejar de elegir un proveedor en
nuevos egresos y conservar su historial, marcá Inactivo y guardá. Eliminar pide
confirmación y solo borra fichas sin registros vinculados. Las ayudas se abren pulsando ?.

Los proveedores y movimientos anteriores se incorporan una sola vez por consola,
según [la guía técnica de carga JSON](IMPORTACION_JSON.md). No hay pantalla de
importación ni hace falta ejecutar SQL en Adminer. Después se modifican proveedores
y registros desde sus formularios habituales.

## Resumen
Resumen abre en el mes actual. Elegir Año o Mes aplica el período de calendario
y reemplaza las fechas personalizadas. Si completás ambas fechas en orden, se
aplica el rango y el Excel usa esas mismas fechas. Ver resumen actualiza las cifras
en la misma pantalla.
Se muestran Ventas, Egresos en blanco, Egresos en negro,
Total Egresos, Pago de sueldos y Ganancia (ventas menos egresos y sueldos).
También muestra efectivo/MP y cuánto se pagó a cada empleado. Promedio diario,
gráfico y detalle mensual ayudan a comparar. Los cobros y facturas están separados.
Las tarjetas mantienen el signo de peso junto al importe. Los separadores distinguen
los desgloses y las tablas alternan filas y destacan las columnas de totales.
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
Fecha desde o Fecha hasta actualiza el reporte automáticamente. Se puede filtrar
con una sola fecha como límite. El total incluye todas las páginas del filtro.
Usar el lápiz para editar. Se descuenta en Ganancia.

## Fiados
La opción A está en revisión de desarrollo, sin actualizar la Raspberry.
Preparación de la instancia con ejemplos ficticios: [FIADOS.md](FIADOS.md).

El listado abre en **Con deuda**. **Sin deuda** y **Todas** cambian el filtro al
pulsarlos. Escribí nombre, apellido o referencia y pulsá Enter o Buscar; `perez`
encuentra a Marcela Pérez. El total corresponde a todo el filtro, incluidas las
páginas siguientes.

En **Nuevo fiado**, escribí parte del nombre y elegí una persona de la lista que
aparece sobre el formulario. También podés usar flechas y Enter; Escape cierra
la lista. Para alguien nuevo, pulsá **Crear una persona nueva**, completá nombre
y una referencia opcional. Los nombres parecidos muestran una advertencia antes
de crear otra cuenta. Cada persona conserva su identidad aunque se corrija el nombre.

Ingresá el importe entero, la fecha y una observación opcional. Al escribir
`10000` verás `10.000`; también podés pegar un importe con puntos de miles.
No se aceptan comas ni decimales. Fecha empieza en hoy y no admite un día futuro.
Guardar registra la compra y abre la cuenta.

**Registrar pago** permite abonar una parte. Revisá el nombre, importe, fecha y
saldo resultante antes de confirmar. **Saldar** prepara un pago por todo el saldo.
El sistema rechaza un pago mayor a la deuda y pide revisar si otra ventana cambió
la cuenta. Un pago se aplica al saldo global, sin marcar compras por separado.

Al llegar a cero, el período pasa al **Historial**. Una nueva compra inicia otro
período y conserva los anteriores. Para corregir un movimiento, pulsá su lápiz:
importe, fecha y detalle aparecen completos. Corregí los productos y guardá.
**Eliminar** muestra una confirmación antes de retirarlo del saldo. Se conservan
internamente los originales y sus correcciones. Una corrección de importe o baja
que deje pagos mayores a la deuda se rechaza; revisá primero esos pagos.

El lápiz junto al nombre edita los datos de la persona y su celular. Ingresá solo
el código de área y número: 10 dígitos, sin 0 inicial, 15, espacios ni signos.
El prefijo argentino se agrega al preparar WhatsApp. El botón con su icono está
en la cabecera del reporte. **Enviar detalle por WhatsApp** muestra
fechas, importes, productos/observaciones y saldo. Elegí Período actual o Historial
completo: el mensaje cambia automáticamente. Pulsá **Abrir WhatsApp**, encima del
mensaje. El texto queda
preparado; lo enviás desde WhatsApp. Si es muy largo habrá varias partes numeradas.
Si no hay celular, aparece el enlace para agregarlo.

Los movimientos se leen por columnas y aparece primero el último registrado.
El lápiz está en la primera columna; Eliminar se encuentra dentro de su edición.
Las notificaciones flotan arriba al centro y desaparecen a los dos segundos;
la cruz permite cerrarlas antes.

Si aparece el aviso de registros anteriores, entrá en **Revisar y vincular** y
elegí expresamente a quién pertenece cada uno. Un pendiente incorpora el saldo;
un pagado se conserva en **Archivo anterior**, sin inventar un pago ni una fecha
desconocida. No se fusionan nombres automáticamente ni se recuperan eliminados.
Un importe histórico dudoso requiere conciliación antes de trasladarlo.

Fiados sigue siendo independiente: registrar compras, pagos o anulaciones no
suma ventas ni modifica caja, Ganancia, Mercado Pago o facturación.


## Correcciones de Sueldos y botones comunes · 21/11/2026

Para quitar un pago de sueldo equivocado, entrar por el lápiz, pulsar Eliminar y
confirmar. Cancelar vuelve sin cambios. La baja conserva fecha, empleado, importe,
tipo y registro original; deja de contar en Sueldos, Resumen y Excel. No representa
un reintegro de dinero ni una operación en Mercado Pago. Una nueva carga usa un
formulario nuevo; reenviar el anterior no reactiva lo eliminado.

Guardar tiene ese mismo nombre en altas/ediciones. Cancelar está a la izquierda;
Guardar y Eliminar a la derecha, con Eliminar siempre rojo. En Gestión se elimina
solo al editar, no desde la fila del reporte. En Fiados el resumen dice Total fiado.
