"""Cuentas de Fiados y diario inmutable; históricos sin atribuciones automáticas."""
from alembic import op
import sqlalchemy as sa

revision = "0017_credit_accounts"
down_revision = "0016_credit_deletion"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.create_table("credit_customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entry_key", sa.String(36), nullable=False, unique=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("alias", sa.String(80), nullable=False, server_default=""),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_credit_customer_name"),
        sa.CheckConstraint("version > 0 AND last_seq >= 0", name="ck_credit_customer_version"))
    op.create_table("credit_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("credit_customers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("account_seq", sa.Integer(), nullable=False),
        sa.Column("entry_key", sa.String(36), nullable=False, unique=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("delta", sa.Numeric(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("observation", sa.Text(), nullable=False, server_default=""),
        sa.Column("reversal_of", sa.Integer(), unique=True),
        sa.Column("actor", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("customer_id", "account_seq", name="uq_credit_movement_sequence"),
        sa.UniqueConstraint("id", "customer_id", name="uq_credit_movement_owner"),
        sa.ForeignKeyConstraint(["reversal_of", "customer_id"], ["credit_movements.id", "credit_movements.customer_id"],
                                name="fk_credit_reversal_owner", ondelete="RESTRICT"),
        sa.CheckConstraint("delta <> 0 AND delta = trunc(delta) AND abs(delta) < 10000000000000000", name="ck_credit_movement_integer"),
        sa.CheckConstraint("account_seq > 0", name="ck_credit_movement_sequence"),
        sa.CheckConstraint("(kind IN ('purchase','opening') AND delta > 0 AND reversal_of IS NULL) OR "
                           "(kind = 'payment' AND delta < 0 AND reversal_of IS NULL) OR "
                           "(kind = 'reversal' AND reversal_of IS NOT NULL AND reversal_of <> id)",
                           name="ck_credit_movement_kind"))
    op.create_index("ix_credit_movement_date", "credit_movements", ["customer_id", "entry_date", "id"])
    op.create_table("credit_legacy_links",
        sa.Column("legacy_credit_id", sa.Integer(), sa.ForeignKey("customer_credits.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("entry_key", sa.String(36), nullable=False, unique=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("credit_customers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("opening_movement_id", sa.Integer(), unique=True),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["opening_movement_id", "customer_id"],
            ["credit_movements.id", "credit_movements.customer_id"], name="fk_credit_legacy_owner", ondelete="RESTRICT"))
    # La revisión solo agrega estructura: ningún nombre identifica automáticamente a alguien.
    op.execute("""CREATE FUNCTION protect_credit_journal() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'El historial de Fiados es inmutable; registrar una anulación'
        USING ERRCODE = '23514'; END $$""")
    for table in ("credit_movements", "credit_legacy_links"):
        op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION protect_credit_journal()")
    op.execute("""CREATE FUNCTION protect_linked_legacy_credit() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF EXISTS (SELECT 1 FROM credit_legacy_links WHERE legacy_credit_id = OLD.id) THEN
            RAISE EXCEPTION 'El fiado anterior ya fue vinculado; conservar su registro original'
            USING ERRCODE = '23514';
          END IF;
          IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER linked_legacy_credit_immutable BEFORE UPDATE OR DELETE ON customer_credits
        FOR EACH ROW EXECUTE FUNCTION protect_linked_legacy_credit()""")


def downgrade():
    raise RuntimeError("Restaurar un respaldo verificado; no descartar cuentas ni movimientos de Fiados")
