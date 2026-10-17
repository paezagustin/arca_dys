# Transición de pagos MP históricos repetidos

Este procedimiento es MANUAL, con web y workers detenidos, backup comprobado y
primero sobre `restore_check`. No inicia la aplicación, no factura ni consulta MP
o ARCA. No elimina pagos ni reasigna vínculos. Los ensayos del repositorio son
sintéticos: no sustituyen la prueba de su respaldo real.

## Decisión y compatibilidad

Se conservan las 3876 filas originales de payments con sus IDs, las 3625 marcas
registered_arca, las 181 facturas y los 3624 vínculos. Las diferencias de JSON,
estado, fecha o marca entre duplicados NO permiten decidir automáticamente qué
fila representa el pago. Tampoco se infiere una factura a partir del importe.
Los 40 grupos/88 filas quedan protegidos de UPDATE/DELETE y excluidos de cualquier
nueva facturación, incluidos los miembros sin marca o vínculo. No se crean los
vínculos faltantes ni se modifica registered_arca para igualar cantidades.

`0013_mp_identity`, posterior a las migraciones publicadas, crea:

- mp_payment_identities: PK por ID externo. Una identidad no repetida apunta al
  mismo ID interno existente; un grupo repetido queda bloqueado, sin elegir representante.
- mp_legacy_payment_snapshots: copia completa de cada pago al migrar, antes de
  futuras notificaciones. La auditoría monetaria publicada conserva el Float original.
- mp_legacy_transitions: recibo del puente, revisión de origen/destino, conteos,
  huellas SHA256 y secuencias, sin imprimir JSON ni identidades externas.
- Evidencia adicional en mp_events.resource_responses (historial por intento,
  fecha, resultado y respuestas, sin reemplazar intentos anteriores) y
  payment_changes.previous_data.
  No se inventa evidencia anterior ni se completa raw_afip_response histórico vacío.

Un trigger registra cada INSERT de payments en la PK de identidades en la misma
transacción y rechaza IDs existentes, también con inserciones concurrentes.
Otro impide cambiar IDs externos o modificar/eliminar miembros de grupos bloqueados.
El inbox usa esa identidad, no un primer resultado arbitrario entre duplicados.
Una entrega directa de un ID bloqueado queda en conciliación pendiente sin consultar
MP; si una orden devuelve ese ID, se conserva su respuesta y se omite la actualización.
El resto de la orden puede procesarse. No se factura desde el webhook.

Las revisiones 0001-0012 y el baseline NO cambian. El upgrade ordinario sigue
rechazando duplicados en 0004; una revisión posterior sola no puede evitar ese rechazo.
Por eso `python -m app.manage migrate-legacy-mp` implementa un puente versionado
en migrations/mp_legacy_bridge.py, solo desde 0001_legacy, 0002_cleanup o 0003_billing:

1. Bloquea tablas fiscales, toma conteos/huellas/secuencias y ejecuta las revisiones
   originales hasta 0003. Rechaza drift de esquema y solicitudes fiscales activas.
2. Crea el contrato MP de 0004 **salvo** su índice único incompatible. El índice
   histórico sigue no único. Compara el esquema completo con ese contrato explícito.
3. Solo entonces registra internamente 0004 y ejecuta las revisiones originales
   0005-0012 y la nueva 0013. Verifica esquema final, identidades y dos triggers.
4. Compara nuevamente filas originales, controles fiscales, cantidades y secuencias,
   incluyendo los textos monetarios originales contra money_migration_audit.
   Si todo coincide, guarda el recibo y confirma una única transacción PostgreSQL.

Un fallo revierte el DDL y el versionado completo del puente. No se deja una base
visible en 0004 con duplicados. **No ejecutar alembic stamp manual**, no retirar
restricciones ni ejecutar solamente la parte DDL de este módulo. El comando está
fijado al head 0013_mp_identity y exige revisión de compatibilidad ante otro head.
Una instalación ya versionada desde 0004, sin duplicados, utiliza `alembic upgrade head`
normalmente. Una base sin duplicados desde 0001-0003 también usa el upgrade normal.
No ejecutar código anterior contra el nuevo esquema ni hacer downgrade: una
recuperación exige backup restaurado en otra DB y cambio coordinado con la imagen.

