# Estado de ejecución

Actualizado: 2026-10-15, America/Buenos_Aires.

## Estado vigente: H2-H5 validados, continuar H6-H8
El usuario pidió completar TODO el roadmap sin detenerse entre hitos y avisar al
final. Objetivo activo: continuar H6, H7 y H8 de forma autónoma.
H4 publicado como e3228d77c75633ed4de40c4869bdcdb9964f4ff3; CI success:
https://github.com/paezagustin/arca_dys/actions/runs/38820685646.

H5 implementado: filtros/paginación SQL independientes, límites de página y orden
estable; auditoría paginada y URL heredada compatible. TODO define los IDs de todo
el filtro en servidor; seleccionados rechaza IDs fuera del filtro. Ambas opciones
revisan cantidad/total antes de confirmar. Cola fiscal durable: HTTP no espera al
proveedor; la pantalla muestra el resultado y permite consultar incertidumbres.
Protección del resultado autorizado ante pérdida del ACK del commit; principal de
sesión inmutable para mostrar errores tras rollback. Sin CDN, con CSP y logo local.
Validación H5: 132 passed, 70 warnings HTTPX heredados, 34.39s; backup/restauración
con revisión 0006_listings. Navegador: desde página 2 de 31 pagos, TODO confirmó
31 por 31000 y generó factura SIM id5. En móvil 390x844, seleccionar todos marcó
dos pagos por 6000, confirmación y factura SIM id6. Auditoría página 2 y ancho de
documento comprobados sin desbordamiento exterior. Capturas ignoradas en artifacts/.
Continuar H6 sin detenerse. Ninguna operación real de ARCA/MP ni acceso a Raspberry.
H3 publicado como 8bc2a3f8200c68354d95046cd7ff5b0b7ffedd19; CI success:
https://github.com/paezagustin/arca_dys/actions/runs/38818564439.

H4 implementado: 0005_settings, sesiones revocables/roles/CSRF/login limitado,
configuración con auditoría/versionado, snapshot fiscal, factura independiente con
confirmación persistente y generador ReportLab unificado sin Chromium/PDF remoto.
112 pruebas aprobadas (74 warnings heredados), QR decodificado desde PDF rasterizado;
backup/restauración comprobados con revisión 0005_settings. Suite final tras ajustes
de bloqueo/CSRF: 112 passed, 74 warnings, 27.22s; ninguna omitida.
Navegador: login real local, importe 12345.67, revisión y confirmación; factura SIM id4
guardada sin pagos nuevos. Captura artifacts/h4-factura-independiente.jpg.
PDF simulado revisado visualmente: 14076 bytes, una página; artifacts/comprobante-simulado.pdf
y PNG de revisión (ignorados en Git). Imagen prod amd64 construida sin iniciarla:
328861983 bytes. Consumo instantáneo del dev amd64/reloader 109.8 MiB; no es medida Pi.
Publicar H4 y continuar H5 sin detenerse ni pedir permiso.
H2 publicado como d7eb9a8253024cd008b13dd6840faab28494c0f5; CI success:
https://github.com/paezagustin/arca_dys/actions/runs/38817262006.

H3 implementado: 0004_mp audita IDs heredados antes de imponer unicidad; no borra
duplicados. Inbox durable confirmado antes de ACK, worker del mismo proceso sin
infraestructura extra, historial y estados por timestamp, reintentos tras errores.
Firmas y entrada legacy separada, GETs con timeout y propietario comprobado.
Contratos y límites reales en MERCADO_PAGO.md; falta contraste con formatos de la
cuenta efectiva, no necesario para seguir desarrollando en simulación.
Validación H3: 94 passed, 57 warnings, 10.83s; backup/restauración revisión 0004_mp.
Navegador: SIM-H3-QA pasó approved → refunded; DB conservó un pago por 10000,
registered_arca=false y dos cambios. Captura de H3 no disponible en IAB; no se
afirma una captura guardada. DOM/acciones y persistencia sí comprobados.
Publicar H3 y registrar CI; seguir H4 sin solicitar aprobación.
H2 implementado: BillingService sin HTML, solicitudes/reservas/snapshots persistentes,
bloqueo PostgreSQL por punto/tipo, resultado incierto y consulta/reenvío del mismo
número; persistencia local atómica y PDF independiente. Migración 0003_billing.
Adaptador SDK con timeout, sin reintentos automáticos ni automatizaciones de cuenta.

