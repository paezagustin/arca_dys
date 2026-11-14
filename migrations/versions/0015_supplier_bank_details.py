"""Agregar CBU y alias opcionales a proveedores."""

from alembic import op
import sqlalchemy as sa

revision = "0015_supplier_bank_details"
down_revision = "0014_credit_timestamps"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column("suppliers", sa.Column("cbu", sa.String(22), nullable=True))
    op.add_column("suppliers", sa.Column("alias", sa.String(20), nullable=True))


def downgrade():
    raise RuntimeError("Conservar los datos bancarios antes de volver a una revisión anterior")