El puente mantiene bloqueos exclusivos hasta confirmar: requiere la ventana con
web/workers detenidos. Un lock_timeout de 5s lo cancela si otra sesión ocupa las
tablas; revisar esa sesión antes de repetir. Los snapshots requieren espacio
adicional: comprobar capacidad del SSD y del tmpfs de ensayo (1 GB en la guía).
Si falta espacio, ampliar solo el ensayo o preparar capacidad; no podar evidencia.
El tiempo y consumo físico en esta Raspberry siguen sin comprobarse.

## 1. Preparación y controles de solo lectura

Conservar las variables y funciones de [OPERACION_RASPBERRY.md](OPERACION_RASPBERRY.md):
MAINT_DIR, DEPLOY_IMAGE, copycmd, maintenance, PG_CONTAINER, PG_USER y PG_DB.
Actualizar por fast-forward y reconstruir la imagen con el código de esta entrega.
No reemplazar configuración, tokens, dominio ni certificados. No recrear la DB real.

Si `restore_check` ya fue restaurada y adoptada, NO restaurar encima ni volver a adoptar.
Si el intento de upgrade falló, consultar la revisión efectiva: se aceptan 0001,
0002 y 0003. Otro estado exige detenerse y revisar.

```sh
copycmd alembic current
copycmd python -m app.manage audit-mp-legacy > "$MAINT_DIR/restore-mp.before.json"
cat "$MAINT_DIR/restore-mp.before.json"
```

audit-mp-legacy abre una transacción REPEATABLE READ READ ONLY. Devuelve cantidades,
huellas y secuencias; no nombres, IDs MP, importes individuales ni cuerpos JSON.
Para este respaldo se esperan payments=3876, registered=3625, invoices=181,
links=3624, errors=175, duplicate_groups=40, duplicate_rows=88 y additional_rows=48.
Una cantidad diferente se investiga antes de continuar: no forzar esos números.

Estas consultas opcionales son estrictamente de lectura y solo muestran agregados:

```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
WITH groups AS (
    SELECT id_payment_mp FROM payments GROUP BY id_payment_mp HAVING count(*) > 1
)
SELECT count(DISTINCT p.id) AS filas_repetidas,
       count(DISTINCT p.id) FILTER (WHERE p.registered_arca) AS marcadas_facturadas,
       count(l.id) AS vinculos, count(DISTINCT l.invoice_id) AS facturas_distintas
FROM payments p JOIN groups USING (id_payment_mp)
LEFT JOIN payment_invoice l ON l.payment_id=p.id;

SELECT count(*) AS grupos_con_mas_de_una_factura FROM (
    SELECT p.id_payment_mp FROM payments p
    JOIN payment_invoice l ON l.payment_id=p.id
    GROUP BY p.id_payment_mp HAVING count(DISTINCT l.invoice_id)>1
) g;

SELECT count(*) FILTER (WHERE monts>1) AS importes_distintos,
       count(*) FILTER (WHERE statuses>1) AS estados_distintos,
       count(*) FILTER (WHERE dates>1) AS fechas_distintas,
       count(*) FILTER (WHERE flags>1) AS marcas_distintas,
       count(*) FILTER (WHERE raws>1) AS json_distintos
FROM (
    SELECT count(DISTINCT jsonb_build_array(mont)) AS monts,
           count(DISTINCT jsonb_build_array(status)) AS statuses,
           count(DISTINCT jsonb_build_array(date_approved)) AS dates,
           count(DISTINCT jsonb_build_array(registered_arca)) AS flags,
           count(DISTINCT jsonb_build_array(raw_json::text)) AS raws
    FROM payments GROUP BY id_payment_mp HAVING count(*)>1
) g;
COMMIT;
```

Ejecutarlas únicamente contra el destino confirmado (primero restore_check).
Se esperan 88/74/74/31, cero grupos con más de una factura y diferencias 0/1/1/5/29.
La comparación JSON textual también detecta diferencias de representación: no
justifica sobrescribir una fila. No hace falta enviar datos individuales para
usar esta estrategia conservadora, ya que todos los grupos repetidos se bloquean.

## 2. Ensayo de la transición en restore_check

La función copycmd de la guía usa la red del contenedor aislado, la DB restore_check,
integraciones mock y ninguna credencial/certificado productivo. No iniciar web/worker
con esta copia del respaldo, ni siquiera después de migrar.

```sh
copycmd python -m app.manage migrate-legacy-mp > "$MAINT_DIR/restore-mp.transition.json"
copycmd alembic current
copycmd python -m app.manage check-mp-identities
copycmd python -m app.manage audit-mp-legacy > "$MAINT_DIR/restore-mp.after.json"
diff -u "$MAINT_DIR/restore-mp.before.json" "$MAINT_DIR/restore-mp.after.json"
```

