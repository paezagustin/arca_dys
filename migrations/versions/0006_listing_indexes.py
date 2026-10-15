"""Índices de filtros/listados y cola, sin modificar registros."""
from alembic import op

revision = "0006_listings"
down_revision = "0005_settings"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_payments_billing_date", "payments", ["status", "registered_arca", "date_approved", "id"])
    op.create_index("ix_invoices_date", "invoices", ["invoice_date", "id"])
    op.create_index("ix_billing_state", "billing_requests", ["state", "created_at"])
    op.create_index("ix_billing_date", "billing_requests", ["invoice_date", "created_at", "id"])


def downgrade():
    op.drop_index("ix_billing_date", table_name="billing_requests")
    op.drop_index("ix_billing_state", table_name="billing_requests")
    op.drop_index("ix_invoices_date", table_name="invoices")
    op.drop_index("ix_payments_billing_date", table_name="payments")
