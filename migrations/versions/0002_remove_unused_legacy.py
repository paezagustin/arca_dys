"""Retira estructuras sin datos confirmadas por el usuario.

No editar el baseline: las bases existentes se adoptan primero como 0001_legacy.
La comprobación y el DDL comparten transacción y bloqueo para evitar pérdida de datos.
"""
from alembic import context, op
import sqlalchemy as sa

revision = "0002_cleanup"
down_revision = "0001_legacy"
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        raise RuntimeError("0002_cleanup requiere conexión para verificar que no elimina datos")
    connection = op.get_bind()
    connection.execute(sa.text(
        "LOCK TABLE error_logs, logs_invoice, payments IN ACCESS EXCLUSIVE MODE"
    ))
    checks = {
        "logs_invoice": "SELECT EXISTS (SELECT 1 FROM logs_invoice)",
        "payments.id_arca": """SELECT EXISTS (SELECT 1 FROM payments
            WHERE nullif(btrim(id_arca), '') IS NOT NULL)""",
        "error_logs.resolution": """SELECT EXISTS (SELECT 1 FROM error_logs
            WHERE resolved IS TRUE OR resolved_at IS NOT NULL
            OR nullif(btrim(resolved_by), '') IS NOT NULL
            OR nullif(btrim(resolution_notes), '') IS NOT NULL)""",
    }
    for name, query in checks.items():
        if connection.execute(sa.text(query)).scalar_one():
            raise RuntimeError(
                f"0002_cleanup detenida: {name} contiene información. "
                "Conservarla y revisar la migración antes de continuar."
            )
    for column in ["resolved", "resolved_at", "resolved_by", "resolution_notes"]:
        op.drop_column("error_logs", column)
    op.drop_table("logs_invoice")
    op.drop_column("payments", "id_arca")


def downgrade():
    # Se reponen estructuras vacías; el upgrade solo acepta valores sin información.
    op.add_column("payments", sa.Column("id_arca", sa.String(200)))
    op.create_table("logs_invoice",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("error", sa.String(300), nullable=False),
        sa.Column("created_at", sa.DateTime()))
    op.create_index("ix_logs_invoice_id", "logs_invoice", ["id"])
    op.add_column("error_logs", sa.Column("resolved", sa.Boolean()))
    op.add_column("error_logs", sa.Column("resolved_at", sa.DateTime()))
    op.add_column("error_logs", sa.Column("resolved_by", sa.String(100)))
    op.add_column("error_logs", sa.Column("resolution_notes", sa.Text()))
