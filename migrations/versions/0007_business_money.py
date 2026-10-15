"""Gestión y conversión monetaria conciliada, conservando la representación original."""
from alembic import op
import sqlalchemy as sa

revision = "0007_business"
down_revision = "0006_listings"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    connection.execute(sa.text("LOCK TABLE payments, invoices IN ACCESS EXCLUSIVE MODE"))
    for table, column in (("payments", "mont"), ("invoices", "total_amount")):
        # Solo tolerar ruido binario menor a una millonésima de peso, nunca medio centavo.
        bad = connection.execute(sa.text(f"""SELECT id FROM {table} WHERE {column} IS NOT NULL AND
            CASE WHEN {column}::text IN ('NaN','Infinity','-Infinity') THEN true
            ELSE abs({column}::numeric) >= 10000000000000000
              OR abs({column}::numeric - round({column}::numeric,2)) > 0.000001 END LIMIT 1""")).scalar()
        if bad is not None:
            raise RuntimeError(f"Conversión monetaria detenida: revisar {table} id {bad}; no se modificaron datos")
    op.create_table("money_migration_audit", sa.Column("table_name", sa.String(40), primary_key=True),
        sa.Column("record_id", sa.Integer(), primary_key=True), sa.Column("original_text", sa.String(100)),
        sa.Column("converted", sa.Numeric(18, 2)))
    for table, column in (("payments", "mont"), ("invoices", "total_amount")):
        connection.execute(sa.text(f"INSERT INTO money_migration_audit SELECT '{table}', id, {column}::text, round({column}::numeric,2) FROM {table}"))
        op.alter_column(table, column, type_=sa.Numeric(18, 2), existing_nullable=True,
                        postgresql_using=f"round({column}::numeric,2)")
        different = connection.execute(sa.text(f"""SELECT count(*) FROM {table} t FULL JOIN
            (SELECT * FROM money_migration_audit WHERE table_name='{table}') a ON a.record_id=t.id
            WHERE t.id IS NULL OR a.record_id IS NULL OR t.{column} IS DISTINCT FROM a.converted""")).scalar_one()
        if different:
            raise RuntimeError("La conciliación monetaria no coincide; transacción cancelada")
    op.create_table("suppliers", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False), sa.Column("name_key", sa.String(150), nullable=False, unique=True),
        sa.Column("contact", sa.String(200), nullable=False), sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False), sa.Column("version", sa.Integer(), nullable=False))
    op.create_table("business_entries", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entry_key", sa.String(100), nullable=False, unique=True), sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False), sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("category", sa.String(100), nullable=False), sa.Column("medium", sa.String(30), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id")), sa.Column("description", sa.Text(), nullable=False),
        sa.Column("classification", sa.String(100), nullable=False), sa.Column("origin", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False), sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('sale','income','expense')", name="ck_business_kind"),
        sa.CheckConstraint("amount >= 0 AND (kind = 'sale' OR amount > 0)", name="ck_business_amount"),
        sa.CheckConstraint("supplier_id IS NULL OR kind = 'expense'", name="ck_business_supplier"))
    op.create_index("ix_business_date", "business_entries", ["entry_date", "id"])
    op.create_index("uq_business_daily_sale", "business_entries", ["entry_date"], unique=True,
                    postgresql_where=sa.text("kind = 'sale' AND active"))
    op.create_table("business_changes", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity", sa.String(20), nullable=False), sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(80), nullable=False), sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("previous", sa.JSON()), sa.Column("current", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_business_change_entity", "business_changes", ["entity", "entity_id", "id"])


def downgrade():
    raise RuntimeError("No se elimina gestión ni se vuelve a Float automáticamente; restaurar una copia verificada")
