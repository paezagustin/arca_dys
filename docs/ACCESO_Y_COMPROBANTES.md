# Acceso, configuración y comprobantes

## Acceso
Las páginas, configuración, descargas y operaciones requieren una sesión. Webhooks
MP usan su propio contrato; health y assets son públicos. Las sesiones aleatorias
se guardan hasheadas en PostgreSQL, expiran a las 12 horas y se revocan al salir.
Cookies HttpOnly/SameSite; Secure en producción. Formularios POST requieren CSRF,
incluido salir y reintentos. El login usa nonce de formulario y cookie separada.
Contraseñas PBKDF2 SHA256, salt aleatorio, 600000 iteraciones. Diez intentos inválidos
por usuario/origen bloquean ese acceso 10 minutos. No hay registro público de cuentas.
No se requiere Redis, JWT, servidor de identidad ni un frontend compilado.

Dev/test crean exclusivamente la cuenta admin / pruebas-locales, con datos ficticios.
La creación está bloqueada en producción. Después de migrar una instalación real:

```sh
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm --no-deps -e ALLOW_LIVE_OPERATIONS=true fastapi python -m app.manage create-user --username administracion --role admin
```

El comando pide contraseña por entrada oculta, no por argumento ni en Git. No
reemplaza cuentas existentes ni hace operaciones con proveedores. Rol operator
permite trabajar con facturación/gestión; solo admin cambia configuración e integración.
No se creó ninguna cuenta ni contraseña en la Raspberry durante el desarrollo.

## Configuración del emisor
La página Configuración permite nombre/razón social, domicilio, CUIT, condición
fiscal compatible con C, Ingresos Brutos, inicio y punto de venta. No se infiere la
condición real del emisor: en producción queda vacía hasta que se configure.
Factura C/tipo 11, consumidor final, Efectivo y reparto 50/50 permanecen fijos.
Los límites mínimo/máximo se validan y son controles de aplicación, no una regla
legal. Cada cambio guarda usuario, fecha, valores anteriores y nuevos. Un número
de versión evita pisar cambios de otra pantalla.

La preparación fiscal toma una copia inmutable y se coordina con el guardado de
configuración mediante bloqueo compartido/exclusivo. Cambiar datos después no
modifica facturas previas. El CUIT debe coincidir con ARCA_CUIT de los certificados
para habilitar una nueva emisión/recuperación. Las claves permanecen fuera del panel.
Antes de publicar, verificar régimen, punto de venta, certificados y datos reales
con quien administra la facturación; no usar la configuración ficticia de desarrollo.

## Factura independiente
Factura por importe prepara una confirmación persistente, privada para el usuario
que la creó, con importe/configuración y vencimiento de 15 minutos. Hasta confirmar
no se inicia emisión. Se revalidan importe, vigencia y versión de configuración.
Repetir la confirmación reutiliza el mismo intento, incluso si se perdió su respuesta.
No crea pagos MP ni ventas diarias. No permite imputaciones parciales a un cobro.
La misma infraestructura de confirmación se reutiliza para la selección por filtros.

## PDF y QR
Un único generador ReportLab local reemplaza Chromium y PDF remoto. El PDF se
construye desde el registro y su snapshot fiscal. El logo procede del asset existente.
Dos renglones: Cotillón y Repostería; Decimal redondea la primera mitad al centavo y
la segunda es el resto, conservando exactamente el total. Condición de venta Efectivo.
El QR fiscal se genera por comprobante, con Base64 del JSON especificado por ARCA:
fecha, CUIT, punto/tipo/número, importe, PES/cotización, documento y CAE.
No se consulta la URL del QR durante las pruebas. Las simulaciones llevan aviso
SIN VALIDEZ FISCAL y QR textual de simulación, sin simular una autorización real.

Los históricos sin snapshot conservan sus valores conocidos; el PDF indica
DATOS FISCALES INCOMPLETOS y no inventa emisor ni genera QR fiscal. No reemplaza el
original; su pdf_url previo sigue almacenado. No se rellenan respuestas o snapshots
históricos consultando producción ni copiando la configuración actual.

Verificaciones: autenticación/roles, expiración/revocación/CSRF, auditoría de ajustes,
confirmaciones repetidas/vencidas/configuración cambiada, formulario por importe,
reparto exacto y lectura del QR desde el PDF rasterizado con PDFium/ZXing.
Muestra visual simulada revisada, una página sin superposiciones. Imagen amd64
328861983 bytes frente a 2216024526 iniciales; no equivale a consumo RAM en Raspberry.

Referencia QR: https://arca.gob.ar/fe/qr/documentos/QRespecificaciones.pdf
