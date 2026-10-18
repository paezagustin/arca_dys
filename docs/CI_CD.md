# Git, CI y despliegue seguro H19

Decisión del 18/10/2026: reemplaza la prohibición histórica de autodespliegue.
**Implementar no equivale a activar.** No se ha accedido a la Raspberry ni validado
su instalación, respaldo real o primera actualización. No activar sin completar
el bootstrap y el ensayo supervisado de esta guía.

## Arquitectura y confianza

`task/*` o `fix/*` → PR → CI → squash a `main` → CI del SHA definitivo → artefacto
ARM64 → agente pull local → drenaje → reemplazo de fastapi → smoke → reapertura.
No hay rama dev permanente. Codex puede integrar cambios rutinarios tras validar
el SHA y todos los checks; para fiscales/destructivos/DB/seguridad/infraestructura/
credenciales/dependencias se requiere intervención explícita antes del merge.
Esta primera configuración es sensible: queda en PR para esa intervención.
Eliminar la rama temporal después del squash, nunca usar force-push sobre main.

Se conserva tests.yml: suite completa y migraciones con PostgreSQL descartable,
backup/checksum/restauración, producción x86 en mock, pip check y pip-audit.
Se agregan Compose ficticio, gitleaks redactado sobre historia/árbol, construcción
productiva ARM64 y smoke HTTP/worker/PDF bajo QEMU, sin credenciales productivas.
`ci-required` exige success de tests/security/arm64: skipped/neutral/pending no
alcanzan. Corre en PR y push. Solo un push a main produce el artefacto, con SHA,
revisión, protocolo, image ID y SHA256 del tar. Aunque el artefacto exista antes
de terminar otro job, el agente espera el éxito de TODO el run y cada job requerido.
La validación HTTP funcional no es revisión visual en navegador.

Se elige **pull systemd saliente** en lugar de self-hosted runner: no recibe jobs
arbitrarios de Actions/PR, no abre SSH/Docker/DB ni guarda secretos productivos en
GitHub. Un runner ARM64 sería simple, pero cualquier workflow con acceso podría
comprometer el host; una etiqueta no es aislamiento. Tailscale/SSH exige identidad,
red y privilegios de acceso remoto adicionales. GHCR privado agrega credenciales
de registro; el artefacto evita ese registro. Costo: minutos Actions para QEMU,
almacenamiento/descarga de una imagen y consulta cada minuto; retención 14 días.
Si caduca el artefacto, reejecutar CI para ese main; no reconstruir en producción.

El agente es stdlib Python >=3.11, instalado por root fuera del checkout. Su código,
Compose/configuración local y política NO se actualizan desde el artefacto.
El token local de GitHub es fine-grained, SOLO este repositorio y permisos Contents,
Actions y Pull requests de lectura; sin administración/escritura. Renovarlo localmente.
Docker da privilegios equivalentes a root: el agente tiene esa confianza; el token
y los directorios de estado/control son root:root 0700/0600. No montar Docker socket
en la app ni ofrecer comandos/argumentos arbitrarios a través de la web.

## Protección de main: verificación real y limitación administrativa

Consulta realizada: repositorio privado, conexión con push/triage, **sin admin ni
maintain**. `GET branches/main/protection` devuelve 403 Resource not accessible by
integration. `allow_auto_merge=false`; squash está disponible, también merge/rebase.
No se pudo conocer el plan, verificar protecciones existentes ni configurarlas.
El 403 NO demuestra que no exista protección ni que el plan sea gratuito.

La auditoría local de historia gitleaks v8.30.1 detectó 13 hallazgos (generic-api-key
y private-key) en commits anteriores, incluidos notebooks y un .env antiguo. No se
comprobó vigencia ni se copiaron valores. El job security queda deliberadamente en
fallo: no merge ni activación. El propietario debe investigar/revocar credenciales
afectadas fuera del chat. Rotar NO borra los hallazgos del historial: posteriormente
podrá autorizarse una baseline puntual de fingerprints revocados/falsos positivos
con evidencia. Esta implementación no incluye excepciones, exclusión global de
historia ni reescritura/force-push. El reporte local redactado está ignorado en Git.

El propietario debe ir a Settings → Rules/Branches y comprobar que su plan permite
proteger este repositorio privado (Pro/Team/Enterprise según titularidad). Configurar:

- PR obligatorio, historial lineal, checks tests/security/arm64/ci-required, fuente
  GitHub Actions y rama actualizada con main. Sin force-push, borrado ni bypass,
  incluidos administradores. No poner filtros de paths que omitan estos jobs.
