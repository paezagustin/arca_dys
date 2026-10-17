# ARCA DYS: instrucciones de trabajo

## Propósito y alcance vigente
Aplicación personal para una usuaria: facturar fácilmente y controlar un negocio
en Raspberry Pi 5. Usar FastAPI, SQLAlchemy, Jinja2, PostgreSQL 17 y Docker Compose.
Leer README, docs/ALCANCE.md, docs/ROADMAP.md y docs/EXECUTION_STATUS.md al retomar.
Las correcciones humanas del alcance prevalecen sobre propuestas anteriores.

## Preparación de despliegue H15 (prevalece sobre la limpieza total propuesta)
- El usuario confirmó: conservar control de facturación y limpiar el resto de Gestión.
  Solicita comandos para ejecutar ÉL posteriormente en la Raspberry, no ejecución
  productiva por el agente. No acceder ni desplegar allí en esta sesión.
- Reutilizar /mnt/datos/docker/arca_dys y el cluster PostgreSQL existente. Guardar
  respaldo/configuración/imagen, ensayar en copia, migrar a head y recién limpiar.
- scripts/reset-business-data.sql es una operación MANUAL puntual de datos, no una
  migración ni parte del arranque. Solo siete tablas de Gestión/importación/Sueldos/
  Fiados, con RESTRICT, sin CASCADE y transacción. Nunca toda la base/volumen.
- Conservar pagos y marca facturado, facturas/CAE/respuestas/vínculos, solicitudes y
  reservas fiscales (incluidas inciertas), inbox/historial MP, usuarios y emisor.
- No cambiar cuenta/token/dominio NGROK, app/cuenta MP, CUIT/punto/certificados.
  El override opcional NGROK fija la URL existente; no sustituye un agente externo
  ni migra sus políticas automáticamente. No crear un segundo túnel del mismo dominio.
- Documentar tecnologías, configuración y comandos exactos con límites comprobados.
  Probar el SQL SOLO en PostgreSQL descartable; no ejecutar la limpieza local otra vez.

## Carga inicial JSON y menú H14 (prevalece sobre el antiguo módulo Excel)
- Menú móvil: icono sencillo de tres líneas junto al nombre de la sección activa.
  Sin flecha. El icono queda oculto en escritorio junto con el summary móvil.
- Eliminar el módulo de importación Excel, sus rutas, pantallas, lectores y scripts.
  Conservar la exportación Excel de Resumen. No volver a crear importadores web.
- Carga puntual por consola: scripts/import_business_json.py, tres JSON privados,
  validación sin escrituras por defecto, --apply transaccional, conciliación por
  mes/tipo y repetición idempotente. No conectar ARCA/MP ni iniciar web/worker.
- Proveedores por clave explícita normalizada; no fusionar por similitud. Ventas
  históricas con total y desglose NULL; no inventar efectivo/MP, sueldos ni fiados.
- Guardar originales y normalizados en data/private/, ignorados en Git y Docker.
  Los datos reales no son fixtures. La Raspberry recibe esos archivos por separado.
- Mantener tablas legadas de importación y migraciones publicadas por integridad;
  no borrar registros previos de producción al retirar las funciones Excel.
- H14 autorizó vaciar SOLO la DB local dev para esa carga, con respaldo. H15 agrega
  limpieza manual futura de Gestión conservando control fiscal. No repetir el
  vaciado total ni ejecutar operaciones productivas desde esta sesión.

## Ajustes H12 de formularios y navegación
- Altas de montos manuales vacías con placeholder 0,00; conservar valores guardados
  al editar, importes de revisión y configuración. MP sigue sugiriendo el total
  local cuando es positivo; si no hay cobros, queda vacío. No imponer cero inicial.
- En ventas, un componente vacío vale cero si se completó el otro. Ambos vacíos
  se rechazan; cero explícito sigue siendo una venta válida. Total calculado en servidor.
- Marca visible Dulce y Salado, logo centrado y nombre debajo. Menú móvil nativo
  desplegable, cerrado al entrar; escritorio abierto, incluso al cambiar de tamaño.
- Administración y controles de sesión al final, justo antes de ARCA DYS.
- El desplegable móvil no lleva flecha; su texto es el nombre de la sección
  marcada con aria-current. Usar Menú solo si no existe una sección activa.

## Ampliación H10 solicitada el 16/10/2026 (prevalece sobre exclusiones anteriores)
- Ventas: fecha, efectivo y MP editable sugerido desde cobros locales aprobados sin
  facturar de esa fecha. Total calculado en servidor. Guardar desglose, no recalcular
  cierres guardados cuando después se facture. Históricos sin desglose no se inventan.
