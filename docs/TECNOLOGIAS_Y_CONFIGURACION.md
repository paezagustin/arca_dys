# Tecnologías, configuración e implementación

Referencia del código publicado, actualizada el 16/10/2026. Las versiones Python
están fijadas en requirements.in/requirements.txt; las imágenes, en los Compose.
Los nombres y montajes efectivos de la Raspberry se verifican antes de actualizar.

## Componentes del sistema

| Tecnología | Función | Implementación y configuración |
| --- | --- | --- |
| Python 3.11 | Ejecutar aplicación y comandos de mantenimiento. | Imagen python:3.11-slim-bookworm en Dockerfile. No requiere instalar Python en la Raspberry fuera de Docker. |
| FastAPI 0.143.2 | Rutas HTTP, formularios, validación y respuestas. | app/main.py registra app/api/*.py. Las rutas delegan reglas en app/services/. No hay servidor de frontend separado. |
| Uvicorn 0.54.0 | Servidor ASGI. | Un proceso, puerto 8000 dentro del contenedor; sin reload en producción. No aumentar workers sin revisar el diseño del worker interno. |
| Pydantic 2.14.1 y python-multipart 0.0.32 | Validación HTTP y lectura de formularios. | FastAPI valida parámetros tipados; los formularios y las reglas de dinero/negocio se comprueban también en servicios. No delegar en el navegador la suma ni la elegibilidad de pagos. |
| python-dotenv 1.2.4 y python-dateutil 2.9.0.post0 | Configuración explícita y fechas externas. | config.py solo carga archivo si se indica APP_ENV_FILE; Compose suministra el entorno. payments.py interpreta fechas MP con zona y las lleva a Buenos Aires. |
| Jinja2 3.1.6, HTML, CSS y JavaScript | Interfaz renderizada en servidor. | app/templates/, app/assets/ y app/web.py. Menú móvil nativo details/summary, formularios con CSRF, búsquedas/paginación SQL, gráficos SVG locales. Sin SPA, Node ni compilación de frontend en producción. |
| PostgreSQL 17.8 | Persistencia y coordinación del trabajo. | Datos, sesiones, solicitudes fiscales e inbox MP. Transacciones, índices únicos y bloqueos PostgreSQL protegen duplicados/concurrencia. Producción usa imagen Debian; dev/test usan Alpine descartable. |
| SQLAlchemy 2.0.54 y psycopg2-binary 2.9.13 | Acceso a PostgreSQL. | app/core/database.py crea engine y sesiones; app/models/ define tablas/relaciones. Dinero en Decimal/NUMERIC(18,2), fechas comerciales en Buenos Aires. |
| Alembic 1.20.0 | Versionar el esquema. | alembic.ini, migrations/ y alembic_version. Head actual 0013_mp_identity; puente explícito para históricos MP repetidos según MIGRACION_MP_LEGACY.md. Producción exige migración manual; el arranque solo verifica la revisión. Revisiones publicadas inmutables. |
| afip.py 1.2.0 (Afip SDK) | Comunicación fiscal con ARCA/AFIP. | app/services/fiscal_gateway.py y app/services/arca/. Usa CUIT, access token de Afip SDK y certificado/clave ya existentes. No crea certificados ni registra otro punto de venta. |
| Requests 2.34.2 | Consultar recursos de Mercado Pago. | app/services/mp.py: GET a endpoints conocidos, token Bearer, comprobación de cuenta y timeouts. No usa el SDK MP ni ejecuta cobros/devoluciones. |
| ReportLab 4.5.1 | Generar PDF y QR localmente. | app/services/invoices.py usa la factura y su snapshot. Sin Chromium ni servicio remoto. Factura C, condición Efectivo y distribución 50/50, conservando el centavo. Un fallo de PDF no reemite. |
| openpyxl 3.1.5 y defusedxml 0.7.1 | Exportación de planillas. | app/services/excel_export.py genera el Excel de Resumen; defusedxml protege el manejo XML disponible para openpyxl. No hay importación Excel web. |
| Docker y Compose | Empaquetado, redes, arranque y almacenamiento. | Compose separados dev/test/prod. Dockerfile con targets development/production. Datos fuera del contenedor en el SSD. No se instala un broker ni un servicio adicional de tareas. |
| NGROK, agente 3 | Conectar HTTPS público con FastAPI para webhooks y acceso configurado. | Se conserva cuenta, authtoken y URL actuales. El perfil public es opcional; el override docker-compose.ngrok.yml fija explícitamente la URL existente. No abrir otro túnel simultáneo con el mismo dominio. |
| Adminer 5 | Consultar PostgreSQL manualmente. | Perfil tools, puerto 127.0.0.1:8081. No es la fuente de datos ni reemplaza pg_dump. No es necesario recrear el Adminer existente. |
| Uptime Kuma | Monitor de disponibilidad. | Perfil monitoring opcional; volumen propio en /mnt/datos/docker/uptime-kuma/data. Conservar el contenedor/volumen existente. El tag actual es latest: no hacer pull ni actualizarlo por efecto de desplegar esta app. |
| pytest y herramientas de pruebas | Verificación aislada. | requirements-dev.txt, tests/ y Compose test con PostgreSQL descartable/red interna. APIs simuladas, sin secretos productivos. Las pruebas de navegador usan un perfil temporal. |
| GitHub Actions | Validar PR y main integrado. | tests.yml conserva suite/backup/auditoría; agrega secretos, ARM64 y gate estricto. Solo main publica un artefacto; no conecta con Raspberry. |
| Agente pull systemd | Publicar main validado por conexión saliente. | scripts/deploy_agent.py instalado por root; sin runner/SSH entrante. Imagen exacta, drenaje PostgreSQL/marcador persistente, misma DB/NGROK y recuperación sin datos. Bootstrap supervisado en CI_CD.md. |
| Samba | Compartir archivos en la Raspberry. | Servicio externo al proyecto. Ya no interviene en la operación de Gestión: los datos están en PostgreSQL. Se puede usar para copiar JSON privados/respaldo; desplegar la app no modifica Samba. |

## Procesos y flujos

```mermaid
flowchart LR
    Browser[Navegador HTTPS] --> Tunnel[NGROK existente]
    MP[Mercado Pago] --> Tunnel
    Tunnel --> Web[FastAPI y Uvicorn]
    Web --> DB[(PostgreSQL en SSD)]
    Web --> Worker[Hilo worker del mismo proceso]
    Worker --> DB
    Worker --> MPGet[GET canónico MP]
    Worker --> Fiscal[Afip SDK / ARCA]
    Web --> PDF[PDF y Excel locales]
    CLI[Comandos manuales] --> DB
```

- **Facturación:** la confirmación HTTP guarda una solicitud durable. El worker
  procesa después. Consulta FECompUltimoAutorizado para CUIT/punto/tipo y obtiene
  el siguiente número; nunca lo calcula contando filas locales. Antes del envío
  persiste payload/número/reservas. Una respuesta incierta se consulta antes de
  reintentar; conservar esas tablas es parte de mantener el control fiscal.
- **Mercado Pago:** el POST se guarda en mp_events antes del ACK. El worker consulta
  el recurso real con GET, normaliza pago/estado y conserva historial. El ID canónico
  es único; repetir una notificación no duplica pagos ni borra registered_arca.
  Recibir un pago no emite una factura automáticamente.
- **Worker:** app/services/worker.py ejecuta MP y solicitudes fiscales en un hilo
  del proceso; espera tres segundos cuando no hay trabajo. La cola vive en DB.
  Reiniciar puede retomar solicitudes previamente confirmadas: antes del despliegue
  hay que drenar con el protocolo H19. Una barrera compartida cubre entrada,
  procesamiento y recuperación; paused impide operaciones nuevas mientras el host
  espera el bloqueo exclusivo. El cierre espera al hilo; nunca reemite como prueba.
- **Gestión:** ventas/egresos son independientes de cobros/facturas. Sueldos reducen
  Ganancia una vez; Fiados es un registro independiente. Los históricos JSON sin
  desglose conservan efectivo/MP NULL. Importación solo por consola, con transacción
  y recibo idempotente; ver IMPORTACION_JSON.md.

## Configuración: dónde se guarda y qué tiene prioridad

1. `.env.prod` es un archivo privado de la Raspberry. `--env-file .env.prod`
   alimenta la interpolación de Compose; `env_file: .env.prod` entrega variables
   al contenedor fastapi. Las claves declaradas en environment del servicio tienen
   prioridad sobre env_file; `docker compose run -e ...` puede sustituirlas para
   un comando puntual. Ese comando no reescribe el archivo. Las variables exportadas
   en la terminal prevalecen sobre --env-file para la interpolación de Compose.
2. `.env` no se carga automáticamente desde Python. APP_ENV_FILE solo permite
   cargar otro archivo cuando se especifica explícitamente; no se necesita en los
   Compose preparados. No ejecutar source .env.prod ni mostrar config completo.
3. Configuración en DB: business_settings conserva emisor, punto y límites
   guardados desde Configuración. Esos valores prevalecen sobre sus defaults de
   entorno; ARCA_PTO_VTA y límites de .env.prod son los valores iniciales si no hay
   configuración guardada. El CUIT de la pantalla debe coincidir con ARCA_CUIT.
4. Cada factura conserva un snapshot: editar ajustes no cambia las ya emitidas.
   Conservar business_settings y users evita reconfigurar el emisor y el admin
   al limpiar Gestión. Tokens, certificado y clave nunca se guardan en el panel.

| Variable | Uso y valor a conservar/verificar |
| --- | --- |
| ENV / INTEGRATIONS_MODE | production / production para la aplicación real. development o test con mock para ensayos. No combinar producción con mock. |
| ENVIRONMENT | Alias anterior opcional de ENV. Si ambos están definidos deben coincidir; retirar el alias viejo o corregirlo si contradice ENV. |
| ALLOW_LIVE_OPERATIONS | true para arrancar la aplicación productiva. false en dev/test. La configuración rechaza combinaciones ambiguas; no es un interruptor para poner en pausa una web productiva. |
| DATABASE_URL | Conexión a la DB efectiva, normalmente postgresql://arca_user:...@postgres:5432/arca_dys. Codificar caracteres reservados de la contraseña. No imprimirla. |
| POSTGRES_PASSWORD | Contraseña del rol existente; no cambiarla al actualizar. Cambiar esta variable no actualiza una contraseña de un volumen PostgreSQL ya inicializado. |
| POSTGRES_DATA_PATH | Directorio de datos existente; referencia /mnt/datos/docker/arca_dys/postgres. Verificar el montaje real antes de iniciar otro contenedor. |
| BACKUP_PATH / APP_LOGS_PATH | /mnt/datos/docker/arca_dys/backups y /mnt/datos/docker/arca_dys/logs. |
| ARCA_CERTIFICATES_PATH | Carpeta del host con el certificado y la clave existentes, montada solo lectura en /run/arca. |
| ARCA_CRT_PATH / ARCA_KEY_PATH | Rutas DENTRO del contenedor; por ejemplo /run/arca/certificado.crt y /run/arca/privada.key. Deben coincidir con los nombres reales. |
| ARCA_CUIT / ARCA_ACCESS_TOKEN | CUIT real y token de Afip SDK que ya funcionan. No confundir este token con la clave privada ni con el authtoken NGROK. |
| ARCA_PTO_VTA | Punto habilitado existente, sin cambiarlo para reiniciar la numeración. Factura C/tipo 11 está fijada en código. |
| MP_ACCESS_TOKEN / MP_COLLECTOR_ID | Token productivo y ID de la cuenta receptora que ya funciona. El gateway comprueba el collector de cada recurso. |
| MP_WEBHOOK_SECRET | Secreto de firma de la misma aplicación MP. Ruta firmada POST /mp/webhook. |
| MP_LEGACY_WEBHOOK_TOKEN | Solo para productos que no firman según su contrato; mínimo 32 caracteres. Ruta POST /mp/webhook/legacy/<token>. No ponerlo en ejemplos ni logs. |
| NGROK_AUTHTOKEN | Token de la misma cuenta NGROK. Si se mantiene el agente externo existente, se conserva en su instalación. |
| NGROK_URL | URL HTTPS actual completa, sin path. La consume únicamente el override docker-compose.ngrok.yml; no el código Python. No elegir otro dominio al desplegar. |
| LIMITE_FACTURACION_MINIMA / LIMITE_FACTURACION_MAXIMA | Defaults 1000 / 2000000, controles internos de la aplicación. Los límites guardados en Configuración prevalecen. No representan una afirmación legal. |
| UPTIME_KUMA_DATA_PATH | Volumen existente de Kuma, fuera de la carpeta PostgreSQL. No se limpia al actualizar Gestión. |

El archivo usa sintaxis dotenv, no es un script de shell. Los valores entre comillas
simples se interpretan literalmente; los valores sin comillas o con comillas dobles
pueden interpolar `$`. Preservar el valor exacto de cada clave y codificar caracteres
reservados de la contraseña en DATABASE_URL. Validar con config --quiet y respaldar
los archivos actuales antes de editar. Ver [la sintaxis oficial de Compose](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/#env-file-syntax).

## Persistencia en el SSD

```text
/mnt/datos/docker/
  arca_dys/
    postgres/           # cluster PostgreSQL existente; nunca borrar/mover por esta limpieza
    certificates/       # certificado y clave originales, solo lectura para la app
    backups/            # dumps custom, SHA256 y copias privadas de configuración
    logs/               # app.log/errors.log rotativos
    importacion_json/   # los tres JSON normalizados, copiados fuera de Git
  uptime-kuma/data/     # solo si coincide con el montaje que ya existe
```

Es una distribución de referencia. La carpeta arca_dys ya creada se reutiliza;
no se presupone que esté vacía ni que el repositorio de código esté dentro de ella.
Conservar rutas existentes si difieren y configurar las variables correspondientes.
PostgreSQL almacena también adjuntos JSON/resultados/snapshots. PDF y Excel se
generan a demanda; no requieren otro volumen de documentos.

Los logs locales rotan a 5 MB con cinco copias por archivo. Docker mantiene además
sus logs según la configuración del host. Un backup de la DB no copia certificados,
.env.prod, configuración NGROK ni el volumen de Kuma: conservarlos por separado.
CRON y copia de backups a otro dispositivo siguen fuera de este despliegue.

## Redes y servicios opcionales

- La aplicación escucha en 0.0.0.0:8000 dentro de Docker. El Compose productivo
  publica solo 127.0.0.1:8001 en la Raspberry; no es acceso LAN por IP. NGROK dentro
  de la misma red Docker usa http://fastapi:8000; un agente en el host puede usar
  http://127.0.0.1:8001. Un contenedor externo no llega al host con su propio localhost.
- Usar el acceso HTTPS ya configurado. Las cookies Secure de producción requieren
  HTTPS para los formularios/sesiones; una prueba HTTP de /health no valida el login.
- PostgreSQL no publica puerto al host en el Compose productivo. Adminer se conecta
  a postgres:5432 en esa red. No agregar puertos públicos para hacer la migración.
- Perfiles opcionales: public (NGROK), tools (Adminer), backup y monitoring (Kuma).
  Arrancar fastapi con --no-deps después de comprobar PostgreSQL evita recrear
  servicios externos. Mantener un único gestor: Compose existente o Portainer,
  sin dos stacks que intenten usar los mismos nombres/volúmenes.
- Dev/test tienen redes aisladas; Nginx es únicamente proxy local de desarrollo,
  no una dependencia del Compose productivo. No copiar el perfil dev a la Raspberry.

## Qué se conserva durante la limpieza acordada

La limpieza manual documentada elimina únicamente proveedores, ventas/egresos,
importaciones de Gestión, Sueldos y Fiados. Conserva payments/registered_arca,
invoices, payment_invoice, billing_requests/reservations, inbox/historial MP,
usuarios, emisor, auditoría monetaria, logs y Alembic. Así no se pierde la identidad
de un cobro facturado ni una emisión incierta. No se reinicia el cluster ni las
secuencias fiscales; no se toca NGROK, certificados ni credenciales.

Procedimiento y comandos: [OPERACION_RASPBERRY.md](OPERACION_RASPBERRY.md).
Modelo y recuperación: [ARQUITECTURA.md](ARQUITECTURA.md).
Contratos efectivos: [MERCADO_PAGO.md](MERCADO_PAGO.md).

Referencias oficiales contrastadas al preparar esta guía:
- [NGROK: URL y destino del agente](https://ngrok.com/docs/agent/cli/#ngrok-http).
- [Mercado Pago: configuración y reentregas de notificaciones](https://www.mercadopago.com.ar/developers/es/docs/checkout-api-orders/optional-notifications).
- [Afip SDK: último comprobante autorizado](https://afipsdk.com/docs/api-reference/web-services/wsfe/FECompUltimoAutorizado/prod/python/).
- [PostgreSQL 17: TRUNCATE y RESTRICT](https://www.postgresql.org/docs/17/sql-truncate.html).
- [Imagen PostgreSQL: variables solo para inicialización](https://docs.docker.com/guides/postgresql/).
