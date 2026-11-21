"""Celular argentino: área y número; conservar ante formatos inesperados."""
from alembic import op

revision = "0019_credit_local_phone"
down_revision = "0018_credit_updates"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("LOCK TABLE credit_customers IN SHARE ROW EXCLUSIVE MODE")
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM credit_customers WHERE phone <> ''
        AND phone !~ '^[1-9][0-9]{9}$' AND phone !~ '^549[1-9][0-9]{9}$') THEN
        RAISE EXCEPTION 'Revisar celulares anteriores: se conservaron sin convertir formatos ambiguos';
      END IF;
    END $$""")
    op.execute("UPDATE credit_customers SET phone=substring(phone FROM 4), version=version+1 WHERE phone ~ '^549[1-9][0-9]{9}$'")
    op.create_check_constraint("ck_credit_customer_phone", "credit_customers", "phone = '' OR phone ~ '^[1-9][0-9]{9}$'")


def downgrade():
    raise RuntimeError("Restaurar un respaldo verificado; no reinterpretar celulares guardados")
