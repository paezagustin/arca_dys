"""Conservar estados del catálogo y el punto de sincronización incremental."""
import sqlalchemy as sa
from alembic import op

revision = "0023_restock_catalog"
down_revision = "0022_restock"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column("restock_products", sa.Column("catalog_product_active", sa.Boolean))
    op.add_column("restock_products", sa.Column("catalog_category_id", sa.BigInteger))
    op.add_column("restock_products", sa.Column("catalog_category_name", sa.String(100)))
    op.add_column("restock_products", sa.Column("catalog_category_active", sa.Boolean))
    op.add_column("restock_order_lines", sa.Column("product_description", sa.Text))
    op.add_column("restock_catalog_sync", sa.Column("watermark", sa.DateTime(timezone=True)))
    op.add_column("restock_catalog_sync", sa.Column("last_full_sync_at", sa.DateTime(timezone=True)))


def downgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("LOCK TABLE restock_products, restock_order_lines, restock_catalog_sync IN ACCESS EXCLUSIVE MODE")
    connection = op.get_bind()
    if connection.scalar(sa.text("""
        SELECT EXISTS (SELECT 1 FROM restock_products WHERE catalog_product_active IS NOT NULL
            OR catalog_category_id IS NOT NULL OR catalog_category_name IS NOT NULL OR catalog_category_active IS NOT NULL)
        OR EXISTS (SELECT 1 FROM restock_order_lines WHERE product_description IS NOT NULL)
        OR EXISTS (SELECT 1 FROM restock_catalog_sync WHERE watermark IS NOT NULL OR last_full_sync_at IS NOT NULL)
    """)):
        raise RuntimeError("La reversión descartaría datos del catálogo o de pedidos. Conservá la revisión 0023.")
    op.drop_column("restock_catalog_sync", "last_full_sync_at")
    op.drop_column("restock_catalog_sync", "watermark")
    op.drop_column("restock_order_lines", "product_description")
    for column in ("catalog_category_active", "catalog_category_name", "catalog_category_id", "catalog_product_active"):
        op.drop_column("restock_products", column)
