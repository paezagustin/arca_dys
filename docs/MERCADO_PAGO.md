# Mercado Pago: contratos, recepción y recuperación

## Recepción y procesamiento
El POST se confirma con 200 únicamente después de guardar la notificación en
mp_events. Un worker liviano en el mismo proceso web consulta PostgreSQL cada 3s;
no agrega Redis, Celery ni otro contenedor. Reclama filas con FOR UPDATE SKIP LOCKED.
Tras un reinicio retoma pendientes/errores. No requiere esperar otro cobro real.
Las consultas GET usan timeout conexión/lectura 5/10s, sin redirects. Nunca se
invocan endpoints de cobrar, devolver dinero o modificar aplicaciones MP.

Una transacción guarda pago y PaymentChange junto con el resultado del evento.
Se serializan las actualizaciones por ID externo, y la PK de mp_payment_identities
impide duplicar pagos mediante un trigger transaccional, incluso con INSERT
concurrentes. payments conserva su índice no único y todas las filas históricas.
Eventos anteriores no reemplazan información más reciente del proveedor.
Importes contradictorios o estados distintos con igual timestamp quedan para revisar.
No se cambian facturas ni el indicador facturado por devoluciones/contracargos.
Devoluciones parciales se registran como partially_refunded y requieren revisión;
no habilitan facturar una fracción del pago ni una nota de crédito automática.

Los eventos con identidad propia se deduplican por tema/recurso/ID de evento.
IPN sin identidad fiable conserva cada entrega; su efecto es idempotente por pago
y fecha del proveedor. Errores reintentan con espera creciente hasta 300s, sin
descartar notificaciones. El panel operativo permite revisar/reintentar eventos.
Nunca se guardan firmas o tokens en el payload ni se imprime el JSON completo.

## Históricos repetidos e integridad
Los grupos repetidos se conservan completos y bloqueados: no se elige un pago
canónico, no se actualizan sus estados/JSON/marcas ni se reasignan facturas.
Quedan fuera de la selección y envío fiscal y de la sugerencia del cierre diario.
Una notificación directa queda en review (Conciliación pendiente), sin consultar
al proveedor. Si una orden devuelve ese ID, se conserva la respuesta y se omite
solo su actualización; el resto de los pagos puede procesarse de forma idempotente.
review no se reintenta automáticamente ni cambia reservas o documentos fiscales.

0013 conserva snapshots completos de los pagos existentes; una actualización
posterior de un pago no repetido guarda previous_data en PaymentChange. Las
respuestas canónicas consultadas se agregan por intento a MPEvent.resource_responses,
incluso si una validación impide aplicarlas. Un reintento conserva las respuestas
anteriores con su fecha y resultado. Los campos anteriores no se rellenan con
datos inventados. La migración/recuperación manual y su compatibilidad con 0004
se detallan en [MIGRACION_MP_LEGACY.md](MIGRACION_MP_LEGACY.md).

## Entradas y configuración
Producción requiere MP_ACCESS_TOKEN y MP_COLLECTOR_ID de la cuenta receptora.
La API comprueba el propietario de cada recurso/pago; la notificación sola no
acredita que haya existido un cobro. Dev/test usan exclusivamente el simulador.

- `/mp/webhook`: firma HMAC SHA256 usando MP_WEBHOOK_SECRET. El manifest toma
  data.id de la query en minúsculas, x-request-id y ts de x-signature; el ID del
  cuerpo debe coincidir. Firma ausente/incorrecta retorna 401 sin consultar MP.
- `/mp/webhook/legacy/<token>`: solo para QR/IPN cuyos contratos no firman. Requiere
  MP_LEGACY_WEBHOOK_TOKEN aleatorio de al menos 32 caracteres; se oculta en los
  logs de acceso. No habilita excepciones en la entrada firmada. Configurar la URL
  completa en el producto que corresponda. No usar secretos reales en ejemplos/tests.

Configurar NGROK y notificaciones es una operación de publicación del usuario;
el desarrollo no modifica la aplicación MP ni prueba esta URL contra producción.
La firma autentica la identidad del recurso, no todos los campos del cuerpo: los
importes/estados siempre se obtienen nuevamente desde la API de la cuenta.
No se aplica una ventana temporal corta a ts que invalide reentregas legítimas;
la persistencia de identidad/fecha y las consultas autoritativas controlan su efecto.

## Formatos admitidos
payment → GET /v1/payments/{id}. merchant_order → GET /merchant_orders/{id},
verificación de collector y consulta de cada pago. order/orders → GET /v1/orders/{id},
user_id y referencia canónica de transactions.payments.reference_id, contrastando
importe con GET /v1/payments. Esto evita contar otra vez un pago notificado por dos temas.
Una orden final sin referencia canónica se conserva como error para revisar el
contrato; nunca se inventa otra identidad. Los formatos particulares se ensayan con
fixtures ficticios, no con dinero ni notificaciones privadas reales.
point_integration_wh/point_integration_ipn consulta el payment intent y luego
payment.id cuando existe; un intento sin pago no crea ingresos. Los temas no
admitidos se conservan como ignorados y no generan consultas arbitrarias.
Se aceptan data.id, resource, query topic/id y URLs MP de rutas concretas. No se
siguen URLs arbitrarias recibidas en un webhook.

Las transferencias se incorporan si MP las expone a esta aplicación como pagos
notificados/consultables. No se garantiza que todo movimiento de una cuenta MP
produzca un webhook. La conciliación con la cuenta y las ventas manuales sigue
siendo necesaria; ventas, cobros y facturas no se suman automáticamente entre sí.

## Evidencia y límites
Pruebas con datos ficticios de reentrega, concurrencia, orden temporal, fallos/reinicio,
firma, propietario, URLs y proveedor GET. Simulador web permite reutilizar un ID para
approved → refunded; ambos cambios se conservan sin volver a facturar.
No se certificaron los formatos efectivos de la cuenta del usuario ni conexión real.
Antes de publicar, contrastar notificaciones anonimizadas de Point/QR/transferencias
con estos contratos. Cualquier diferencia queda visible, sin descartar ni facturar.

Fuentes primarias consultadas:
- https://www.mercadopago.com.ar/developers/en/docs/your-integrations/notifications/webhooks
- https://www.mercadopago.com.ar/developers/en/docs/your-integrations/notifications/ipn
- https://www.mercadopago.com.ar/developers/en/reference/in-person-payments/point/orders/get-order/get
