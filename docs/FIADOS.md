# Fiados por persona

Implementación de ARCA-27, ARCA-29 y ajustes ARCA-30 del 21/11/2026, después del análisis DYS-20.
Se usa la opción A: personas, cuenta enfocada, compras y pagos independientes,
saldo global y períodos anteriores. Desplegado en Raspberry el 21/11/2026 a las 02:15 (Buenos Aires), commit de ejecución 52b3e17 y esquema 0020. Se conservaron todos los originales; cinco registros con nombres repetidos siguen visibles para revisión humana. Ver EXECUTION_STATUS.md y Lific ARCA-PLAN-2.

El directorio muestra una tabla con persona, estado, saldo y accesos a su cuenta.
El lápiz de la primera columna abre los datos de la persona. En el detalle de la
cuenta, el lápiz de cada movimiento abre ese movimiento.

## Probar en esta PC

Desde el repositorio, con Docker Desktop iniciado:

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.fiados-dev.yml up --build -d
docker compose -f docker-compose.dev.yml -f docker-compose.fiados-dev.yml exec -e CREDIT_DEMO_SEED=1 fastapi python -m scripts.seed_credit_demo
docker compose -f docker-compose.dev.yml -f docker-compose.fiados-dev.yml exec -e CREDIT_DEMO_SEED=1 fastapi python -m scripts.seed_credit_demo --apply
```

El segundo comando valida sin escribir. El tercero crea ejemplos ficticios de
Marcela, Juan, Ana y Carlos; repetirlo no repite sus movimientos. Se rechaza si
encuentra datos ajenos a esos ejemplos, una DB distinta de desarrollo/pruebas o
integraciones distintas de mock. No borra ni restablece registros.

Abrir **http://localhost:8001/fiados**. El proyecto de Compose se llama
`arca-dys-fiados-dev` y usa `arca-dys-fiados-dev_pg_dev`, separado del desarrollo
anterior y de las pruebas. Solo el proxy publica `127.0.0.1:8001`; la DB y la app
permanecen en red interna. El override sustituye el montaje de la raíz del repo
por código de app/migraciones y el cargador ficticio, sin `.env.prod`, certificados,
respaldos ni JSON privados. Requiere Compose >= 2.24.4 por `!override`, conforme a
la [documentación oficial](https://docs.docker.com/reference/compose-file/merge/#replace-value).

Para detener esta instancia, conservar el volumen:

```powershell
docker compose -f docker-compose.dev.yml -f docker-compose.fiados-dev.yml stop
```

No usar `down --volumes` para detenerla ni aplicar el reset manual H15.
El prototipo público de Sites sigue siendo una simulación separada; este enlace
local permite probar la implementación con PostgreSQL en esta PC. No iniciar
simultáneamente el Compose de desarrollo anterior: ambos reservan el puerto 8001.
Detener una instancia conserva su volumen; no hace falta borrar datos.

## Uso cotidiano

- Buscar en Con deuda, Sin deuda o Todas. Una persona se identifica por ID,
  aunque se corrija su nombre. Referencia opcional para distinguir homónimos.
- Nuevo fiado: seleccionar persona o crearla desde el formulario, ingresar
  importe, fecha y observación opcional. El importe empieza vacío.
- Al escribir `10000`, el campo muestra `10.000`. También admite pegar `10.000`.
  No acepta comas ni fracciones. Importes y saldos se muestran sin decimales.
- Registrar pago: ingresar el monto, revisar persona/fecha/saldo resultante y
  confirmar. Saldar prepara un pago por todo el saldo y vuelve a comprobar la
  versión al confirmar. Un sobrepago se rechaza; no hay saldo a favor en esta versión.
- Al volver a cero se conserva el tramo en Historial. Un nuevo fiado abre otro.
  Las fechas anteriores se conservan sin cambiar el orden de los registros ya
  confirmados. Una fecha futura se rechaza en nuevas compras/pagos.
- El lápiz del movimiento abre importe, fecha y detalle precargados. Corregir
  productos no requiere volver a cargar la compra ni cambia su saldo. Guardar
  conserva una copia interna de antes/después en la misma transacción.
- Eliminar abre una confirmación; Cancelar no escribe. Confirmar marca baja
  lógica, conserva el importe original y lo excluye de saldo/listados/mensajes.
  Editar importes o eliminar recalcula los saldos por secuencia: se rechaza si
  algún punto quedaría con pagos mayores que la deuda, aunque el saldo final
  fuera positivo. Primero revisar los pagos correspondientes. Los períodos
  saldados se recalculan con los movimientos vigentes.
- Los saldos legados incorporados y movimientos con una anulación anterior no
  se editan desde estos controles; su fuente y la relación histórica se conservan.

No se marcan compras individuales como pagadas: los pagos se aplican al saldo de
la persona. No se crean ventas, egresos, cobros MP ni comprobantes fiscales.

## Búsqueda sin saltos del formulario

El servidor normaliza mayúsculas, tildes y espacios, y busca cada término en
cualquier posición de nombre y referencia. `perez`, `PÉREZ` y `PeReZ` encuentran
`Marcela Pérez`; `perez marc` también la encuentra. Los comodines se tratan como
texto, no como SQL. La respuesta está acotada a ocho opciones.

Se sigue el patrón [combobox con selección manual de W3C APG](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/):
input con `aria-autocomplete=list`, `aria-expanded` y `aria-controls`, opciones
`listbox`, foco real en el input y opción activa mediante `aria-activedescendant`.
Flechas recorren, Enter selecciona, Escape cierra sin enviar el formulario y Tab
continúa. El popup se posiciona sobre la interfaz, dentro del diálogo, sin ocupar
altura de documento. Se ajusta al espacio disponible y al viewport del teclado.
Las respuestas viejas se cancelan/ignoran. Escribir un nombre no basta: el servidor
exige un ID seleccionado o una creación explícita.

Los nombres similares generan una advertencia y requieren confirmar que es otra
persona. No hay unicidad por nombre ni fusión automática. Las altas/renombres se
serializan al revisar similitudes para advertir también ante altas simultáneas.

## Persistencia y concurrencia

`0017_credit_accounts` agrega `credit_customers`, `credit_movements` y
`credit_legacy_links`. No modifica revisiones anteriores ni copia/agrupa nombres.
`0018_credit_updates` agrega celular, versión/baja de movimiento y
`credit_movement_changes`. No modifica 0017 ni ninguna revisión previa.

Los importes del diario usan NUMERIC sin coerción de escala, con restricciones
de entero, signo, no cero y rango menor a 10^16 en valor absoluto. Así se rechaza
también una fracción como 1.001 recibida por SQL en vez de redondearla. El servicio
usa Decimal, valida el saldo final y nunca convierte dinero a Float/Number.

Cada compra, pago, anulación y vinculación tiene UUID y huella del payload. El mismo UUID exacto devuelve su
resultado; otro payload es conflicto. Un bloqueo transaccional por UUID serializa
reenvíos. Cada escritura monetaria bloquea la fila de la persona, revalida versión,
recalcula el saldo y agrega una secuencia al crear o conserva la secuencia al corregir.
La corrección de nombre usa versión para rechazar una edición o repetición obsoleta.
Los triggers rechazan DELETE físico y cambios sin control. Cada edición/baja
con versión y comando válidos guarda snapshots JSONB completos antes/después;
esa evidencia y los vínculos siguen siendo inmutables. Se conserva ID, UUID
original, propietario, secuencia, tipo y fecha/hora de creación. No hay cambios
físicos ni reactivación de filas eliminadas. Reenviar una corrección confirmada
devuelve su movimiento; cambiar el payload con el mismo UUID produce conflicto.
La sesión anónima sigue siendo Local; no identifica cuál de los empleados operó.

Las rutas HTTP anteriores de editar/marcar pagado/eliminar no mutan la fuente:
devuelven conflicto para reabrir la cuenta. Sueldos mantiene su contrato existente.
Los GET/formularios completos funcionan sin el diálogo mejorado; el autocompletado
y la agrupación durante la escritura requieren JavaScript.

## Registros anteriores y transición productiva

La migración solo crea estructura. `customer_credits` conserva todos sus valores,
IDs, UUID, marcas de baja, fechas y horas conocidas/desconocidas. El listado avisa
cuántos registros anteriores faltan vincular y muestra su deuda por separado;
no los presenta como cuentas ya conciliadas.

En **Revisar y vincular**, una persona del negocio elige una cuenta o crea una
identidad distinta. Un pendiente genera un saldo anterior incorporado con su
importe y fecha originales; no se lo presenta como una nueva compra reconstruida.
Un pagado se agrega solo al Archivo anterior: no se inventa una compra/pago que
compense ni una fecha desconocida. Una fila eliminada no se vincula ni se reactiva.

La revisión comprueba la huella de todas las columnas originales dentro de un
bloqueo. Conservar el vínculo impide duplicar la incorporación; sus FKs verifican
que la apertura pertenezca a la misma cuenta. La fuente vinculada queda protegida
contra UPDATE/DELETE. Un importe pendiente con centavos se rechaza para conciliarlo;
no se redondea, oculta o traslada silenciosamente. Un histórico pagado con centavos
se conserva sin mostrarlos como un nuevo movimiento entero.

La autorización del 21/11 permite desplegar después del respaldo y ensayo real.
`scripts.transition_credit_legacy` prepara un plan privado, con huellas de todas
las columnas originales, y aplica el conjunto en una transacción. Solo incorpora
nombres exactos normalizados que aparecen una vez; toda repetición queda visible
para revisión humana. No decide si dos filas con el mismo nombre son la misma persona.
Repetir el plan no duplica cuentas ni aperturas; si cambia la fuente se rechaza.
`scripts.verify_credit_transition` contrasta las huellas de todas las tablas y
secuencias anteriores antes/después. Los planes y respaldos reales permanecen en
el SSD de Raspberry; no son fixtures ni se publican en Git.

El ensayo real conservó 21 originales (8 eliminados intactos), vinculó 8 filas y
delegó 5 filas de nombres repetidos a ARCA-35. Deuda: 133.594 incorporada + 70.437
anterior pendiente de revisión = 204.031. Los pagados se archivan sin inventar pagos.
No se usa el reset H15 ni hay auto-deploy por push. El downgrade se rechaza para
no perder el diario: la recuperación requiere respaldo y conciliación de operaciones
posteriores, no borrar tablas nuevas. Ver OPERACION_RASPBERRY.md.

## Verificación

```powershell
docker compose -f docker-compose.test.yml run --build --rm test
docker compose -f docker-compose.test.yml --profile backup-test run --rm backup-test
node tests/credit-money.cjs
git diff --check
```

La suite cubre búsqueda, exactitud y límites, UUID, versiones, pagos parciales,
cancelación, nuevos períodos, anulaciones, concurrencia real con dos conexiones,
rollback antes de commit, pérdida de respuesta después de commit, históricos
sin pérdida ni pagos inventados y contratos anteriores de Sueldos/facturación.
El perfil de respaldo crea bases efímeras propias, restaura movimientos/vínculos
y comprueba saldo, fechas desconocidas y protecciones de historial.
La verificación de navegador se registra separadamente de TestClient.

Resultado local del 20/11/2026: **364 pruebas aprobadas en 139,71 s**, sin omitidas,
con una advertencia conocida de Starlette/httpx. Respaldo custom, checksum y
restauración en 0017 aprobados: saldo 7.500, dos movimientos, vínculo histórico
pagado sin fecha inventada y triggers activos. Prueba de formato/cursor con Node
y análisis sintáctico de ambos archivos JS aprobados. Sin dependencias nuevas.

Navegador real, escritorio 1366×900 y móvil 390×844: alta ficticia, pago parcial,
revisión/confirmación, saldar, nuevo período, anulación, historial, advertencia por
nombre parecido, filtros y búsqueda `perez`. El popup mantiene la posición del
importe (desplazamiento medido: 0 px) y el foco de teclado en el buscador; no hay
desborde horizontal en las vistas revisadas. Escritura 10.000/100.000, pegado con
puntos, rechazo de comas y borrado junto al separador comprobados. La vinculación
visual de dos originales ficticios mantuvo su contenido y la fecha de pago desconocida.
Sin errores de consola observados en la cuenta revisada.

La instancia queda encendida con las cuatro cuentas del cargador y una quinta
cuenta ficticia usada para verificar la interfaz, saldada y con historial. Los
dos originales ficticios de esa cuenta ya están vinculados. El cargador protegido
rechazará volver a aplicarse ahora que hay registros ajenos a sus cuatro ejemplos;
eso no afecta al uso ni exige limpiar la DB. Capturas locales en
`artifacts/fiados-dev/`, ignoradas por Git.

La imagen local `arca-dys-fiados-runtime`, construida con target production, aprobó
`scripts.smoke_runtime` en la red interna test: servidor HTTP, Fiados nuevo,
Gestión, Sueldos, Resumen, sesión/CSRF, worker y PDF simulado. La DB efímera propia
se retiró al terminar. No se contactaron proveedores externos.

La verificación anterior documenta la etapa de desarrollo del 20/11. El 21/11 se
ensayó el respaldo real y la imagen ARM64 nativa; la evidencia del despliegue queda
en EXECUTION_STATUS.md. ARCA-28 conserva la aceptación por la usuaria y la prueba
en teléfono físico/teclado virtual; ARCA-35 conserva la revisión de identidades.

## Celular y WhatsApp · ARCA-29

El lápiz junto al nombre edita nombre, referencia y celular opcional. Por decisión
ARCA-30, todos los clientes son argentinos: ingresar solo código de área y número,
10 dígitos, sin 0 inicial, 15, espacios ni signos. La UI bloquea caracteres/pegados
inválidos y el servidor valida ASCII y longitud. La ficha guarda solo esos 10
dígitos; el prefijo 549 se agrega únicamente al preparar el destino de WhatsApp.

Enviar detalle por WhatsApp abre una revisión local del período actual o historial
completo, con nombre, fechas, tipo, importes enteros, observaciones completas y
saldo actual. Las bajas quedan excluidas; se usan las correcciones vigentes. En
historial completo los pagados legados aparecen como archivo, sin pagos inventados.
El snapshot bloquea brevemente la cuenta para no mezclar operaciones simultáneas.
Los textos largos se dividen en partes numeradas, sin omitir productos/filas.

Abrir WhatsApp usa [Click to chat oficial](https://faq.whatsapp.com/5913398998672934),
`https://wa.me/numero?text=texto_codificado`, con saltos y negritas de WhatsApp.
No hay API, token, envío automático ni contacto externo al generar la revisión.
El selector de período actual/historial completo actualiza contenido y enlaces
automáticamente, sin recargar el documento, perder foco o mover el scroll. Se
cancelan/descartan respuestas viejas y se deshabilita la apertura del chat mientras
se actualiza. Si falla, se conserva el mensaje anterior y vuelve el selector a su
valor. No se consulta cuando la selección coincide con el contenido ya mostrado.
El botón con icono y el destino están encima del mensaje; si falta celular, se
ofrece agregarlo con aviso rojo en ese lugar. No se comprueba que el número tenga
cuenta de WhatsApp activa ni se envía automáticamente.

