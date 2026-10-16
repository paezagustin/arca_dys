# Estado de ejecución

Actualizado: 2026-10-16, America/Buenos_Aires.

## Estado vigente
H0-H7 publicados y validados. H8 implementado: métricas, índices 0009_reports,
dependencias actualizadas/auditadas, límites de carga, renovación de assets y
documentación de operación. Falta cerrar la última ejecución ARM64 y CI del hito.
El objetivo sigue activo hasta completar esas comprobaciones y publicar su evidencia.
No detenerse entre pasos ordinarios ni pedir otra autorización para commits/push.

## Entregas publicadas
| Hito | Commit de código | Evidencia |
| --- | --- | --- |
| H0/H1 | bc5ef9c2c33d06ff5f1e8bfa7334c0ac90377fa6 | Entorno aislado, baseline/adopción, 50 pruebas, backup/restore y navegador. CI 38810887827 success. |
| Preparación H2 | ddb345b803fff2910605ce796b2fbb4f63f5c750 | Limpieza autorizada 0002 y respuesta fiscal completa. CI 38814927347 success. |
| H2 | d7eb9a8253024cd008b13dd6840faab28494c0f5 | 76 pruebas; concurrencia, pérdida de respuesta/CAE/commit, recuperación y PDF sin reemisión. CI 38817262006 success. |
| H3 | 8bc2a3f8200c68354d95046cd7ff5b0b7ffedd19 | 94 pruebas; inbox, firmas, identidad, estados, reintentos y contratos MP. CI 38818564439 success. |
| H4 | e3228d77c75633ed4de40c4869bdcdb9964f4ff3 | 112 pruebas; acceso/roles/CSRF, ajustes/snapshot, factura independiente y QR leído desde PDF. CI 38820685646 success. |
| H5 | 89dc110c087495520e86c700eb4561526c53454c | 132 pruebas; paginación/filtros/TODO, confirmación estable y cola fuera de HTTP. CI 38823737655 success. |
| H6 | e6dde32fa171c2fab645ec88926d81053c0d7c67 | 150 pruebas; gestión/proveedores, auditoría y Float→NUMERIC conciliado. CI 38824494125 success. |
| H7 | 8d0e384555a1b85771c92874516fac5dfa11a87b | 161 pruebas + ampliación dirigida de 13 casos; Excel trazable y conflicto/XML. CI 38844309749 success. |

## Evidencia vigente de H8
- Suite x86/Windows: 173 passed, 1 warning, 48.15s; cero pruebas omitidas. Se amplió
  después la protección de precisión fiscal para límites administrativos elevados;
  los 40 casos de métricas/operación/seguridad afectados aprobaron tras ese ajuste.
- Auditoría pip-audit 2.10.1: sin vulnerabilidades conocidas en requirements.txt.
  Resolución instalada con pip check aprobado. Sin pymysql/SDK MP innecesarios;
  SQLAlchemy sigue en 2.0 y PostgreSQL sigue en 17.8.
- Backup custom, catálogo, SHA256 y restauración con importe 12345.67/revisión
  0009_reports aprobados tanto en x86 como en ARM64. Ejecutar después de migrar y
  sin otra suite sobre la misma DB; una recreación de tmpfs elimina su esquema.
- Original Excel montado read-only, verificado otra vez con dependencias nuevas:
  9 meses, 493 registros, 30 revisiones; totales mensuales numéricos exactos,
  reimportación idempotente, originales/históricos íntegros, sueldos excluidos y
  hash del archivo intacto. DB privada efímera eliminada, sin datos reales en Git/dev.
- Imagen de ejecución ARM64 construida: 379878247 bytes. Su servidor real en mock
  completó login/CSRF, confirmación, worker, factura independiente, PDF y dashboard.
  RSS máximo hijo 169400 KiB; 10 health promediaron 20.3 ms bajo emulación/QEMU.
- Imagen de ejecución amd64: 343873208 bytes; mismo recorrido aprobado, RSS máximo
  hijo 110708 KiB y health promedio 3.0 ms. Sin reload en ambos ensayos. Son muestras
  locales, no mediciones del hardware Raspberry. No se iniciaron servicios productivos.
- Suite ARM inicial: 172 casos aprobados; un proceso de inspección tardó más del
  límite de 15s bajo emulación. Se amplió a 60s y la suite completa se está repitiendo.
- Navegador: venta/egreso/proveedor, importación ficticia y revisión con motivo,
  históricos separados y filtro mensual/tabla/gráfico. Documento móvil 375px de
  ancho sin desbordamiento exterior en viewport 390x844. Consola sin errores.
  CSS/JS se versionan para renovar la caché al actualizar; colores/estructura verificados.
- PDF simulado revisado: una página, logo, C, Efectivo, 50/50 exacto y SIN VALIDEZ
  FISCAL. No se emitió ninguna factura real ni se consultó el QR en ARCA.

Capturas/resultados ignorados en artifacts/: h2-facturacion.jpg,
h4-factura-independiente.jpg, h5-todo-filtro.jpg, h5-seleccion-movil.jpg,
h6-gestion.jpg, h7-historicos.jpg, h8-grafico.jpg, h8-movil.jpg y
comprobante-simulado.pdf. H3 se verificó por navegador/DB; no se afirma captura de H3.

## Alcance preservado y publicación posterior
Factura C, Efectivo y reparto 50/50; cobros completos sí/no, factura independiente,
ventas manuales reales separadas, proveedores simples, Excel sin sueldos y métricas
sin saldos pendientes. No se agregaron stock, cuenta corriente, salarios ni SPA.
Los originales SQL/Excel se conservan; solo se retiran las estructuras autorizadas.

Ningún push despliega la Raspberry. No se accedió al dispositivo ni se hizo su backup
real en el SSD; se dejó el comando manual validado. Montajes/locale/configuración
efectivos, ensayo del respaldo real y ejemplos anonimizados de la cuenta MP se
verifican antes de publicar allí, según OPERACION_RASPBERRY.md y MERCADO_PAGO.md.
Los contratos MP actuales están basados en documentación oficial/fixtures, sin
certificar que todos los medios de la cuenta notifiquen igual. No se certificó
homologación ni conectividad productiva ARCA/MP. CRON y rotación de claves quedan
para el usuario. La sesión no ejecuta esas operaciones como parte de las pruebas.
