"""Conservar los fiados retirados del listado."""

import sqlalchemy as sa
from alembic import op

revision = "0016_credit_deletion"
down_revision = "0015_supplier_bank_details"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column("customer_credits", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("LOCK TABLE customer_credits IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM customer_credits WHERE deleted_at IS NOT NULL)")):
        raise RuntimeError("Volver a la revisión anterior reactivaría fiados eliminados")
    op.drop_column("customer_credits", "deleted_at")
