"""Gestión simple, sin historial de correcciones; sesiones locales anónimas."""
from alembic import op
import sqlalchemy as sa

revision = "0010_simple_business"
down_revision = "0009_reports"
branch_labels = None
depends_on = None


def upgrade():
    db = op.get_bind()
    db.execute(sa.text("LOCK TABLE business_entries IN ACCESS EXCLUSIVE MODE"))
    if db.execute(sa.text("SELECT count(*) FROM business_entries WHERE kind='income'")).scalar_one():
        raise RuntimeError("Existen otros ingresos: reclasificarlos antes de migrar; no se eliminaron registros")
    op.add_column("business_entries", sa.Column("expense_type", sa.String(10)))
    db.execute(sa.text("""UPDATE business_entries SET expense_type=CASE
        WHEN upper(trim(classification))='COMPRAS EN BLANCO' THEN 'white'
        WHEN upper(trim(classification))='COMPRAS EN NEGRO' THEN 'black' END
        WHERE kind='expense'"""))
    # Mantener las descripciones manuales anteriores sin inventar un tipo de egreso.
    db.execute(sa.text("""UPDATE business_entries SET description=concat_ws(' · ',
        nullif(description,''), nullif(category,'')) WHERE kind='expense'
        AND category NOT IN ('Compras','Ventas','') AND category IS DISTINCT FROM description"""))
    op.drop_constraint("ck_business_kind", "business_entries")
    op.create_check_constraint("ck_business_kind", "business_entries", "kind IN ('sale','expense')")
    op.create_check_constraint("ck_business_expense_type", "business_entries",
        "expense_type IS NULL OR (kind='expense' AND expense_type IN ('white','black'))")
    for column in ("medium", "classification", "category"):
        op.drop_column("business_entries", column)
    op.drop_table("business_changes")
    op.drop_table("settings_changes")
    db.execute(sa.text("UPDATE import_rows SET resolution=resolution::jsonb - 'history' WHERE resolution IS NOT NULL"))
    op.alter_column("web_sessions", "user_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("billing_previews", "user_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("billing_previews", sa.Column("session_hash", sa.String(64)))


def downgrade():
    raise RuntimeError("Restaurar un backup verificado; no se reconstruyen historiales ni clasificaciones eliminadas")
