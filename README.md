# ARCA DYS

Sistema personal para facturación sencilla y control del negocio en Raspberry Pi 5.
FastAPI, SQLAlchemy, Jinja2, PostgreSQL 17 y Docker Compose.

La refactorización se desarrolla por hitos. Están preparados Windows 11, simulación,
migraciones, facturación recuperable, integración MP y configuración/comprobantes.
Gestión, importación y métricas continúan según el roadmap. La aplicación de la
Raspberry no se despliega ni se modifica automáticamente al publicar en GitHub.

## Probar en Windows 11 sin ARCA ni Mercado Pago

Requisito: Docker Desktop iniciado con contenedores Linux. En PowerShell, desde
esta carpeta:

```powershell
docker compose -f docker-compose.dev.yml up --build -d
```

Abrir **http://localhost:8001/dev**. Ingresar con **admin / pruebas-locales**,
cuenta exclusiva del entorno simulado. Cargar pagos ficticios y recorrer Facturación,
selección de uno o varios pagos y descarga del PDF simulado. No requiere .env,
certificados, tokens, NGROK ni un pago real. Los comprobantes dicen SIN VALIDEZ FISCAL.
El importe del cargador es el de un pago ficticio. Para una factura independiente,
usar **Factura por importe**, revisar el importe y confirmar. No crea otro ingreso.

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

## Producción

`docker-compose.prod.yml` está separado del entorno local. Requiere .env.prod,
certificados y configuración explícita. Antes de cualquier actualización, identificar
la instalación efectiva, hacer backup en el SSD, ensayar adopción/migración en copia
y seguir la guía de operación. El SQL adjunto por el usuario solo contiene estructura.
No importarlo sobre la base actual.

Faltan los hitos de UI/gestión/importación/métricas y la comprobación ARM. No se declara
listo para reemplazar al sistema productivo sin terminar el roadmap y ensayar su
configuración y migraciones en copia. La rotación de claves y CRON quedan a cargo
del usuario en una etapa posterior.
