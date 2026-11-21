"""Carga explícita e idempotente de Fiados ficticios en el entorno aislado local."""
import argparse
import os
from uuid import NAMESPACE_URL, uuid5
from sqlalchemy import select, func
from app.core.config import ENV, INTEGRATIONS_MODE
from app.core.database import SessionLocal, engine
from app.models.credits import CreditCustomer, CreditMovement
from app.models.registers import CustomerCredit
from app.models.business import BusinessEntry
from app.services.credits import save_customer, save_movement

PEOPLE = [("Marcela Pérez", "Cuenta de ejemplo con pagos"), ("Juan Gómez", "Una compra de ejemplo"),
          ("Ana López", "Cuenta de ejemplo saldada"), ("Carlos Martínez", "Historial de ejemplo")]
MOVEMENTS = [(0,"purchase","5000","2026-11-01"), (0,"purchase","10000","2026-11-02"),
    (0,"purchase","30000","2026-11-03"), (0,"payment","25000","2026-11-10"),
    (1,"purchase","7500","2026-11-18"), (2,"purchase","18000","2026-11-08"),
    (2,"payment","18000","2026-11-15"), (3,"purchase","4200","2025-10-03"),
    (3,"payment","4200","2025-10-09")]


def demo_key(value):
    return str(uuid5(NAMESPACE_URL, "arca-dys:fiados-demo-v1:" + value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Crear los ejemplos después de verificar el entorno")
    args = parser.parse_args()
    if ENV not in {"development", "test"} or INTEGRATIONS_MODE != "mock" or os.getenv("CREDIT_DEMO_SEED") != "1":
        raise RuntimeError("La demo exige entorno local mock y CREDIT_DEMO_SEED=1 explícito")
    if engine.url.host != "postgres" or engine.url.database not in {"arca_dys_dev", "arca_dys_test"}:
        raise RuntimeError("La demo solo admite el PostgreSQL local aislado de desarrollo o pruebas")
    person_keys = [demo_key("person:" + str(n)) for n in range(len(PEOPLE))]
    movement_keys = [demo_key("movement:" + str(n)) for n in range(len(MOVEMENTS))]
    with SessionLocal() as db:
        other_people = db.scalar(select(func.count()).select_from(CreditCustomer).where(CreditCustomer.entry_key.not_in(person_keys)))
        other_movements = db.scalar(select(func.count()).select_from(CreditMovement).where(CreditMovement.entry_key.not_in(movement_keys)))
        if other_people or other_movements or db.scalar(select(func.count()).select_from(CustomerCredit)) or db.scalar(select(func.count()).select_from(BusinessEntry)):
            raise RuntimeError("Se encontraron datos ajenos a estos ejemplos. No se modificó ni se limpió la base")
        if not args.apply:
            print("Validación sin escrituras: 4 personas y 9 movimientos ficticios; repetir con --apply para cargarlos.")
            return
        ids = []
        for index, (name, alias) in enumerate(PEOPLE):
            row = save_customer(db, {"entry_key": person_keys[index], "name": name, "alias": alias, "distinct_person": "1"})
            ids.append(row.id)
        for index, (owner, kind, amount, day) in enumerate(MOVEMENTS):
            row = db.get(CreditCustomer, ids[owner])
            save_movement(db, {"entry_key": movement_keys[index], "customer_id": str(row.id), "version": str(row.version),
                "kind": kind, "amount": amount, "entry_date": day, "observation": "Ejemplo ficticio"}, "Demo local")
        print("Demo ficticia lista: Marcela 20.000, Juan 7.500, Ana 0 y Carlos 0. No se crearon cobros ni facturas.")


if __name__ == "__main__":
    main()
