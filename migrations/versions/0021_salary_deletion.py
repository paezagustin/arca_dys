"""Conservar los pagos de sueldos retirados del listado."""
import sqlalchemy as sa
from alembic import op

revision = "0021_salary_deletion"
down_revision = "0020_credit_person_names"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column("salary_payments", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("LOCK TABLE salary_payments IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM salary_payments WHERE deleted_at IS NOT NULL)")):
        raise RuntimeError("Volver a la revisión anterior reactivaría pagos de sueldos eliminados")
    op.drop_column("salary_payments", "deleted_at")