- Sueldos: fecha, empleado (ENUM PostgreSQL Francisco/Juan Cruz), monto y tipo
  (ENUM efectivo/mercado pago, default mercado pago). Reporte del mes actual filtrable.
  Sueldos reducen Ganancia y se muestran por empleado en Resumen, sin duplicar egresos.
- Fiados: nombre, monto, observación, fecha y pagó sí/no (no por defecto), listado y
  marcado de pago. Fecha de pago automática al pasar de No a Sí (hoy en Buenos Aires),
  conservada al editar y vacía al volver a No. No inventar fechas históricas. Registro independiente, sin crear ventas ni alterar la caja automática.
- Sueldos y Fiados accesibles sin login para uso local, en el menú junto a las otras
  secciones públicas. Mantener CSRF, idempotencia y edición sin motivos/historial.
- Centrar cabeceras y valores de tablas. Sin nuevos campos comerciales innecesarios.
- La revisión 0011_sales_payroll_credits implementa H10; una vez publicada,
  las revisiones 0001-0012 son inmutables. Agregar otra para cambios posteriores.
  0012_credit_paid_date agrega la fecha automática de pago de Fiados solicitada
  después de H10; conserva sin fecha los pagos anteriores desconocidos.

## Simplificación solicitada el 16/10/2026 (prevalece sobre H0-H8)
- Acceso local sin login a Facturación, Gestión y Resumen, incluidos sus formularios.
  Sesión anónima individual y CSRF; únicamente admin ve y usa los demás módulos.
- Venta diaria: fecha editable (hoy por defecto) e importe. Egreso: fecha, importe,
  tipo En Blanco/En Negro, proveedor con búsqueda y descripción opcional.
- Sin otros ingresos, medios, categorías adicionales, estados editables, motivos
  de corrección ni historiales de cambios. Conservar historial de solicitudes fiscales,
  snapshots de comprobantes y metadatos de importaciones anteriores por integridad.
- Resumen: Ventas, Egresos en blanco, Egresos en negro, Total Egresos y Ganancia
  (ventas menos egresos). Exportación con las seis columnas del Excel original.
- Ayudas mediante diálogo al pulsar un icono, sin subtítulos explicativos permanentes.
- Proveedores: la carga inicial usa los JSON corregidos entregados por el usuario.
  Mantener nombres ambiguos separados. No publicar datos reales.
- Referencia visual: PDF de Figma; logo completo, barra lateral, azul/cian/rosa.

- Mercado Pago: facturar el importe COMPLETO de cada pago, con facturado sí/no.
- Conservar FACTURAR TODO y FACTURAR SELECCIONADOS; TODO abarca el filtro completo,
  no solo la página actual. Definir un conjunto estable de IDs al confirmar.
- Nueva factura por importe: INDEPENDIENTE de Mercado Pago. No imputaciones
  parciales, saldos de pagos ni métricas de pendientes en el dashboard.
- Ventas diarias: carga MANUAL del total vendido, incluyendo efectivo y MP.
  Facturas y cobros no crean ni modifican esa venta. No imponer igualdad entre ellos.
- Proveedores: datos básicos y selección al registrar pagos. Sin cuentas corrientes,
  compras a crédito, vencimientos ni pagos parciales de deuda en este alcance.
- JSON: proveedores, ventas totales y egresos. No importar bloques manuales del
  dashboard ni sueldos/adelantos del Excel; registro manual de Sueldos habilitado
  por H10. Exportación Excel conservada. No inventar datos históricos.
- Factura C (tipo 11) correcta. Corregir plantilla, no cambiar de tipo fiscal.
  Conservar condición de venta fija y distribución cotillón/repostería 50/50.
  La condición fiscal exacta del emisor debe configurarse, no inferirse de que no es RI.
- Límites mínimos/máximos centralizados; sus valores iniciales conservan 1000/2000000.
  Agregar edición administrativa en su etapa. No presentarlos como límites legales.

## Autonomía y publicación
El usuario autorizó cambios, dependencias necesarias, pruebas locales, commits y
push directo a GitHub sin revisión ni aprobación por tarea. Continuar los pasos
ordinarios del hito solicitado; registrar decisiones y evidencia. Publicar solo
cambios comprobados y nunca usar force-push ni descartar cambios ajenos.
El roadmap es la secuencia de trabajo, no evidencia de funcionalidades completadas.
No modificar configuración global de Codex ni intentar anular su sandbox.
No desplegar en la Raspberry como efecto de un push. No crear auto-deploy.
No rotar claves ni reescribir historial como parte de este trabajo: el usuario
hará esa rotación después. No introducir nuevas claves ni datos privados en Git.

