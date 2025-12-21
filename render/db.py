import os
import psycopg2

DATABASE_URL = os.environ["DATABASE_URL"]

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    print("Conectando a DB...")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id SERIAL PRIMARY KEY,
        mp_payment_id BIGINT UNIQUE,
        status TEXT,
        amount NUMERIC(12,2),
        payment_type TEXT,
        raw_json JSONB,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    conn.commit()
    conn.close()
    print("DB inicializada.")
