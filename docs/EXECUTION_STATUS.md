# Estado de ejecución

Actualizado: 2026-10-15, America/Buenos_Aires.

## Hito actual
H0 y H1 completados. Código publicado en main como `bc5ef9c2c33d06ff5f1e8bfa7334c0ac90377fa6`.
CI de ese commit: [Pruebas aisladas, ejecución 38810887827](https://github.com/paezagustin/arca_dys/actions/runs/38810887827), success.
Imagen productiva construida en amd64, sin desplegarla. El sistema completo NO está refactorizado
todavía y este hito no se despliega sobre la Raspberry.

## Alcance incorporado
Factura C, pagos completos con facturado sí/no y factura independiente futura.
Sin facturación parcial, sueldos, saldos en métricas ni cuentas corrientes.
Ventas diarias manuales independientes de cobros y facturas; dashboard e importación
histórica incluidos. Condición de venta y reparto 50/50 conservados.
No hubo rotación de claves, operación en proveedores, backup productivo ni acceso a Raspberry.

## Implementación inicial
- Reglas AGENTS, alcance, arquitectura, roadmap, operación, testing y guía de uso.
- Compose dev/test/prod separados; dev local accesible solo por loopback.
- API y PostgreSQL locales en red interna; entrada mínima de navegador mediante proxy.
- Simulación sin credenciales, clientes reales bloqueados, escenarios y ejemplos.
- PDF simulado legible y señalizado; imagen dev sin Chromium.
- Mínimo/máximo centralizados y configuración con rechazo de combinaciones inseguras.
- Baseline Alembic 0001_legacy, comparador congelado y adopción explícita sin pérdida.
- Arranque sin create_all; rechazo de revisión de DB desactualizada.
- Backup manual custom/checksum y ensayo de restauración con datos ficticios.
- Workflow de GitHub Actions sin secretos ni despliegue automático.

## Evidencia ejecutada
| Verificación | Resultado |
| --- | --- |
| Docker Desktop/Linux en Windows | Disponible; entornos con nombres propios, sin usar el PostgreSQL ajeno que ya ocupaba 5432. |
| Suite PostgreSQL 17.8 | 50 passed, 29 warnings, 3.86s; ninguna omitida. |
| Migración nueva | 0001_legacy aplicada y esquema comprobado. |
| Adopción desde fixture Adminer | Fila ficticia e importe conservados; drift y segunda adopción rechazados. |
| Backup/restauración | Checksum OK; restauración en otra DB conserva 12345.67 y revisión 0001_legacy. |
| Navegador IAB | Cargar tres pagos; seleccionar dos; emitir SIM por 40000; queda un pago por 10000 y enlace PDF. |
| Error simulado en navegador | Falla MP muestra resultado comprensible sin agregar pago aprobado. |
| PDF | Parseado con pypdf; texto SIN VALIDEZ FISCAL e importe comprobados. |
| Compose prod | config --no-env-resolution --quiet validado con valores de ejemplo; NO iniciado. |
| Imagen prod | Build target production en amd64 completado, Chromium instalado; sin montar credenciales ni iniciar servicios productivos. ARM pendiente. |
| Tamaño de imágenes amd64 | Dev 297307718 bytes; prod 2216024526 bytes. La optimización del PDF/Chromium está pendiente en H4; no son mediciones de RAM. |
| Aislamiento local | API solo en arca-dys-dev_isolated; network internal=true; puerto publicado únicamente por proxy en 127.0.0.1. |
| Salida externa de API | Prueba de socket desde el contenedor sin ruta externa: bloqueada. |
| GitHub | Push directo a main confirmado; workflow de tests y backup/restauración exitoso. Sin PR ni despliegue automático. |
| Exclusiones Git | Variables privadas, claves, backups, Excel, logs, cachés y capturas ignorados. |
| Sintaxis | 45 archivos Python parseados sin errores; diff --check limpio. |

Los warnings corresponden a APIs heredadas de TestClient/Jinja y consultas SQLAlchemy;
no fueron tratados como verificaciones omitidas. Su limpieza acompaña H2/H5.
Capturas locales no versionadas: artifacts/facturacion-simulada.jpg y artifacts/pruebas-locales.jpg.

## Próximo hito
H2 del roadmap: extraer caso de uso fiscal y resolver persistencia, atomicidad local,
concurrencia y resultado incierto. Luego H3 idempotencia/estados de MP y H4 configuración,
factura independiente y comprobante. No eliminar campos aún: el SQL entregado no contiene
datos para demostrar que estén vacíos. Auditar antes con scripts/audit-legacy.sql.

## Límites pendientes
Build/funcionamiento ARM y configuración efectiva de la Raspberry no comprobados.
Diseño PDF productivo, QR, emisor, autenticación, idempotencia del webhook y demás
hitos H2-H8 pendientes. El Compose productivo requiere adopción/migración coordinada;
no ejecutar up ni ALLOW_LIVE_OPERATIONS=true para probar cambios de desarrollo.