## Límite obligatorio de pruebas
NUNCA facturar realmente en ARCA, cobrar, devolver dinero o modificar la aplicación
productiva de Mercado Pago para verificar código. Tampoco se permiten facturas
"de importe pequeño" en producción. Usar simulación por defecto, datos ficticios,
PostgreSQL descartable y red Docker interna. No montar .env.prod ni certificados
reales en desarrollo, test o CI. La suite comprueba su DB de destino antes de limpiar.
Homologación y sandbox, si se incorporan, serán perfiles explícitos separados,
con credenciales propias y sin habilitar destinos productivos.
Una importación de módulos, un seed o un arranque no debe contactar proveedores.
Ante timeout fiscal, conservar resultado incierto y consultar antes de reemitir.
Un error de PDF jamás justifica volver a emitir una factura autorizada.

## Arquitectura y datos
Monolito modular. Rutas HTTP delgadas; casos de uso sin HTML; adaptadores externos
sustituibles. Mantener PostgreSQL compartido. Agregar procesos o infraestructura
solo con una necesidad comprobada. No reemplazar el stack ni sumar SPA/ERP.
Cambiar esquema exclusivamente con migraciones Alembic versionadas y revisadas.
No editar una migración ya publicada ni el baseline congelado. Las revisiones
0001-0012 se conservan; cualquier cambio posterior agrega otra migración.
No borrar columnas por ausencia de INSERT en un dump: comprobar referencias y datos.
El usuario confirmó sin uso los campos de resolución de error_logs, logs_invoice
y payments.id_arca. Se retiran con 0002_cleanup, que rechaza información inesperada.
resolution_by no existe en el esquema entregado; no crear una columna para retirarla.
Conservar invoices.raw_afip_response y guardar el resultado completo de emisión
devuelto por el SDK, sin añadir la solicitud ni credenciales. No inventar respuestas
históricas ni consultar ARCA en producción para rellenarlas durante el desarrollo.
Antes de adoptar/migrar producción: backup lógico y prueba en copia. El respaldo
inicial se almacena en el mismo SSD; CRON y copia externa quedan para el usuario.
No ejecutar DROP/TRUNCATE ni importar fixtures sobre la base productiva desde el
agente. El único reset manual futuro autorizado es el SQL restringido H15 que el
usuario ejecutará luego según la guía y con respaldo; no borrado fiscal/cluster.
Los retiros de esquema autorizados solo se aplican mediante su migración probada,
durante una actualización coordinada con backup; esta sesión no despliega en Raspberry.
Conservar originales privados fuera de Git; hashes y recibo de carga JSON trazables.
Los metadatos Excel anteriores quedan sin rutas de lectura/escritura ni pantallas.
Dinero nuevo: Decimal/NUMERIC. Migrar Float heredado en una tarea con conciliación.
Idempotencia basada en identidad externa, nunca en igualdad de importes.
Cambios de estado de MP no generan documentos fiscales automáticamente.

## Verificaciones y documentación
Ejecutar `docker compose -f docker-compose.test.yml run --build --rm test`.
Para respaldo/restauración, ejecutar también el perfil backup-test documentado.
Ejecutar `git diff --check`, revisar archivos a publicar y excluir secretos/datos.
Al cambiar dependencias, actualizar requirements.in y su resolución fijada en
requirements.txt; ejecutar pip check/audit y las pruebas afectadas, incluyendo ARM
cuando cambien paquetes con binarios. Consultar docs/OPERACION_RASPBERRY.md.
Pruebas críticas: formularios cero/uno/varios, duplicados, concurrencia, resultado
ARCA incierto, fallo DB posterior al CAE, PDF sin reemisión, fechas, filtros, importes,
permisos, migraciones sin pérdida, carga JSON atómica/repetida y exportación Excel.
Verificar UI en navegador cuando cambie un flujo; no llamar validación visual a
TestClient ni a una inspección HTML. No declarar una tarea validada con tests omitidos.
Actualizar docs/EXECUTION_STATUS.md, roadmap y guías afectadas por cada hito.
Informar qué se implementó, qué se probó, qué no se probó y el commit publicado.
