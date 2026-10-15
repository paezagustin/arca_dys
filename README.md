# ARCA DYS

Sistema personal para facturación sencilla y control del negocio en Raspberry Pi 5.
FastAPI, SQLAlchemy, Jinja2, PostgreSQL 17 y Docker Compose.

La refactorización se desarrolla por hitos. El primer entregable prepara Windows 11,
simulación sin servicios reales, migraciones y documentación. La aplicación de la
Raspberry no se despliega ni se modifica automáticamente al publicar en GitHub.

## Probar en Windows 11 sin ARCA ni Mercado Pago

Requisito: Docker Desktop iniciado con contenedores Linux. En PowerShell, desde
esta carpeta:

```powershell
docker compose -f docker-compose.dev.yml up --build -d
```

Abrir **http://localhost:8001/dev**. Cargar pagos ficticios y recorrer Facturación,
selección de uno o varios pagos y descarga del PDF simulado. No requiere .env,
certificados, tokens, NGROK ni un pago real. Los comprobantes dicen SIN VALIDEZ FISCAL.
El importe del cargador es el de un pago ficticio; la factura independiente por
importe pertenece al hito H4, aún pendiente.

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

## Producción

`docker-compose.prod.yml` está separado del entorno local. Requiere .env.prod,
certificados y configuración explícita. Antes de cualquier actualización, identificar
la instalación efectiva, hacer backup en el SSD, ensayar adopción/migración en copia
y seguir la guía de operación. El SQL adjunto por el usuario solo contiene estructura.
No importarlo sobre la base actual.

La autorización fiscal confiable, idempotencia de MP, acceso autenticado y corrección
del comprobante productivo siguen en el roadmap. Este primer hito no se declara listo
para reemplazar al sistema productivo. La rotación de claves y CRON quedan a cargo
del usuario en una etapa posterior.
