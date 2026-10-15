"""Identidad externa única e inbox durable. No deduplica ni elimina datos heredados."""
from alembic import op
import sqlalchemy as sa

revision = "0004_mp"
down_revision = "0003_billing"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    connection.execute(sa.text("LOCK TABLE payments IN ACCESS EXCLUSIVE MODE"))
    if connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM payments GROUP BY id_payment_mp HAVING count(*) > 1)")).scalar_one():
        raise RuntimeError("Hay IDs MP duplicados heredados. Conservarlos y conciliar sus vínculos antes de migrar.")
    op.drop_index("ix_payments_id_payment_mp", table_name="payments")
    op.create_index("ix_payments_id_payment_mp", "payments", ["id_payment_mp"], unique=True)
    op.add_column("payments", sa.Column("provider_updated_at", sa.DateTime(timezone=True)))
    op.create_table("mp_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dedup_key", sa.String(64), unique=True, nullable=False),
        sa.Column("topic", sa.String(50), nullable=False),
        sa.Column("resource", sa.String(200), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False), sa.Column("state", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("error", sa.Text()),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)))
    op.create_index("ix_mp_events_queue", "mp_events", ["state", "next_attempt_at"])
    op.create_table("payment_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("mp_events.id"), nullable=False),
        sa.Column("previous_status", sa.String(50)), sa.Column("new_status", sa.String(50), nullable=False),
        sa.Column("provider_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    raise RuntimeError("El historial de notificaciones se conserva. Preparar una migración explícita para revertir.")
