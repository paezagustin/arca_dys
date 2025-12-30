import psycopg2
import os
import json
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT"),
        cursor_factory=RealDictCursor
    )


def insert_payment(payment: dict):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO payments (
                    id_payment_mp,
                    status,
                    status_detail,
                    date_approved,
                    mont,
                    type_of_paid,
                    bill,
                    regitered_arca,
                    id_arca,
                    raw_json
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id_payment_mp) DO NOTHING
            """, (
                payment["id_payment_mp"],
                payment["status"],
                payment["status_detail"],
                payment["date_approved"],
                payment["mont"],
                payment["type_of_paid"],
                payment["bill"],
                json.dumps(payment["raw_json"])
            ))
            conn.commit()
    finally:
        conn.close()


def get_payments_to_bill(fecha):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, mont
                FROM payments
                WHERE bill = true
                  AND date_approved::date = %s
                  AND factura_id IS NULL
            """, (fecha,))
            return cur.fetchall()
    finally:
        conn.close()
