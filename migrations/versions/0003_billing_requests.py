"""Solicitudes fiscales durables y proveedor simulado persistente."""
from alembic import op
import sqlalchemy as sa

revision = "0003_billing"
down_revision = "0002_cleanup"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invoices", sa.Column("fiscal_snapshot", sa.JSON()))
    op.create_table("billing_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(100), unique=True, nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("point", sa.Integer(), nullable=False),
        sa.Column("voucher_type", sa.Integer(), nullable=False),
        sa.Column("voucher_number", sa.Integer()),
        sa.Column("payment_ids", sa.JSON(), nullable=False),
        sa.Column("payment_snapshot", sa.JSON(), nullable=False),
        sa.Column("fiscal_snapshot", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON()), sa.Column("response", sa.JSON()), sa.Column("error", sa.Text()),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("billing_reservations",
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), primary_key=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("billing_requests.id"), nullable=False))
    op.create_table("simulated_vouchers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("point", sa.Integer(), nullable=False),
        sa.Column("voucher_type", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False), sa.Column("response", sa.JSON(), nullable=False),
        sa.UniqueConstraint("point", "voucher_type", "number", name="uq_simulated_voucher"))


def downgrade():
    # No descartar evidencia fiscal ni reservas por un rollback de aplicación.
    raise RuntimeError("0003_billing conserva evidencia fiscal. Restaurar una copia o preparar una migración explícita.")
