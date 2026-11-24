"""Productos, faltantes y pedidos a proveedores. Solo agrega tablas nuevas."""
import sqlalchemy as sa
from alembic import op

revision = "0022_restock"
down_revision = "0021_salary_deletion"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.create_table(
        "restock_products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("request_key", sa.String(36), unique=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("name_key", sa.Text, nullable=False),
        sa.Column("search_text", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("presentation", sa.String(160), nullable=False),
        sa.Column("barcode", sa.String(100), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("source", sa.String(40)),
        sa.Column("external_id", sa.String(160)),
        sa.Column("catalog_status", sa.String(10)),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source", "external_id", name="uq_restock_product_source"),
        sa.CheckConstraint(
            "(source IS NULL AND external_id IS NULL AND catalog_status IS NULL) OR "
            "(source IS NOT NULL AND length(source) > 0 AND external_id IS NOT NULL AND length(external_id) > 0 "
            "AND catalog_status IS NOT NULL AND catalog_status IN ('active','inactive','missing'))",
            name="ck_restock_product_source",
        ),
    )
    op.create_index("ix_restock_product_name", "restock_products", ["name_key", "id"])
    op.create_index("ix_restock_product_barcode", "restock_products", ["barcode"])
    op.create_table(
        "restock_product_suppliers",
        sa.Column("product_id", sa.Integer, sa.ForeignKey("restock_products.id"), primary_key=True),
        sa.Column("supplier_id", sa.Integer, sa.ForeignKey("suppliers.id"), primary_key=True),
        sa.Column("preferred", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_restock_products_by_supplier", "restock_product_suppliers", ["supplier_id", "product_id"])
    op.create_index("uq_restock_preferred_supplier", "restock_product_suppliers", ["product_id"], unique=True,
                    postgresql_where=sa.text("preferred"))

    op.create_table(
        "restock_needs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("request_key", sa.String(36), nullable=False, unique=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("restock_products.id"), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3)),
        sa.Column("unit", sa.String(160), nullable=False),
        sa.Column("notes", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('pending','ordered','received','cancelled')", name="ck_restock_need_status"),
        sa.CheckConstraint("quantity > 0", name="ck_restock_need_quantity"),
    )
    op.create_index("uq_restock_active_need", "restock_needs", ["product_id"], unique=True,
                    postgresql_where=sa.text("status IN ('pending','ordered')"))
    op.create_index("ix_restock_need_status_date", "restock_needs", ["status", "created_at", "id"])
    op.create_index("ix_restock_need_product", "restock_needs", ["product_id"])

    op.create_table(
        "restock_orders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("request_key", sa.String(36), nullable=False, unique=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("supplier_id", sa.Integer, sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("supplier_name", sa.String(150), nullable=False),
        sa.Column("notes", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_restock_order_date", "restock_orders", ["created_at", "id"])
    op.create_index("ix_restock_order_supplier_date", "restock_orders", ["supplier_id", "created_at", "id"])
    op.create_table(
        "restock_order_lines",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("restock_orders.id"), nullable=False),
        sa.Column("need_id", sa.Integer, sa.ForeignKey("restock_needs.id"), nullable=False),
        sa.Column("product_name", sa.String(180), nullable=False),
        sa.Column("presentation", sa.String(160), nullable=False),
        sa.Column("barcode", sa.String(100), nullable=False),
        sa.Column("search_text", sa.Text, nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3)),
        sa.Column("unit", sa.String(160), nullable=False),
        sa.Column("notes", sa.Text, nullable=False),
        sa.Column("outcome", sa.String(11), nullable=False),
        sa.Column("receipt_notes", sa.Text, nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("order_id", "need_id", name="uq_restock_order_need"),
        sa.CheckConstraint("quantity > 0", name="ck_restock_line_quantity"),
        sa.CheckConstraint(
            "(outcome = 'waiting' AND resolved_at IS NULL) OR "
            "(outcome IN ('received','undelivered','cancelled') AND resolved_at IS NOT NULL)",
            name="ck_restock_line_resolution",
        ),
    )
    op.create_index("uq_restock_waiting_line", "restock_order_lines", ["need_id"], unique=True,
                    postgresql_where=sa.text("outcome = 'waiting'"))
    op.create_index("ix_restock_line_need", "restock_order_lines", ["need_id"])
    op.create_table(
        "restock_catalog_sync",
        sa.Column("source", sa.String(40), primary_key=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text),
    )


def downgrade():
    tables = ("restock_order_lines", "restock_orders", "restock_needs", "restock_product_suppliers",
              "restock_products", "restock_catalog_sync")
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute(f"LOCK TABLE {', '.join(tables)} IN ACCESS EXCLUSIVE MODE")
    for table in tables:
        if op.get_bind().scalar(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")):
            raise RuntimeError("La reversión descartaría registros de Faltantes. Conservá la revisión 0022.")
    for table in tables:
        op.drop_table(table)
