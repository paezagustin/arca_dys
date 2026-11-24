# Faltantes y pedidos a proveedores

Faltantes está debajo de Fiados en el menú de ARCA DYS. Usa la sesión local y la
protección CSRF de los demás formularios. La lista es compartida entre dispositivos.

## Uso diario

1. En **Faltantes**, buscá por nombre, presentación o código de barras. Elegí el
   producto y pulsá **Registrar faltante**. La cantidad, unidad y observaciones
   son opcionales. Si no aparece, elegí **Crear y registrar faltante**.
2. Usá **Sin proveedor asociado** para encontrar faltantes sin un proveedor activo.
   Abrí **Gestionar proveedores** para completar los vínculos. En **Productos**
   podés buscar, editar, archivar y distinguir presentaciones. Desde **Productos
   por proveedor** o la ficha de Gestión podés seleccionar varias fichas de la
   página y asociarlas juntas. La preferencia solo orienta la compra.
3. En **Pedidos**, elegí un proveedor y seleccioná los productos. Ajustá cantidades
   y observaciones y revisá el mensaje. Podés copiarlo o abrir WhatsApp si el
   contacto de Gestión contiene un número único en un formato reconocible. Una
   vez hecho el pedido, pulsá **Registrar pedido realizado**. Copiar y abrir el
   enlace son acciones de consulta.
4. En **Historial**, abrí el pedido para recibir todo o resolver cada renglón.
   **Mantener pendiente de entrega** conserva el pedido abierto. **No entregado**
   y **Cancelar** devuelven ese producto a Faltantes y guardan el resultado de
   ese intento. Podés anotar observaciones incluso si el renglón sigue abierto.

El contacto de WhatsApp admite un número internacional explícito con `+`, el
formato `549` más código de área y número, o un celular argentino de diez
dígitos. Con un contacto libre ambiguo se ofrece copiar el texto. La vista
permite seleccionar el texto manualmente si el navegador restringe el portapapeles.
La aplicación conserva un borrador con cambios al pasar a WhatsApp y comprueba las
versiones al registrar. La coordinación del envío manual ocurre fuera del sistema.

## Datos y garantías

La revisión [`0022_restock`](../migrations/versions/0022_restock.py) agrega seis
tablas. Las rutas HTTP y plantillas viven en `app/api/restock.py` y
`app/templates/restock/`. `app/services/restock.py` concentra las reglas y
consultas. El módulo conserva la arquitectura FastAPI, Jinja y SQLAlchemy.

| Tabla | Datos y relaciones |
| --- | --- |
| `restock_products` | Ficha local e ID estable, presentación y código de barras. Identidad comercial opcional y única por `(source, external_id)`. |
| `restock_product_suppliers` | N:M con `suppliers`; clave primaria compuesta y hasta un preferido por producto. |
| `restock_needs` | Necesidad y datos estimados, fecha, estado y versión. Un índice parcial permite un solo faltante pendiente o pedido por producto. |
| `restock_orders` | Proveedor existente, nombre al registrar, UUID de confirmación, observaciones y fechas. |
| `restock_order_lines` | Resultado, cantidades, observaciones y datos de producto al registrar. Un índice parcial permite un solo renglón en espera por faltante. |
| `restock_catalog_sync` | Último intento, última sincronización exitosa y error por origen. |

```mermaid
stateDiagram-v2
    [*] --> Pendiente
    Pendiente --> Pedido: confirmar pedido
    Pedido --> Recibido: recibir
    Pedido --> Pendiente: no entregado o cancelado
    Pendiente --> Cancelado: cancelar faltante
    Recibido --> [*]
    Cancelado --> [*]
```

Registrar un pedido bloquea y revalida proveedor, productos y faltantes
seleccionados antes de escribir. Si algún producto dejó de ser elegible o cambió
su versión, se rechaza el pedido entero y se actualiza la lista. El registro
y todos sus renglones se confirman en la misma transacción. Un reintento del
mismo formulario y contenido devuelve el pedido original. La recepción bloquea
el pedido y los faltantes afectados en una transacción. El estado de la cabecera
se calcula a partir de los renglones; la fecha de cierre se guarda cuando se
resuelve el último pendiente de entrega.

Archivar un proveedor conserva vínculos e historial y lo retira de los pedidos
nuevos. Un producto archivado o retirado del catálogo deja de admitir nuevos
faltantes. Los pendientes y pedidos existentes siguen accesibles con una
advertencia y pueden resolverse, incluso si hay que asociar otro proveedor.
Cambiar asociaciones, una presentación o el nombre de un producto o proveedor
conserva los datos de los pedidos ya registrados.

Se reutilizan los filtros parciales de reportes. Las vistas dinámicas se sirven
con `Cache-Control: no-store`. La PWA actual usa el manifiesto y abre en línea;
en el repositorio no hay un service worker que cachee respuestas. Al volver a la
página se consultan los listados, preservando formularios con cambios.

## Catálogo Dulce y Salado

Dulce y Salado es el origen de los productos comerciales. ARCA DYS usa una copia
local para sus búsquedas, relaciones y pedidos. Guardá bolsas, etiquetas y otros
insumos como productos locales desde **Nuevo producto**. El nombre es el único
dato obligatorio. Los nombres y códigos similares generan una advertencia;
las presentaciones siguen siendo fichas independientes.

`app/services/restock_catalog.py` recibe un conjunto validado por un adaptador y
lo aplica de forma idempotente por identidad externa dentro de una transacción.
Las fichas locales y el estado de archivado local se conservan. Una ficha ausente
se marca retirada únicamente tras una lectura confirmada como completa. Una
respuesta parcial solo actualiza los productos que incluye. Un error conserva la
copia anterior y registra un mensaje sin detalles del proveedor ni credenciales.

El botón **Sincronizar catálogo**, junto con la fecha y el último error, está en
**Productos → Catálogo Dulce y Salado**. Se habilita al conectar el adaptador real.
La interfaz interna `CatalogSnapshot` es una representación de la copia a aplicar.
El adaptador HTTP, la autenticación, el recorrido completo y el tratamiento de
bajas se definirán con el contrato de Dulce y Salado. Para una segunda etapa,
validar primero la ejecución manual. Con latencia y volumen medidos, evaluar
una ejecución programada en la operación existente de la Raspberry, separada
del ciclo de la cola fiscal y con el mismo bloqueo de sincronización.

## Validación y recuperación

La suite Compose usa datos ficticios y PostgreSQL aislado. Incluye altas, cambios,
vínculos, filtros, duplicados, dos operaciones concurrentes, registro parcial de
pedidos, recepción, cancelación, historial, proyección local y rollback. El
perfil `backup-test` comprueba la restauración de un faltante activo, su proveedor
preferido y dos intentos de pedido, junto con las verificaciones anteriores.

El despliegue y la recuperación de esta revisión siguen el procedimiento específico
de [operación en Raspberry](OPERACION_RASPBERRY.md#faltantes-0022).
