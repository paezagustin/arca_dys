-- SOLO mantenimiento manual, web detenida y backup comprobado.
-- Ejecutar con psql -X --single-transaction -v ON_ERROR_STOP=1.
-- No borra cobros/facturas/configuracion ni modifica esquema o certificados.
SET LOCAL lock_timeout = '5s';

DO $$
BEGIN
    IF to_regclass('public.alembic_version') IS NULL THEN
        RAISE EXCEPTION 'Migrar primero: falta alembic_version';
    END IF;
    IF (SELECT count(*) FROM public.alembic_version) <> 1
       OR (SELECT version_num FROM public.alembic_version LIMIT 1) <> '0013_mp_identity' THEN
        RAISE EXCEPTION 'Se requiere 0013_mp_identity; no se limpio ningun dato';
    END IF;
END $$;

-- Lista cerrada y RESTRICT: una FK inesperada bloquea todo, nunca amplia el borrado.
TRUNCATE TABLE public.import_rows, public.import_supplier_maps, public.import_batches,
    public.business_entries, public.suppliers, public.salary_payments,
    public.customer_credits RESTART IDENTITY RESTRICT;

SELECT 'proveedores' AS tabla, count(*) AS registros FROM public.suppliers
UNION ALL SELECT 'ventas y egresos', count(*) FROM public.business_entries
UNION ALL SELECT 'importaciones', count(*) FROM public.import_batches
UNION ALL SELECT 'sueldos', count(*) FROM public.salary_payments
UNION ALL SELECT 'fiados', count(*) FROM public.customer_credits;
