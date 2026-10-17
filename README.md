# ARCA DYS

Sistema personal para facturación sencilla y control del negocio en Raspberry Pi 5.
FastAPI, SQLAlchemy, Jinja2, PostgreSQL 17 y Docker Compose.

Facturación recuperable, cobros MP idempotentes, configuración, gestión/proveedores,
carga inicial por consola desde JSON y dashboard. La aplicación de la Raspberry no
se despliega ni se modifica automáticamente al publicar en GitHub.

## Probar en Windows 11 sin ARCA ni Mercado Pago

Requisito: Docker Desktop iniciado con contenedores Linux. En PowerShell, desde
esta carpeta:

```powershell
docker compose -f docker-compose.dev.yml up --build -d
```

Abrir **http://localhost:8001** sin login para Facturación, Gestión, Resumen, Sueldos y Fiados.
Para Pruebas y administración, ingresar con **admin / pruebas-locales**,
cuenta exclusiva del entorno simulado. Cargar pagos ficticios y recorrer Facturación,
selección de uno o varios pagos y descarga del PDF simulado. No requiere .env,
certificados, tokens, NGROK ni un pago real. Los comprobantes dicen SIN VALIDEZ FISCAL.
El importe del cargador es el de un pago ficticio. Para una factura independiente,
usar **Factura por importe**, revisar el importe y confirmar. No crea otro ingreso.
En **Gestión** registrar efectivo y Mercado Pago del día (MP sugerido editable),
y egresos En Blanco/En Negro. **Sueldos** registra pagos de Francisco/Juan Cruz;
**Fiados** permite anotar clientes y marcar pagos. En **Resumen** consultar por
día/período/mes/año, ventas por medio, sueldos por empleado y Ganancia después de
egresos y sueldos. Exportar Excel conserva las seis columnas originales y añade
hojas Ventas y Sueldos. No hay módulo web de importación.

La carga inicial de los tres JSON corregidos se ejecuta una sola vez por base:

```powershell
docker compose -f docker-compose.dev.yml run --rm --no-deps fastapi python -m scripts.import_business_json --directory /app/data/private/importacion_negocio/normalizados
docker compose -f docker-compose.dev.yml run --rm --no-deps fastapi python -m scripts.import_business_json --directory /app/data/private/importacion_negocio/normalizados --apply
```

El primer comando valida sin escribir; el segundo inserta todo en una transacción.
Repetir los mismos archivos no duplica datos. Los JSON privados no se publican en
GitHub ni se incluyen en las imágenes. Ver [preparación y comandos para Raspberry](docs/IMPORTACION_JSON.md).

```powershell
docker compose -f docker-compose.dev.yml stop
docker compose -f docker-compose.dev.yml up -d
```

El volumen de desarrollo conserva solo datos locales. No usar down --volumes
para detenerlo. No comparte /mnt ni la base de la Raspberry.

## Ejecutar las pruebas

```powershell
docker compose -f docker-compose.test.yml run --build --rm test
docker compose -f docker-compose.test.yml --profile backup-test run --rm backup-test
docker compose -f docker-compose.test.yml down --volumes --remove-orphans
```

La suite usa PostgreSQL descartable y red interna. No necesita secretos de GitHub.
La segunda prueba verifica backup custom, checksum y restauración de datos ficticios.

## Documentación

- [Reglas para Codex](AGENTS.md): autonomía, push directo y prohibición de pruebas productivas.
- [Alcance definitivo](docs/ALCANCE.md): decisiones, exclusiones y requisitos.
- [Roadmap](docs/ROADMAP.md) y [estado reanudable](docs/EXECUTION_STATUS.md).
- [Arquitectura y revisión de campos](docs/ARQUITECTURA.md).
- [Pruebas](docs/TESTING.md) y [guía de uso local](docs/GUIA_USUARIO.md).
- [Versionado, backup y operación](docs/DATOS_Y_OPERACION.md).
- [Acceso, configuración y PDF](docs/ACCESO_Y_COMPROBANTES.md).
- [Contratos y operación MP](docs/MERCADO_PAGO.md).
- [Transición de históricos MP repetidos](docs/MIGRACION_MP_LEGACY.md): ensayo
  aislado, conservación íntegra y puente explícito hasta 0013_mp_identity.
- [Gestión y proveedores](docs/GESTION.md), [importación por consola](docs/IMPORTACION_JSON.md)
  y [métricas](docs/METRICAS.md).
- [Validación ARM y operación](docs/OPERACION_RASPBERRY.md).
- [Tecnologías y configuración](docs/TECNOLOGIAS_Y_CONFIGURACION.md): función,
  implementación, variables, redes, volúmenes y servicios opcionales.

## Producción

`docker-compose.prod.yml` está separado del entorno local. Requiere .env.prod,
certificados y configuración explícita. Antes de cualquier actualización, identificar
la instalación efectiva, hacer backup en el SSD, ensayar adopción/migración en copia
y seguir la [guía de despliegue manual](docs/OPERACION_RASPBERRY.md). El usuario
confirmó conservar cobros/facturas/control fiscal y limpiar únicamente Gestión,
Sueldos y Fiados con el comando puntual documentado, después de migrar. No borrar
la DB ni el directorio PostgreSQL. Mantener el dominio NGROK y las credenciales
MP/ARCA; el override opcional docker-compose.ngrok.yml fija la URL actual.
El SQL adjunto por el usuario solo contiene estructura.
No importarlo sobre la base actual.

El entorno simulado y sus pruebas nunca emiten en ARCA ni operan dinero real.
La puesta en producción requiere verificar la instalación efectiva y los formatos
de notificación de la cuenta, configurar el emisor y ensayar sobre su respaldo.
La rotación de claves y CRON quedan a cargo del usuario. Consultar el estado de
ejecución para la evidencia realizada y los límites de la validación.
