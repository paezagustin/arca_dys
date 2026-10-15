"""Configuración auditable, acceso y confirmaciones de facturación."""
from alembic import op
import sqlalchemy as sa

revision = "0005_settings"
down_revision = "0004_mp"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(80), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False), sa.Column("role", sa.String(20), nullable=False))
    op.create_table("web_sessions", sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("csrf_token", sa.String(64), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("login_throttles", sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("failures", sa.Integer(), nullable=False), sa.Column("blocked_until", sa.DateTime(timezone=True)))
    op.create_table("business_settings", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("values", sa.JSON(), nullable=False), sa.Column("version", sa.Integer(), nullable=False))
    op.create_table("settings_changes", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False), sa.Column("previous", sa.JSON(), nullable=False),
        sa.Column("current", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("billing_previews", sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False), sa.Column("payment_ids", sa.JSON(), nullable=False),
        sa.Column("total", sa.Numeric(18, 2), nullable=False), sa.Column("settings_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("billing_requests.id")))


def downgrade():
    raise RuntimeError("Configuración, usuarios y auditoría no se eliminan automáticamente.")
