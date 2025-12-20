import os
import psycopg2

DATABASE_URL = os.environ["postgresql://db_dys_user:5Sh7fQK7bq13hjB74RH3XG35VfIN7kuR@dpg-d52u7gumcj7s73dq8ce0-a/db_dys"]

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id SERIAL PRIMARY KEY,
        mp_payment_id BIGINT UNIQUE,
        status TEXT,
        amount NUMERIC(12,2),
        currency TEXT,
        payment_type TEXT,
        method TEXT,
        date_approved TIMESTAMPTZ,
        raw_json JSONB,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    conn.commit()
    conn.close()
