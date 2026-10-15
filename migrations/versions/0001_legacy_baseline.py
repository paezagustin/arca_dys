"""Esquema inicial contrastado con exportación Adminer PostgreSQL 17.8.

No elimina campos heredados ni modifica importes. En una base existente se
adopta con app.manage adopt-legacy, luego de comprobar su estructura.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_legacy"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("error_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("error_type", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.String(100)), sa.Column("raw_data", sa.JSON()),
        sa.Column("resolved", sa.Boolean()), sa.Column("resolved_at", sa.DateTime()),
        sa.Column("resolved_by", sa.String(100)), sa.Column("resolution_notes", sa.Text()))
    op.create_table("invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_number", sa.String(300)), sa.Column("total_amount", sa.Float()),
        sa.Column("status", sa.String(100)), sa.Column("error_message", sa.String(200)),
        sa.Column("cae", sa.String(300)), sa.Column("cae_due_date", sa.Date()),
        sa.Column("invoice_date", sa.Date()), sa.Column("pdf_url", sa.String(300)),
        sa.Column("raw_afip_response", sa.JSON()), sa.Column("created_at", sa.DateTime()))
    op.create_index("invoices_invoice_number_key", "invoices", ["invoice_number"], unique=True)
    op.create_table("logs_invoice",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("error", sa.String(300), nullable=False), sa.Column("created_at", sa.DateTime()))
    op.create_table("payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("id_payment_mp", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False), sa.Column("status_detail", sa.String(150)),
        sa.Column("mont", sa.Float()), sa.Column("type_of_paid", sa.String(50)),
        sa.Column("date_approved", sa.DateTime()), sa.Column("bill", sa.Boolean()),
        sa.Column("registered_arca", sa.Boolean()), sa.Column("id_arca", sa.String(200)),
        sa.Column("raw_json", sa.JSON()), sa.Column("created_at", sa.DateTime()))
    op.create_index("ix_payments_id_payment_mp", "payments", ["id_payment_mp"])
    op.create_table("payment_invoice",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False))
    for table in ["error_logs", "invoices", "logs_invoice", "payments", "payment_invoice"]:
        op.create_index(f"ix_{table}_id", table, ["id"])


def downgrade():
    raise RuntimeError("El baseline no se elimina automáticamente. Restaurar un backup en una base separada.")
