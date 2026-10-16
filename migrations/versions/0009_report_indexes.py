"""Índices de agregación por período; sin cambios de datos."""
from alembic import op
revision = "0009_reports"
down_revision = "0008_import"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_business_kind_date", "business_entries", ["kind", "active", "entry_date"])
    op.create_index("ix_business_supplier_date", "business_entries", ["supplier_id", "entry_date"])
    op.create_index("ix_payments_status_date", "payments", ["status", "date_approved"])


def downgrade():
    op.drop_index("ix_payments_status_date", table_name="payments")
    op.drop_index("ix_business_supplier_date", table_name="business_entries")
    op.drop_index("ix_business_kind_date", table_name="business_entries")