Cada comando debe finalizar sin error; ante un fallo detenerse, no continuar con
los siguientes. Head esperado **0013_mp_identity**. El diff debe estar vacío,
incluidas huellas y secuencias. check-mp-identities debe mostrar invalid_groups=0,
protected_triggers=2, blocked_groups=40 y legacy_snapshots=3876 para este respaldo.
Habrá 3828 identidades: 3788 apuntan a filas no repetidas y 40 quedan bloqueadas.
Las 88 filas originales siguen en payments y sus vínculos conservan los mismos IDs.

El recibo permite repetir el comando sin escrituras mientras la DB permanezca
idéntica y detenida; si cambió, se rechaza esa repetición. No es un proceso para
ejecutar con cada despliegue. La limpieza de Gestión es otra operación, no parte
del puente. Solo después de todos los controles, volver al ensayo de esa limpieza
en la guía; scripts/reset-business-data.sql ahora exige 0013_mp_identity y preserva
también identidades, snapshots y recibos MP. No repetirla después de importar JSON.

## 3. Solo después del ensayo correcto: producción

Lo ejecuta el usuario, nunca este agente. Comprobar inventario, backup/checksum,
imagen/configuración anterior y web/workers detenidos según la guía. Si la base
real aún no fue adoptada, adoptar una única vez; si ya está versionada, omitirlo.
Consultar primero maintenance alembic current y comprobar el estado permitido.

Para distinguir esos casos sin cambiar la DB:

```sh
docker exec "$PG_CONTAINER" psql -X -U "$PG_USER" -d "$PG_DB" -Atc "SELECT to_regclass('public.alembic_version');"
```

Solo si esa consulta terminó correctamente y su respuesta es vacía:

```sh
maintenance python -m app.manage adopt-legacy
```

Después de adoptar, o si ya estaba adoptada en 0001-0003:

```sh
maintenance alembic current
maintenance python -m app.manage audit-mp-legacy > "$MAINT_DIR/prod-mp.before.json"
maintenance python -m app.manage migrate-legacy-mp > "$MAINT_DIR/prod-mp.transition.json"
maintenance alembic current
maintenance python -m app.manage check-mp-identities
maintenance python -m app.manage audit-mp-legacy > "$MAINT_DIR/prod-mp.after.json"
diff -u "$MAINT_DIR/prod-mp.before.json" "$MAINT_DIR/prod-mp.after.json"
```

Detenerse ante cualquier error o diferencia. Comparar cantidades con el inventario
real y repetir el control de head/identidades del ensayo. Los reportes antes/después
de producción deben coincidir entre sí; no se exige que sus hashes coincidan con
los de una copia si hubo movimientos legítimos desde el backup.
Guardar reportes/recibo en el directorio privado de mantenimiento, fuera de Git.
Continuar con la limpieza puntual de Gestión, importación y arranque de la nueva
imagen únicamente cuando corresponda según OPERACION_RASPBERRY.md.

## Efectos visibles y revisión pendiente

- Facturación muestra las filas históricas y sus marcas originales; los grupos
  repetidos no admiten selección, TODO, POST de IDs ni envío de solicitudes en cola.
  Un aviso explica el bloqueo; no se los presenta como una solicitud fiscal nueva.
- La sugerencia MP del cierre excluye los grupos repetidos. No cambia cierres de
  caja ya guardados, ventas, Ganancia, importes de facturas ni sus vínculos.
- Historial y estadísticas conservan todas las filas. Resumen sigue agregando
  registros aprobados y advierte cuántos son históricos repetidos; ese importe
  no se presenta como total conciliado de pagos únicos.
- Conexión MP conserva entregas/respuestas y muestra Conciliación pendiente para
  los IDs bloqueados. No reintenta automáticamente su resolución ni emite facturas.

Queda pendiente una conciliación manual futura de los 40 IDs y de los 14 miembros
repetidos sin marca. Este cambio no incluye un mecanismo de desbloqueo: requiere
otro procedimiento revisado que conserve originales y relaciones, evidencia por
grupo y una decisión explícita. No elegir min(id), el último JSON, una marca true
o la igualdad de importes como prueba de identidad fiscal. El ensayo real puede
descubrir otro bloqueo legítimo de las migraciones originales; no se debe saltar.
