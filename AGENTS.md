# ARCA DYS: instrucciones de trabajo

## Propósito y alcance vigente
Aplicación personal para una usuaria: facturar fácilmente y controlar un negocio
en Raspberry Pi 5. Usar FastAPI, SQLAlchemy, Jinja2, PostgreSQL 17 y Docker Compose.
Leer README, docs/ALCANCE.md, docs/ROADMAP.md y docs/EXECUTION_STATUS.md al retomar.
Las correcciones humanas del alcance prevalecen sobre propuestas anteriores.

- Mercado Pago: facturar el importe COMPLETO de cada pago, con facturado sí/no.
- Conservar FACTURAR TODO y FACTURAR SELECCIONADOS; TODO abarca el filtro completo,
  no solo la página actual. Definir un conjunto estable de IDs al confirmar.
- Nueva factura por importe: INDEPENDIENTE de Mercado Pago. No imputaciones
  parciales, saldos de pagos ni métricas de pendientes en el dashboard.
- Ventas diarias: carga MANUAL del total vendido, incluyendo efectivo y MP.
  Facturas y cobros no crean ni modifican esa venta. No imponer igualdad entre ellos.
- Proveedores: datos básicos y selección al registrar pagos. Sin cuentas corrientes,
  compras a crédito, vencimientos ni pagos parciales de deuda en este alcance.
- Excel: ingresos/egresos y dashboard, incluidos datos manuales históricos.
  Sueldos/adelantos excluidos. No inventar datos ni corregir ambiguos sin trazabilidad.
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
No editar una migración ya publicada ni el baseline congelado.
No borrar columnas por ausencia de INSERT en un dump: comprobar referencias y datos.
Antes de adoptar/migrar producción: backup lógico y prueba en copia. El respaldo
inicial se almacena en el mismo SSD; CRON y copia externa quedan para el usuario.
No ejecutar DROP/TRUNCATE ni importar fixtures sobre la base productiva.
Conservar originales del Excel fuera de Git; lote/hoja/fila y problemas trazables.
Dinero nuevo: Decimal/NUMERIC. Migrar Float heredado en una tarea con conciliación.
Idempotencia basada en identidad externa, nunca en igualdad de importes.
Cambios de estado de MP no generan documentos fiscales automáticamente.

## Verificaciones y documentación
Ejecutar `docker compose -f docker-compose.test.yml run --build --rm test`.
Para respaldo/restauración, ejecutar también el perfil backup-test documentado.
Ejecutar `git diff --check`, revisar archivos a publicar y excluir secretos/datos.
Pruebas críticas: formularios cero/uno/varios, duplicados, concurrencia, resultado
ARCA incierto, fallo DB posterior al CAE, PDF sin reemisión, fechas, filtros, importes,
permisos, migraciones sin pérdida, importación repetida y conciliación del Excel.
Verificar UI en navegador cuando cambie un flujo; no llamar validación visual a
TestClient ni a una inspección HTML. No declarar una tarea validada con tests omitidos.
Actualizar docs/EXECUTION_STATUS.md, roadmap y guías afectadas por cada hito.
Informar qué se implementó, qué se probó, qué no se probó y el commit publicado.