Validación H2: 76 tests passed, 56 warnings heredados, 8.55s; backup SHA256 y
restauración comprobados con revisión 0003_billing. Casos ejecutados: concurrencia
igual/solapada/distinta, respuesta perdida, interrupción de proceso, fallo de commit
después del CAE, rechazo explícito, consulta fallida, reenvío del mismo payload,
autenticación no disponible, número incorrecto y PDF fallido sin reemisión.
Navegador IAB: crear pago ficticio de 10000, seleccionarlo y emitir; pantalla de
resultado con aviso SIN VALIDEZ FISCAL, importe correcto y enlace PDF.
Captura ignorada: artifacts/h2-facturacion.jpg. No se accedió a Raspberry ni proveedores.
Publicar este hito y registrar su CI; continuar H3 sin esperar aprobación humana.

## Antecedentes: H0/H1 y preparación de H2
H0 y H1 completados. Base publicada en main como `bc5ef9c2c33d06ff5f1e8bfa7334c0ac90377fa6`.
CI de ese commit: [Pruebas aisladas, ejecución 38810887827](https://github.com/paezagustin/arca_dys/actions/runs/38810887827), success.
Imagen productiva construida en amd64, sin desplegarla. El sistema completo NO está refactorizado
todavía y este hito no se despliega sobre la Raspberry.

Preparación de H2 implementada y validada localmente: limpieza solicitada de
estructuras sin uso y persistencia de respuesta fiscal completa. H2 NO está completo.
Código publicado en main: `ddb345b803fff2910605ce796b2fbb4f63f5c750`.
CI: [Pruebas aisladas, ejecución 38814927347](https://github.com/paezagustin/arca_dys/actions/runs/38814927347), success.
El push no despliega ni aplica la migración sobre la Raspberry.

## Limpieza de esquema y respuesta de emisión
- Nueva migración 0002_cleanup; 0001, comparador de adopción y exportación intactos.
- Retira error_logs.resolved/resolved_at/resolved_by/resolution_notes, logs_invoice
  y payments.id_arca. resolution_by no existe. Modelos, repositorios, imports y seed
  actualizados; se conserva payment_invoice como vínculo entre pagos y facturas.
- La migración bloquea las tablas y comprueba contenido dentro de una transacción.
  Información inesperada cancela la operación, sin borrarla ni adelantar versión.
- invoices.raw_afip_response conservada; afip.py 1.2.0 con return_response=True
  devuelve el resultado completo, incluidas observaciones. Se persiste también
  cuando falla el PDF. Simulación identificada; históricos sin respuesta no se rellenan.
- Índice único del modelo Invoice alineado con el ya existente; no se recrea.
- El usuario eliminará manualmente su SQL original; no fue modificado ni eliminado.

Evidencia nueva ejecutada en Windows/Docker:

| Verificación | Resultado |
| --- | --- |
| Suite completa PostgreSQL 17.8 | 68 passed, 32 warnings, 6.42s; ninguna omitida. |
| Migraciones | Base vacía hasta head; adopción de exportación con pago/factura/vínculo/error; importes, estados y respuesta previa conservados; metadata coincide con ORM. |
| Información inesperada | Seis escenarios cancelan sin pérdida ni cambios de esquema/versión: tabla de logs, ID y cada campo de resolución. |
| Reversibilidad | Downgrade de 0002 a 0001 y nuevo upgrade sin diferencias de metadata. |
| Adaptador fiscal | Cliente falso; respuesta completa dict/lista sin mutación; rechazos/malformadas no se aceptan como autorizadas. Ninguna emisión real. |
| Respuesta y PDF | JSON completo llega a PostgreSQL aun con fallo PDF; dos descargas posteriores no emiten otra factura. |
| Backup/restauración | SHA256 OK; restauración separada conserva 12345.67 y revisión 0002_cleanup. |
| Desarrollo local | Web healthy, modo mock, revisión 0002_cleanup; volumen ficticio conservado: 4 pagos, 1 factura y 2 vínculos. |
| Interfaz | No cambia un flujo visual en esta entrega; regresión de endpoints con TestClient. No se repitió QA visual ni se lo afirma. |
| GitHub | Push directo a main confirmado; tests y backup/restauración del commit ddb345b exitosos. |

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

## Evidencia inicial (H0/H1)
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
Continuar H5 UI/paginación, H6 gestión, H7 importación y H8 métricas/operación.
No ampliar la limpieza a otros campos sin
evidencia; los retirados en esta entrega fueron confirmados por el usuario.

## Límites pendientes
Build/funcionamiento ARM y configuración efectiva de la Raspberry no comprobados.
Diseño PDF productivo, QR, emisor, autenticación, idempotencia del webhook y demás
hitos H5-H8 pendientes. El Compose productivo requiere adopción/migración coordinada;
no ejecutar up ni ALLOW_LIVE_OPERATIONS=true para probar cambios de desarrollo.
