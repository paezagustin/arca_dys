"""Guardar la hora de alta y pago de Fiados desde esta revisión."""

from alembic import op
import sqlalchemy as sa

revision = "0014_credit_timestamps"
down_revision = "0013_mp_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column("customer_credits", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("customer_credits", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_credit_payment_timestamp",
        "customer_credits",
        "paid_at IS NULL OR (paid AND paid_date IS NOT NULL AND "
        "paid_date = CAST(paid_at AT TIME ZONE 'America/Argentina/Buenos_Aires' AS date))",
    )


def downgrade():
    raise RuntimeError("Restaurar un backup verificado para volver a una revisión anterior")