- Solo squash, eliminación automática de ramas y, si está disponible, auto-merge.
- No exigir aprobación humana universal: impediría la autonomía rutinaria solicitada.
  Las instrucciones de Codex exigen intervención en sensibles; sin una regla de
  aprobación selectiva administrada, esto es una **convención antes del merge**,
  no una garantía técnica. CODEOWNERS sin su regla activa tampoco la garantiza.
- Si el plan no puede imponerlo, registrar esa limitación y NO afirmar que main está
  protegido. No activar CD hasta acordar explícitamente esa limitación con el dueño.

El agente sí impone fuera de GitHub: CI completo del SHA, main actual, avance desde
la versión instalada, cada commit nuevo asociado al squash de un PR integrado,
comparación completa (<300 archivos y <=50 commits, incluidos nombres anteriores).
Su lista positiva permite templates/assets, tests y módulos específicos de Gestión/
reportes. Cualquier archivo desconocido, fiscal, seguridad, scripts, Docker, workflows,
dependencias o migraciones requiere aprobación local del SHA exacto. Una aprobación
no habilita DDL. Usuarios con root o administración GitHub siguen siendo de confianza.

## Condiciones y protocolo fiscal

Antes de reemplazar: comprobar ARM64, UUID/montaje SSD y cada directorio, contenedores
existentes en el proyecto correcto, montajes de PostgreSQL/certificados/logs/control,
control de solo lectura, Compose, revisión Alembic y protocolo instalado. Nunca `up`
de postgres/ngrok ni otro stack. Solo `up -d --no-deps --no-build --pull never fastapi`.
No limpieza/importaciones ni migraciones. El helper `compose run --no-deps fastapi`
ejecuta únicamente la sonda sin iniciar web/worker ni clientes externos.

1. Host crea `deploy-control/paused` en bind persistente de solo lectura para la app.
2. issue/recover/schedule/process_one_queued y procesamiento MP adquieren lock de
   sesión compartido PostgreSQL `(72423,1)` y DESPUÉS comprueban paused. El lock
   cubre proveedor y todos los commits; llamadas anidadas reutilizan el contexto.
3. Sonda espera hasta 120s el lock exclusivo: las activas terminan; las nuevas se
   rechazan con 503 Retry-After (worker espera). La recepción MP sigue guardándose
   antes del ACK; durante el reemplazo el proveedor debe reintentar entregas fallidas.
4. Bloquear si hay sending/uncertain/check_queued/retry_queued, revisión incompatible
   o protocolo ausente. No borrar ni cambiar solicitudes para eludir el control.
5. Sonda de la candidata debe coincidir con la antigua. Releer main. Guardar pending,
   imagen/commit/revisión previos; reemplazar solo fastapi. El marcador persiste en
   la versión nueva y durante recuperación: no se consumen colas hasta el smoke.
6. Verificar HTTP health (commit/revisión/pausa/protocolo), DB y GET /login. No emitir
   ni consultar proveedores como smoke. Guardar current/previous y retirar paused.

Una consulta puntual de actividad NO autoriza reiniciar. La seguridad depende de
que TODO proceso fiscal use el protocolo y la misma DB/control. No ejecutar scripts
externos antiguos contra producción, aumentar workers o abrir otro acceso fiscal.
El cierre espera al worker en lugar de abandonarlo a los dos segundos. Solo CD
drenado debe usar docker stop/recreate; timeout/bloqueo exige revisión, no kill.
No garantiza continuidad ante pérdida de alimentación, muerte del host/DB o un
operador que fuerce el proceso; la recuperación fiscal durable sigue siendo necesaria.

## Instalación inicial supervisada (solo en la Raspberry)

Inventariar primero según OPERACION_RASPBERRY.md: instalación/Portainer, proyecto,
red, locales, contenedores y montajes reales. Los valores del example son referencias,
no una detección de la instalación. Si es Swarm, otros servicios/red o montajes,
adaptar y probar antes; no levantar otro Compose para averiguar si funciona.

```sh
uname -m                       # aarch64
python3 --version               # >=3.11
findmnt -n -o TARGET,UUID --target /mnt/datos/docker/arca_dys
mountpoint -q /mnt
docker inspect pg_dys --format '{{index .Config.Labels "com.docker.compose.project"}}'
docker inspect fastapi_app --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
```

