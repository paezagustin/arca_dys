-- Operación puntual de ARCA-7. Por defecto se ensaya y revierte.
\set ON_ERROR_STOP on
\if :{?apply}
\else
    \set apply false
\endif

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL search_path TO public, pg_catalog;
LOCK TABLE suppliers, business_entries, import_supplier_maps IN SHARE ROW EXCLUSIVE MODE;

DO $merge$
DECLARE
    source suppliers%ROWTYPE;
    target suppliers%ROWTYPE;
    entries_before jsonb;
    aliases_before jsonb;
    moved_entries integer;
    moved_aliases integer;
BEGIN
    IF (SELECT array_agg(version_num) FROM alembic_version) IS DISTINCT FROM ARRAY['0014_credit_timestamps']::varchar[] THEN
        RAISE EXCEPTION 'La unificación requiere la revisión 0014_credit_timestamps';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE contype = 'f' AND confrelid = 'suppliers'::regclass
          AND (conrelid NOT IN ('business_entries'::regclass, 'import_supplier_maps'::regclass)
               OR confdeltype NOT IN ('a', 'r'))
    ) THEN
        RAISE EXCEPTION 'Hay una referencia inesperada a proveedores. Revisar antes de continuar';
    END IF;

    SELECT * INTO STRICT target FROM suppliers
    WHERE name_key IN ('cotillón alberto', 'cotillon alberto');
    IF lower(target.name) NOT IN ('cotillón alberto', 'cotillon alberto') THEN
        RAISE EXCEPTION 'El nombre del proveedor de destino no coincide';
    END IF;
    SELECT * INTO source FROM suppliers WHERE name_key = 'casa alberto';
    IF NOT FOUND THEN
        IF NOT target.active THEN
            RAISE EXCEPTION 'El proveedor de destino está archivado';
        END IF;
        RAISE NOTICE 'Casa Alberto ya está ausente. Destino activo con ID %', target.id;
        RETURN;
    END IF;
    IF lower(source.name) <> 'casa alberto' THEN
        RAISE EXCEPTION 'El nombre del proveedor de origen no coincide';
    END IF;
    IF (source.contact <> '' AND target.contact <> '' AND source.contact <> target.contact)
        OR (source.notes <> '' AND target.notes <> '' AND source.notes <> target.notes) THEN
        RAISE EXCEPTION 'Los proveedores tienen datos de contacto o notas diferentes. Resolverlos antes de unificar';
    END IF;

    -- Comparar cada movimiento y referencia, incluidos los egresos dados de baja.
    SELECT jsonb_agg(to_jsonb(e) - 'supplier_id' - 'version' ORDER BY e.id)
      INTO entries_before FROM business_entries e WHERE e.supplier_id IN (source.id, target.id);
    SELECT jsonb_agg(to_jsonb(m) - 'supplier_id' ORDER BY m.batch_id, m.label)
      INTO aliases_before FROM import_supplier_maps m WHERE m.supplier_id IN (source.id, target.id);

    UPDATE business_entries SET supplier_id = target.id, version = version + 1 WHERE supplier_id = source.id;
    GET DIAGNOSTICS moved_entries = ROW_COUNT;
    UPDATE import_supplier_maps SET supplier_id = target.id WHERE supplier_id = source.id;
    GET DIAGNOSTICS moved_aliases = ROW_COUNT;
    UPDATE suppliers SET active = true, contact = coalesce(nullif(contact, ''), source.contact),
        notes = coalesce(nullif(notes, ''), source.notes), version = version + 1
    WHERE id = target.id AND (NOT active OR (contact = '' AND source.contact <> '') OR (notes = '' AND source.notes <> ''));

    IF entries_before IS DISTINCT FROM (
        SELECT jsonb_agg(to_jsonb(e) - 'supplier_id' - 'version' ORDER BY e.id)
        FROM business_entries e WHERE e.supplier_id = target.id
    ) OR aliases_before IS DISTINCT FROM (
        SELECT jsonb_agg(to_jsonb(m) - 'supplier_id' ORDER BY m.batch_id, m.label)
        FROM import_supplier_maps m WHERE m.supplier_id = target.id
    ) THEN
        RAISE EXCEPTION 'No coinciden los movimientos o las asignaciones. Se revierte toda la operación';
    END IF;

    DELETE FROM suppliers WHERE id = source.id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'El proveedor de origen no se pudo retirar';
    END IF;
    RAISE NOTICE 'Origen %, destino %, movimientos reasignados %, asignaciones conservadas %',
        source.id, target.id, moved_entries, moved_aliases;
END;
$merge$;

\if :apply
    COMMIT;
\else
    ROLLBACK;
\endif
