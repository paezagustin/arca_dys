"""Lotes y filas trazables del Excel, sin modificar datos de gestión existentes."""
from alembic import op
import sqlalchemy as sa
revision = "0008_import"
down_revision = "0007_business"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("import_batches", sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dataset", sa.String(80), nullable=False), sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False), sa.Column("state", sa.String(20), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False), sa.Column("actor", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("dataset", "file_hash", name="uq_import_file"))
    op.create_table("import_rows", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("import_batches.id"), nullable=False),
        sa.Column("sheet", sa.String(80), nullable=False), sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("slot", sa.String(20), nullable=False), sa.Column("source_key", sa.String(64), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False), sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("raw", sa.JSON(), nullable=False), sa.Column("proposed", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False), sa.Column("issue", sa.String(500)),
        sa.Column("resolution", sa.JSON()), sa.Column("entry_id", sa.Integer(), sa.ForeignKey("business_entries.id")),
        sa.UniqueConstraint("batch_id", "sheet", "row_number", "slot", name="uq_import_row"))
    op.create_index("ix_import_rows_batch", "import_rows", ["batch_id", "state", "id"])
    op.create_index("ix_import_rows_source", "import_rows", ["source_key"])
    op.create_table("import_supplier_maps", sa.Column("batch_id", sa.String(36), sa.ForeignKey("import_batches.id"), primary_key=True),
        sa.Column("label", sa.String(200), primary_key=True), sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("actor", sa.String(80), nullable=False))


def downgrade():
    raise RuntimeError("Los originales y decisiones importadas se conservan; usar restauración verificada")