Antes de instalar el primer código con protocolo 1, respaldar/restaurar en copia y
resolver migraciones/solicitudes inciertas mediante las guías existentes. El código
antiguo NO tiene la barrera: el agente se niega a reemplazarlo automáticamente.
El operador debe cerrar efectivamente TODOS los ingresos fiscales (incluidos otros
clientes/scripts y confirmaciones ya en vuelo), dejar terminar el worker y confirmar
cola vacía/resultados conciliados ANTES de detener el contenedor antiguo en una
ventana supervisada. El mecanismo de cierre de ingreso depende del NGROK/Portainer
inventariado; no se proporciona un comando genérico que pueda cortar una emisión.
Si no puede demostrarse esa exclusión, **no detener ni activar**, resolver primero.
No sustituir esto por una sola consulta SQL. No crear otro agente NGROK.

Instalar el código aprobado en una ruta root como /opt/arca-dys (adaptar a la real),
conservar .env.prod/certificados fuera de Git y mismo proyecto/red. Preparar:

```sh
sudo install -d -m 0700 /etc/arca-dys-deploy /mnt/datos/docker/arca_dys/deploy-state /mnt/datos/docker/arca_dys/deploy-control
sudo install -d -m 0755 /usr/local/lib/arca-dys-deploy
sudo install -m 0644 scripts/deploy_agent.py /usr/local/lib/arca-dys-deploy/deploy_agent.py
sudo install -m 0600 ops/deploy-config.example.json /etc/arca-dys-deploy/config.json
sudoedit /etc/arca-dys-deploy/config.json
sudoedit /etc/arca-dys-deploy/github-token
sudo chmod 0600 /etc/arca-dys-deploy/github-token
sudo touch /mnt/datos/docker/arca_dys/deploy-control/protocol-v1 /mnt/datos/docker/arca_dys/deploy-control/paused
sudo install -m 0644 ops/arca-dys-deploy.service ops/arca-dys-deploy.timer ops/arca-dys-deploy-notify.service /etc/systemd/system/
```

Configurar UUID real, rutas absolutas y proyecto EXISTENTE. .env.prod y Compose deben
ser propiedad de root y no escribibles por otros. Si hay paths fuera de /mnt o /opt,
adaptar también ProtectHome/ReadWritePaths del servicio, sin ampliar innecesariamente.
Instalar `/usr/local/sbin/arca-dys-deploy-notify` root:root 0700 con el canal local
ya utilizado (por ejemplo monitor existente), sin claves en Git. Debe avisar cuando
falle arca-dys-deploy.service; probarlo manualmente. No basta journal como alerta.
El agente comprueba que el hook exista; no puede certificar que llegue al destinatario.
No configurar notificaciones enviando claves por el chat.

En la ventana supervisada, instalar imagen aprobada con APP_COMMIT del SHA completo,
el montaje control/protocol-v1 y stop_grace_period de este Compose, solo fastapi,
sin migración automática. Con paused presente, comprobar /health y ambas sondas:

```sh
docker exec fastapi_app python -m scripts.deploy_guard --drain
curl --fail --silent http://127.0.0.1:8001/health
```

Esperado: protocol 1, revision 0013_mp_identity, health commit igual al instalado y
paused true. No usar una imagen de bootstrap desconocida como rollback: ambas
versiones del primer ensayo deben implementar protocolo 1, misma revisión y commit
identificado. Conservar imagen local por ID/tag y archivo `docker save`; no usar
prune ni limpieza automática. Inicializar `deploy-state/current.json` con la misma
estructura de release.json y datos del contenedor instalado. Verificar sin secretos:

```sh
docker inspect fastapi_app --format '{{.Image}}'
docker image inspect IMAGEN_ID_REAL --format '{{index .Config.Labels "org.opencontainers.image.revision"}} {{.Architecture}}'
```

Registrar automáticamente los datos verificados (se niega a sobrescribir un estado
existente; no reemplaza la app ni quita paused):

```sh
sudo python3 /usr/local/lib/arca-dys-deploy/deploy_agent.py --record-bootstrap
sudo cat /mnt/datos/docker/arca_dys/deploy-state/current.json
```

Esperado: mismo commit/image_id/revision, protocolo 1 y arm64; deja tag rollback y
el timer apagado. Guardar también `docker save IMAGEN_ID_REAL` en el SSD con permisos
restrictivos. Nunca inventar SHA ni marcar instalada mientras corre otra versión.
Quitar paused SOLO después de revisar esas comprobaciones:

```sh
sudo rm -- /mnt/datos/docker/arca_dys/deploy-control/paused
```

No se requieren pagos ni facturas reales de prueba.

## Primera prueba y activación

Primero ensayar en copia con datos ficticios: operación simulada lenta, rechazo de
nuevas entradas, uncertain, SSD ausente, revisión incorrecta, main que avanza, CI
pendiente/fallido/omitido, fallo de arranque y recuperación. La suite automatiza
parte de estos casos; no sustituye comprobar montajes/systemd de la Raspberry.
Preparar un siguiente commit rutinario integrado para el ensayo controlado.

