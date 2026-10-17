"""Identidad MP única sin consolidar ni modificar filas históricas repetidas."""
from alembic import op
import sqlalchemy as sa

revision = "0013_mp_identity"
down_revision = "0012_credit_paid_date"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    connection.execute(sa.text("LOCK TABLE payments IN ACCESS EXCLUSIVE MODE"))
    op.create_table("mp_payment_identities",
        sa.Column("id_payment_mp", sa.String(50), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="CASCADE"), unique=True),
        sa.Column("legacy_duplicate", sa.Boolean(), nullable=False),
        sa.CheckConstraint("(legacy_duplicate AND payment_id IS NULL) OR (NOT legacy_duplicate AND payment_id IS NOT NULL)",
                           name="ck_mp_identity_mapping"))
    connection.execute(sa.text("""INSERT INTO mp_payment_identities
        SELECT id_payment_mp, CASE WHEN count(*) = 1 THEN min(id) END, count(*) > 1
        FROM payments GROUP BY id_payment_mp"""))
    op.drop_index("ix_payments_id_payment_mp", table_name="payments")
    op.create_index("ix_payments_id_payment_mp", "payments", ["id_payment_mp"])
    op.create_table("mp_legacy_payment_snapshots",
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), primary_key=True),
        sa.Column("snapshot", sa.JSON(), nullable=False))
    connection.execute(sa.text("INSERT INTO mp_legacy_payment_snapshots SELECT id, row_to_json(p) FROM payments p"))
    op.add_column("mp_events", sa.Column("resource_responses", sa.JSON()))
    op.add_column("payment_changes", sa.Column("previous_data", sa.JSON()))
    op.create_table("mp_legacy_transitions",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("source_revision", sa.String(32), nullable=False),
        sa.Column("target_revision", sa.String(32), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False))
    # La PK de identidades arbitra también INSERT directos/concurrentes. El trigger
    # se ejecuta después de asignar el ID interno, dentro de la misma transacción.
    connection.exec_driver_sql("""
        CREATE FUNCTION mp_register_payment_identity() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            INSERT INTO mp_payment_identities VALUES (NEW.id_payment_mp, NEW.id, false)
                ON CONFLICT (id_payment_mp) DO NOTHING;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'La identidad MP ya existe; conservar su historial'
                    USING ERRCODE = '23505';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER mp_register_payment_identity AFTER INSERT ON payments
            FOR EACH ROW EXECUTE FUNCTION mp_register_payment_identity();
        CREATE FUNCTION mp_protect_payment_history() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'UPDATE' AND NEW.id_payment_mp IS DISTINCT FROM OLD.id_payment_mp THEN
                RAISE EXCEPTION 'La identidad MP es inmutable' USING ERRCODE = '23514';
            END IF;
            IF EXISTS (SELECT 1 FROM mp_payment_identities
                       WHERE id_payment_mp = OLD.id_payment_mp AND legacy_duplicate) THEN
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'Historico MP repetido protegido' USING ERRCODE = '23514';
                ELSIF row_to_json(NEW)::text IS DISTINCT FROM row_to_json(OLD)::text THEN
                    RAISE EXCEPTION 'Historico MP repetido protegido' USING ERRCODE = '23514';
                END IF;
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER mp_protect_payment_history BEFORE UPDATE OR DELETE ON payments
            FOR EACH ROW EXECUTE FUNCTION mp_protect_payment_history();
    """)


def downgrade():
    raise RuntimeError("No se descarta identidad ni evidencia MP; restaurar una copia verificada")
