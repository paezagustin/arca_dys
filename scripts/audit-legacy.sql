-- Solo lectura: cantidades de uso, sin exponer contenidos. No elimina datos.
-- Ejecutar únicamente sobre el esquema heredado/0001_legacy, ANTES de 0002_cleanup.
SELECT count(*) AS pagos,
 count(*) FILTER (WHERE bill IS TRUE) AS bill_true,
 count(*) FILTER (WHERE bill IS FALSE) AS bill_false,
 count(*) FILTER (WHERE bill IS NULL) AS bill_null,
 count(*) FILTER (WHERE nullif(trim(id_arca), '') IS NOT NULL) AS id_arca_con_valor
FROM payments;
SELECT count(*) AS grupos_mp_repetidos FROM
 (SELECT id_payment_mp FROM payments GROUP BY id_payment_mp HAVING count(*) > 1) duplicates;
SELECT count(*) AS facturas,
 count(*) FILTER (WHERE raw_afip_response IS NOT NULL) AS respuesta_guardada,
 count(*) FILTER (WHERE nullif(trim(error_message), '') IS NOT NULL) AS error_guardado
FROM invoices;
SELECT count(*) AS logs_heredados FROM logs_invoice;
SELECT count(*) AS errores,
 count(*) FILTER (WHERE resolved IS TRUE OR resolved_at IS NOT NULL
   OR nullif(btrim(resolved_by), '') IS NOT NULL
   OR nullif(btrim(resolution_notes), '') IS NOT NULL) AS resoluciones_con_datos
FROM error_logs;