```sh
sudo systemd-analyze verify /etc/systemd/system/arca-dys-deploy*.service /etc/systemd/system/arca-dys-deploy.timer
sudo systemctl daemon-reload
# Habilita ejecuciones individuales; el timer sigue APAGADO.
sudo touch /mnt/datos/docker/arca_dys/deploy-state/enabled
sudo systemctl start arca-dys-deploy.service
sudo journalctl -u arca-dys-deploy.service -n 30 --no-pager
sudo cat /mnt/datos/docker/arca_dys/deploy-state/events.jsonl
```

Esperado: deployed con SHA exacto, current/previous correctos, sin pending/paused,
misma DB/PG/ngrok y health correcto. Comprobar menú/HTTPS en el dominio existente sin
emitir/cobrar; el smoke local de login no verifica cookies Secure ni túnel público.
Ensayar recuperación supervisada con imágenes protocolo 1 y misma revisión en copia.
SOLO después del resultado registrado y aprobación de esa activación:

```sh
sudo systemctl enable --now arca-dys-deploy.timer
systemctl list-timers arca-dys-deploy.timer
```

La primera prueba real queda **pendiente**, no ejecutada por el agente de desarrollo.
El timer no es CRON de backups. El agente calla mientras no hay cambios o CI sigue
pendiente; el primer fallo guarda failed.json/notifica y detiene reintentos hasta revisión.

## Mantenimiento, contingencia y recuperación

- Apagar automatismo: `sudo systemctl disable --now arca-dys-deploy.timer`. No mata
  una operación ya iniciada. Revisar el servicio antes de mantenimiento concurrente;
  no reiniciar el host ni matar Docker. El lock local impide dos agentes simultáneos.
- Despliegue manual normal: `sudo systemctl start arca-dys-deploy.service`; mismos
  controles, nunca acepta una rama temporal/SHA arbitrario fuera de main.
- Sensible sin DDL: revisar el PR y registrar aprobación ANTES del merge. Después
  aprobar localmente el SHA definitivo, no el head del PR, en `deploy-state/approved-sha`
  (root:root 0600). Ejecutar `sudo python3 /usr/local/lib/arca-dys-deploy/deploy_agent.py --retry`.
  El permiso aplica solo a ese SHA; no sortea checks/PR/montajes/drenaje/esquema.
- Migración: CD bloquea. Backup/restauración aislada/ensayo de migración y actualización
  supervisada según OPERACION_RASPBERRY.md; no editar versiones antiguas, stamp,
  borrar reservas ni ejecutar alembic desde el agente. Rehacer baseline current/previous
  después del mantenimiento; un rollback de código requiere misma revisión.
- Fallo de nueva imagen con esquema intacto: vuelve a la anterior y la verifica
  MIENTRAS paused está puesto. No toca datos; deja failed.json para revisión.
- Si tampoco recupera, preserva paused/pending/evidencia y bloquea el worker. Revisar
  localmente sin publicar logs fiscales. Con pending disponible, ejecutar:
  `sudo python3 /usr/local/lib/arca-dys-deploy/deploy_agent.py --recover`.
  Recupera la imagen previous registrada, comprueba revisión/HTTP/DB y abre la barrera.
  Admite app detenida; exige PG/stack/montajes sanos. No borra failed.json: el operador
  revisa antes de volver a intentar la versión fallida con --retry.
- Si hubo corte antes de guardar pending, hay paused pero no reemplazo: comprobar
  imagen antigua y sonda --drain; retirar paused manualmente SOLO después de esa
  verificación. No inventar pending ni continuar a ciegas.
- Jamás rollback de DB/datos fiscales, restaurar sobre una DB activa, down -v,
  limpieza/importación o downgrade automático. Una factura emitida fuera del host
  no desaparece restaurando PostgreSQL: requiere conciliación humana.

Logs seguros: events.jsonl registra fecha UTC, SHA, resultado y código de error;
failed/pending/current/previous preservan evidencia. stdout/stderr Docker no se
imprimen para evitar credenciales. El detalle sensible se investiga solo localmente.

## Fuentes técnicas verificadas

- [Riesgos del self-hosted runner](https://docs.github.com/en/actions/reference/security/secure-use).
- [Disponibilidad de protección de ramas](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
- [Restricciones de environments y revisores por plan](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments).
- [API de artefactos y digest](https://docs.github.com/en/rest/actions/artifacts).

GitHub puede aceptar skipped/neutral como check requerido: por eso existe el gate
ci-required y el agente vuelve a exigir success explícito de los jobs completos.
Los revisores de environments en privados dependen del plan: no se asumen disponibles.
