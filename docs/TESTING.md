# Pruebas locales y CI

## Suite reproducible en Windows 11
Instalar/iniciar Docker Desktop con contenedores Linux. Desde la raíz del repo:

```powershell
docker compose -f docker-compose.test.yml run --build --rm test
docker compose -f docker-compose.test.yml --profile backup-test run --rm backup-test
docker compose -f docker-compose.test.yml down --volumes --remove-orphans
```

El último comando elimina exclusivamente el entorno de pruebas arca-dys-test.
Nunca cambiarlo por el compose productivo. No pasar archivos de variables reales.
PostgreSQL test usa tmpfs, sin puerto publicado ni /mnt. Desarrollo usa otro volumen.
El perfil backup-test genera un backup, comprueba checksum, restaura en otra base
temporal y verifica un importe ficticio y la revisión de esquema. No copia datos reales.

## Alcance de la suite inicial
- Fallo cerrado de configuración local/productiva, errores tipográficos y límites.
- Bloqueo de clientes reales; modo simulado rechaza IDs productivos.
- Rutas de simulación ausentes cuando la aplicación se configura para producción.
- Formularios de selección vacía, única, múltiple e inválida; recorrido con PostgreSQL.
- Pagos ficticios -> factura simulada -> PDF parseable con aviso sin validez fiscal.
- Escenarios approved/pending/rejected/refunded/api_error sin conexiones de proveedores.
- Nueva base migrada, exportación heredada adoptada sin perder filas y drift rechazado.
- Limpieza 0002: conserva pagos/facturas/vínculos/errores; rechaza campos o tabla
  con información y deja esquema, datos y versión intactos. Downgrade y upgrade probados.
- Contrato de respuesta completa del SDK, con detalle único o lista, observaciones y
  vencimiento. Cliente falso; ningún contacto con ARCA. Respuesta guardada aunque
  falle PDF; descargas posteriores sin otra emisión. Respuesta simulada identificada.
- Registro y consulta del historial de errores sin campos de resolución retirados.

Estas pruebas NO certifican todavía idempotencia/concurrencia fiscal, recuperación
del CAE, formato de todos los productos MP, QR real ni diseño del PDF productivo.
Esas garantías tienen tareas obligatorias en H2-H5. Los ejemplos no sustituyen
una importación ni una migración de registros de producción.

## Aislamiento
La suite aborta antes de limpiar si no coincide ENV=test, INTEGRATIONS_MODE=mock y
el destino arca_dys_test del servicio postgres. Solo usa fixtures ficticios.
pytest-socket bloquea sockets de red Python; requests se bloquea explícitamente.
psycopg2 en C no pasa por ese bloqueo, por eso se mantienen la validación de URL
y la red interna de Docker. El test de producción importa rutas, sin iniciar
lifespan ni construir clientes reales. No requiere ningún secreto en GitHub Actions.

## Navegador
Abrir http://localhost:8001/dev, cargar ejemplos, seleccionar uno o varios pagos,
facturar y descargar PDF. Probar también errores y selección vacía. Verificar
consola, estado visible y persistencia en DB. Registrar la evidencia concreta.
TestClient y comprobar cadenas HTML no cuentan como validación visual.

## Homologación futura
No habilitada en este hito. Si se agrega, usar un perfil distinto de la suite habitual:
certificados de homologación, production=False y credenciales/URLs de prueba de MP
según el producto real. Nunca usar una factura productiva de prueba ni dinero real.
