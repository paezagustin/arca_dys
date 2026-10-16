"""Fecha de pago de fiados sin inventar fechas para registros anteriores."""
from alembic import op
import sqlalchemy as sa

revision = "0012_credit_paid_date"
down_revision = "0011_sales_payroll_credits"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("customer_credits", sa.Column("paid_date", sa.Date(), nullable=True))
    op.create_check_constraint("ck_credit_payment_date", "customer_credits", "paid OR paid_date IS NULL")


def downgrade():
    raise RuntimeError("Restaurar un backup verificado; no descartar fechas de pago de fiados")
