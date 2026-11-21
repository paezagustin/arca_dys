"""Inicial por palabra en personas; conserva identidades y referencias."""
from alembic import op
import sqlalchemy as sa
import unicodedata

revision = "0020_credit_person_names"
down_revision = "0019_credit_local_phone"
branch_labels = None
depends_on = None


def upgrade():
    db = op.get_bind()
    db.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
    db.execute(sa.text("LOCK TABLE credit_customers IN SHARE ROW EXCLUSIVE MODE"))
    for row in db.execute(sa.text("SELECT id,name,alias FROM credit_customers ORDER BY id")).mappings().all():
        name = " ".join(word.capitalize() for word in row["name"].split())
        search = " ".join("".join(c for c in unicodedata.normalize("NFKD", name + " " + row["alias"])
                                  if not unicodedata.combining(c)).casefold().split())
        db.execute(sa.text("UPDATE credit_customers SET name=:name,search_text=:search,version=version+1 WHERE id=:id AND name<>:name"),
                   {"id":row["id"], "name":name, "search":search})


def downgrade():
    raise RuntimeError("Restaurar un respaldo verificado; no inventar la escritura anterior del nombre")