El saldo ahora agrupa etiqueta/importe/explicación a la izquierda y estado aparte,
sin borde fucsia. Nuevo fiado y Crear persona están juntos sobre la tarjeta; el
buscador es su primer contenido. Breadcrumb compartido en las páginas que tenían
retornos: región nav, lista, separadores y página actual según
[W3C APG](https://www.w3.org/WAI/ARIA/apg/patterns/breadcrumb/).

Validación ARCA-29: **380 pruebas completas aprobadas, 149,91 s**, una advertencia
conocida y sin omitidas. Restauración 0018 aprobada con saldo 7.500, fuente legada
intacta y una corrección antes/después protegida. Desarrollo migrado después de
respaldo local en `artifacts/fiados-dev/before-0018.dump`, sin borrar datos previos.
Navegador: creación ficticia, edición de productos conservando 45.000, celular,
mensaje/destino codificados, cancelar y confirmar eliminación (46.000 → 45.000),
listado y breadcrumbs de Fiados, Proveedores y Factura por importe. Escritorio
1366×900 y móvil 390×844, sin desborde de documento en las vistas revisadas.
Capturas `account-updated.jpg`, `whatsapp-preview.jpg` y `directory-updated-*.jpg`
en la carpeta local de artefactos. No se abrió un chat ni se envió un mensaje real;
pendiente probar la apertura en el WhatsApp/teléfono de la usuaria (ARCA-28).

## Reportes, avisos y celular local · ARCA-30 · 21/11/2026

0019_credit_local_phone convierte solo el formato anterior inequívoco 549+10
dígitos y conserva los números ya locales/vacíos. Incrementa la versión al convertir
para rechazar formularios viejos y agrega CHECK del formato nacional. Un teléfono
anterior de otro formato aborta la migración sin alterar filas: requiere revisión,
no se borra ni se interpreta como argentino. Desarrollo respaldado antes de aplicar
en `artifacts/fiados-dev/before-0019.dump`. No se modificaron revisiones anteriores.

Período actual, historial por períodos y detalle de un período saldado usan tablas.
La primera columna del detalle tiene el lápiz; siguen fecha, movimiento, productos
y monto. La última carga aparece primero por secuencia registrada, aunque su fecha
comercial sea anterior. Los cálculos mantienen secuencia ascendente y saldo exacto.
Se conservan en DB las horas/secuencias: solo se retiraron de la presentación,
junto al saldo acumulado de cada fila. Eliminar se ofrece dentro de Editar,
manteniendo su confirmación y sin reactivar bajas. WhatsApp con icono está en la
cabecera del reporte; deuda en rojo, saldada en verde. En móvil la tabla desplaza
horizontalmente dentro de su contenedor, con el lápiz fijo y sin desbordar la página.

Las notificaciones de estado/error de toda la aplicación se presentan en un
contenedor flotante centrado arriba, con cruz y 2.000 ms de duración. Se usa un
popover manual para estar también encima de un diálogo nativo, sin robar el foco.
Los avisos estructurales, controles de confirmación y el aviso contextual de falta
de celular permanecen dentro de su sección; no son notificaciones transitorias.
Los reportes existentes conservan su documento/foco/scroll al actualizar filtros.

Navegador: celular solo numérico, espacios bloqueados, aviso por encima del modal,
cierre por cruz y desaparición automática (aproximadamente 1.904 ms desde el retorno
del POST, consistente con 2.000 ms desde la creación del aviso). Detalle automático
con cambios rápidos y foco/scroll conservados; falta de celular roja arriba. Reporte
con carga retroactiva primero, eliminación dentro de edición, historial y estados.
Escritorio 1366×900 y móvil 390×844: documento sin desborde, tabla con scroll interno.
Sin errores de consola observados ni apertura/envío a WhatsApp. Capturas locales:
`report-columns-desktop.jpg`, `report-columns-mobile.jpg`, `whatsapp-simplified.jpg`.


Validación final ARCA-30: **390 passed, 152,66 s**, una advertencia conocida y sin
omitidas. Las pruebas de integración cubren teléfono nacional/URL 549 una sola
vez, conversión de datos previos, bloqueo sin pérdida ante formatos ambiguos,
restricción SQL, orden de carga retroactiva, períodos saldados y contenido de
WhatsApp. Las comprobaciones anteriores de conteos/históricos se adaptaron al
nuevo reporte sin retirar sus garantías de saldo y conservación.

Backup-test 0019 aprobado con checksum/restauración, celular nacional conservado,
saldo 7.500, dos movimientos y evidencia inmutable de correcciones. Imagen target
production y smoke HTTP mock/red interna/DB efímera propia aprobados. Sintaxis de
credits.js, notifications.js y reports.js y formato/cursor de dinero con Node
aprobados. git diff --check y enlaces locales de documentación revisados.
Sin cambios de dependencias ni ARM64. Pendiente ARCA-28: teléfono físico y apertura
real de WhatsApp; no se abrió chat ni se envió mensaje durante estas verificaciones.


## Ajustes finales · ARCA-31

Nombre guardado con mayúscula inicial en cada palabra, conservando tildes. 0020
normaliza también las fichas ya creadas sin fusionar IDs ni modificar originales.
Nombre, referencia entre paréntesis y lápiz comparten cabecera; el celular solo
aparece al editar o preparar WhatsApp. En el directorio se conserva el importe
sin el rótulo Saldo pendiente. Cancelar usa el mismo estilo a la izquierda; guardar
y eliminar quedan juntos a la derecha. Gestión alinea título y acciones en desktop;
Sueldos coloca Editar primero. El mensaje empieza con 🧁 y 📋, conserva fechas,
observaciones y montos exactos, y requiere el envío manual en WhatsApp.


## Legibilidad en revisión · ARCA-36 · solo desarrollo

La revisión del 21/11 aumenta el texto principal y los botones de 14 a 16 px,
con encabezados de tabla más marcados y textos secundarios más oscuros dentro de
la misma paleta. Los botones principales tienen al menos 48 px de alto.
La ubicación final de Total fiado es la fila de filtros, alineado a la derecha,
sin fondo ni borde. Etiqueta e importe usan 30 px, por ajuste posterior del usuario. En móvil pasa
a la línea siguiente si no entra y conserva la alineación derecha, sin scroll.
No cambia el cálculo ni incorpora otros saldos.

Disponible en http://localhost:8001/fiados para revisión de la usuaria. Esta
revisión no se desplegó en Raspberry. Navegador real: Fiados, Gestión, Sueldos,
Resumen y Facturación; móvil de 390 y 320 px, sin desborde del documento ni del
modal de edición. Guardar y Eliminar permanecen juntos al ampliar el texto.
396 pruebas completas aprobadas en 155,28 s, sin omitidas; una advertencia conocida
Starlette/httpx. Captura: artifacts/fiados-dev/readability-directory-desktop.jpg.


Refinamientos ARCA-37/38, también solo desarrollo: saldo integrado a los filtros,
sin barras de desplazamiento en el importe. La cantidad de
personas va junto a Todas y ambos permanecen juntos al pasar a móvil. El directorio
aprovecha el ancho de la página: hasta tres tarjetas por fila cuando el espacio
permite leerlas cómodamente, dos en tamaños intermedios y una en móvil. Los saldos
y botones de las tarjetas se alinean aunque las referencias ocupen varias líneas.
Los filtros y sus cálculos no cambian.


ARCA-38 se verificó en navegador de escritorio y anchos móviles de 390 y 320 px:
saldo sin fondo/borde, fuente de 16 px, alineación derecha y documento sin desborde.
Viewport restaurado al terminar. Capturas actuales en
artifacts/fiados-dev/filter-inline-total-desktop.jpg y filter-inline-total-mobile.jpg.
La prueba física con la usuaria sigue pendiente en ARCA-28; no se desplegó esta
revisión ni se publicó un commit.


## CRUD uniforme · ARCA-39

El listado dice Total fiado. Las altas y ediciones usan Guardar; la eliminación
usa Eliminar con relleno rojo, incluida la confirmación. Cancelar queda a la
izquierda y Guardar/Eliminar juntos a la derecha. La revisión de pagos conserva
su paso previo y los controles de versión/confirmación. En pantallas pequeñas las
tres acciones usan el mismo diseño compartido con Gestión, Sueldos y Proveedores.
El usuario autorizó trasladar también los ajustes visuales previos a Raspberry;
la evidencia del despliegue está en EXECUTION_STATUS.md y ARCA-PLAN-3.


Todos estos ajustes de legibilidad/directorio y CRUD fueron autorizados y
publicados en Raspberry con5f21686, esquema0021. Los párrafos anteriores registran
su revisión previa de desarrollo. Total fiado usa30px, sin fondo, junto a los
filtros; se conservan contador junto a Todas y tarjetas3/2/1 según ancho.
