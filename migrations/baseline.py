"""Metadatos congelados del esquema Adminer 17.8; independientes del ORM futuro."""
import sqlalchemy as sa


def legacy_metadata():
    metadata = sa.MetaData()
    def table(name, columns):
        value = sa.Table(name, metadata, sa.Column("id", sa.Integer(), primary_key=True), *columns)
        sa.Index(f"ix_{name}_id", value.c.id)
        return value
    table("error_logs", [sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False), sa.Column("error_type", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False), sa.Column("resource_id", sa.String(100)),
        sa.Column("raw_data", sa.JSON()), sa.Column("resolved", sa.Boolean()),
        sa.Column("resolved_at", sa.DateTime()), sa.Column("resolved_by", sa.String(100)),
        sa.Column("resolution_notes", sa.Text())])
    invoices = table("invoices", [sa.Column("invoice_number", sa.String(300)),
        sa.Column("total_amount", sa.Float()), sa.Column("status", sa.String(100)),
        sa.Column("error_message", sa.String(200)), sa.Column("cae", sa.String(300)),
        sa.Column("cae_due_date", sa.Date()), sa.Column("invoice_date", sa.Date()),
        sa.Column("pdf_url", sa.String(300)), sa.Column("raw_afip_response", sa.JSON()),
        sa.Column("created_at", sa.DateTime())])
    sa.Index("invoices_invoice_number_key", invoices.c.invoice_number, unique=True)
    table("logs_invoice", [sa.Column("error", sa.String(300), nullable=False), sa.Column("created_at", sa.DateTime())])
    payments = table("payments", [sa.Column("id_payment_mp", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False), sa.Column("status_detail", sa.String(150)),
        sa.Column("mont", sa.Float()), sa.Column("type_of_paid", sa.String(50)),
        sa.Column("date_approved", sa.DateTime()), sa.Column("bill", sa.Boolean()),
        sa.Column("registered_arca", sa.Boolean()), sa.Column("id_arca", sa.String(200)),
        sa.Column("raw_json", sa.JSON()), sa.Column("created_at", sa.DateTime())])
    sa.Index("ix_payments_id_payment_mp", payments.c.id_payment_mp)
    table("payment_invoice", [sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False)])
    return metadata
