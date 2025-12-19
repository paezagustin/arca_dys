import psycopg2
from db import get_conn

def save_payment(payment):
    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("""
        INSERT INTO payments (
            mp_payment_id,
            status,
            amount,
            currency,
            payment_type,
            method,
            date_approved,
            raw_json
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (mp_payment_id) DO NOTHING
        """, (
            payment["id"],
            payment["status"],
            payment["transaction_amount"],
            payment["currency_id"],
            payment["payment_type_id"],
            payment["payment_method_id"],
            payment["date_approved"],
            psycopg2.extras.Json(payment)
        ))
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()
