"""Correcciones trazables y baja lógica de movimientos; celular por persona."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0018_credit_updates"
down_revision = "0017_credit_accounts"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column("credit_customers", sa.Column("phone", sa.String(15), nullable=False, server_default=""))
    op.add_column("credit_movements", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("credit_movements", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    for name, length in (("change_key",36),("change_hash",64),("changed_by",80)):
        op.add_column("credit_movements", sa.Column(name, sa.String(length)))
    op.create_table("credit_movement_changes",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("movement_id",sa.Integer(),sa.ForeignKey("credit_movements.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("entry_key",sa.String(36),nullable=False,unique=True),
        sa.Column("payload_hash",sa.String(64),nullable=False),
        sa.Column("before",JSONB(),nullable=False),sa.Column("after",JSONB(),nullable=False),
        sa.Column("actor",sa.String(80),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.execute('''CREATE OR REPLACE FUNCTION protect_credit_journal() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_TABLE_NAME <> 'credit_movements' OR TG_OP <> 'UPDATE' THEN
          RAISE EXCEPTION 'Conservar el historial de Fiados' USING ERRCODE='23514';
        END IF;
        IF OLD.deleted_at IS NOT NULL OR OLD.kind NOT IN ('purchase','payment')
           OR EXISTS (SELECT 1 FROM credit_movements WHERE reversal_of=OLD.id)
           OR NEW.version <> OLD.version+1 OR NEW.change_key IS NULL
           OR NEW.change_hash IS NULL OR NEW.changed_by IS NULL
           OR (to_jsonb(NEW) - ARRAY['delta','entry_date','observation','version','deleted_at','change_key','change_hash','changed_by'])
              IS DISTINCT FROM
              (to_jsonb(OLD) - ARRAY['delta','entry_date','observation','version','deleted_at','change_key','change_hash','changed_by']) THEN
          RAISE EXCEPTION 'Corrección de Fiados inválida u obsoleta' USING ERRCODE='23514';
        END IF;
        INSERT INTO credit_movement_changes(movement_id,entry_key,payload_hash,"before","after",actor)
          VALUES(OLD.id,NEW.change_key,NEW.change_hash,to_jsonb(OLD),to_jsonb(NEW),NEW.changed_by);
        RETURN NEW;
      END $$''')
    op.execute('''CREATE TRIGGER credit_changes_immutable BEFORE UPDATE OR DELETE ON credit_movement_changes
        FOR EACH ROW EXECUTE FUNCTION protect_credit_journal()''')


def downgrade():
    raise RuntimeError("Restaurar un respaldo verificado; conservar correcciones y celulares")
