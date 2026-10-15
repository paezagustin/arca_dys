# Guía de pruebas locales

Esta versión es el primer paso de la refactorización. No sustituye todavía al
sistema de la Raspberry y no emite comprobantes reales.

## Abrir el sistema en Windows
Con Docker Desktop iniciado, abrir PowerShell en la carpeta del repositorio:

```powershell
docker compose -f docker-compose.dev.yml up --build -d
```

Abrir http://localhost:8001/dev. No hay que configurar NGROK, ARCA ni Mercado Pago.
La primera construcción descarga dependencias. Los siguientes arranques conservan
los pagos ficticios en el volumen local de desarrollo.

## Probar una factura
1. Pulsar **Cargar tres pagos de ejemplo**. Se abre Facturación.
2. Seleccionar un pago o varios y pulsar **FACTURAR SELECCIONADOS**.
3. Ver el resultado y descargar el PDF desde la tabla de facturas.
4. El archivo debe indicar **SIMULACION - SIN VALIDEZ FISCAL**.

Se pueden cargar más pagos ficticios ingresando importe y escenario desde /dev.
Pending/rejected/refunded y falla de API permiten verificar respuestas sin pagos reales.
La actualización de una devolución sobre un pago existente se hará en el hito MP.
El PDF de ejemplo es sencillo y no representa aún el diseño fiscal definitivo.

**FACTURAR TODO** conserva por ahora el contrato heredado del listado. La aplicación
de TODO al filtro completo junto con paginación se implementa en H5. La factura
independiente por importe pertenece a H4; todavía no se muestra como disponible.

## Detener y retomar
```powershell
docker compose -f docker-compose.dev.yml stop
docker compose -f docker-compose.dev.yml up -d
```

No usar `down --volumes` para detener desarrollo: eliminaría sus datos ficticios.
Los datos de la Raspberry no se montan en este entorno.

## Si no abre
```powershell
docker compose -f docker-compose.dev.yml ps
docker compose -f docker-compose.dev.yml logs --tail 60 fastapi
```

Comprobar Docker Desktop y que el puerto 8001 esté libre. No pegar claves ni cambiar
a modo production para resolver un error local.

## Funcionalidades del sistema final
Factura independiente; pagos completos de MP; ventas diarias manuales con efectivo+MP;
ingresos/egresos; proveedores simples; importación histórica del Excel y dashboard.
Se documentarán sus pantallas a medida que cada hito esté probado. Sin sueldos,
facturación parcial, cuentas corrientes de proveedores ni saldos pendientes en métricas.

## Recuperación de facturación
Después de facturar se abre el resultado de la solicitud. Si está autorizada,
descargar el PDF; un error de descarga permite repetirla sin emitir otra factura.
Si quedó "Por verificar", conservar la solicitud y usar "Consultar comprobante".
No facturar esos pagos con otra selección. Si no se encuentra autorización,
"Reintentar esta solicitud" vuelve a consultar y usa el mismo número e importe.
Si la consulta falla, el sistema conserva el estado y no reenvía. El soporte puede
identificar la operación con el número de solicitud mostrado en la pantalla.

## Probar cambios de Mercado Pago
En Pruebas locales, cargar un pago con ID SIM-ejemplo y luego elegir "Pago devuelto"
con el mismo ID e importe. Se actualiza ese pago, sin duplicarlo. Si ya tenía una
factura, esa factura sigue guardada; no se emite una nota de crédito por esta prueba.
Las notificaciones con error se conservan para revisar y reintentar, sin facturar.

## Ingresar y emitir por importe
En pruebas locales, usar admin / pruebas-locales. En la instalación real, usar la
cuenta creada por el administrador; la cuenta de prueba no existe allí.
En Facturación elegir "Factura por importe", ingresar total, revisar y confirmar.
Esta factura es independiente: no cambia cobros de Mercado Pago ni ventas diarias.
La confirmación vence a los 15 minutos y no se emite nada hasta aceptarla.
Al terminar se muestra el resultado con enlace PDF. Para cerrar la sesión, elegir Salir.

## Configuración y Mercado Pago
Solo la cuenta administradora puede cambiar los datos del emisor y límites de la
aplicación. Comprobar los datos antes de facturar; cambios posteriores se aplican a
nuevos comprobantes. Las claves de conexión se administran en la instalación.
Mercado Pago muestra las notificaciones y permite reintentar las que tienen error.
Consultar un pago por ID lo actualiza desde la cuenta, sin facturarlo automáticamente.
