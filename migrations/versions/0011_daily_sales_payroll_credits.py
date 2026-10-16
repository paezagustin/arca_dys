"""Desglose de caja, pagos de sueldos y fiados independientes."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_sales_payroll_credits"
down_revision = "0010_simple_business"
branch_labels = None
depends_on = None

BALANCE_CHECK = """(cash_amount IS NULL AND mp_amount IS NULL) OR
    (kind='sale' AND cash_amount IS NOT NULL AND mp_amount IS NOT NULL
     AND cash_amount>=0 AND mp_amount>=0 AND amount=cash_amount+mp_amount)"""


def upgrade():
    op.add_column("business_entries", sa.Column("cash_amount", sa.Numeric(18, 2)))
    op.add_column("business_entries", sa.Column("mp_amount", sa.Numeric(18, 2)))
    op.create_check_constraint("ck_business_sale_breakdown", "business_entries", BALANCE_CHECK)
    employee = postgresql.ENUM("Francisco", "Juan Cruz", name="salary_employee", create_type=False)
    medium = postgresql.ENUM("efectivo", "mercado pago", name="salary_medium", create_type=False)
    employee.create(op.get_bind())
    medium.create(op.get_bind())
    op.create_table("salary_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entry_key", sa.String(36), nullable=False, unique=True),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("employee", employee, nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("medium", medium, nullable=False, server_default="mercado pago"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("amount>0", name="ck_salary_amount"))
    op.create_index("ix_salary_date", "salary_payments", ["entry_date", "id"])
    op.create_index("ix_salary_employee_date", "salary_payments", ["employee", "entry_date"])
    op.create_table("customer_credits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entry_key", sa.String(36), nullable=False, unique=True),
        sa.Column("customer", sa.String(150), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("observation", sa.Text(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("paid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("amount>0", name="ck_credit_amount"))
    op.create_index("ix_credit_paid_date", "customer_credits", ["paid", "entry_date", "id"])


def downgrade():
    raise RuntimeError("Restaurar un backup verificado; no eliminar caja, sueldos ni fiados con datos")
