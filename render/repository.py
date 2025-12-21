import psycopg2
from render.db import get_conn
import psycopg2.extras

def save_payment(payment):
    conn = get_conn()
    cur = conn.cursor()

    try:
        print("Guardando pago en DB...")
        cur.execute("""
        INSERT INTO payments (
            mp_payment_id,
            status,
            amount,
            payment_type,
            raw_json
        ) VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (mp_payment_id) DO NOTHING
        """, (
            int(payment["id"]),
            payment["state"],
            payment["amount"],
            payment["id"],
            psycopg2.extras.Json(payment)
        ))
        conn.commit()
        print("Pago guardado.")
        return cur.rowcount == 1
    finally:
        conn.close()

