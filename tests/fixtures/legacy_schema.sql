-- Adminer 5.4.2 PostgreSQL 17.8 dump


DROP TABLE IF EXISTS "error_logs";
DROP SEQUENCE IF EXISTS "public".error_logs_id_seq;
CREATE SEQUENCE "public".error_logs_id_seq INCREMENT 1 MINVALUE 1 MAXVALUE 2147483647 CACHE 1;

CREATE TABLE "public"."error_logs" (
    "id" integer DEFAULT nextval('error_logs_id_seq') NOT NULL,
    "created_at" timestamp NOT NULL,
    "source" character varying(50) NOT NULL,
    "error_type" character varying(50) NOT NULL,
    "message" text NOT NULL,
    "resource_id" character varying(100),
    "raw_data" json,
    "resolved" boolean,
    "resolved_at" timestamp,
    "resolved_by" character varying(100),
    "resolution_notes" text,
    CONSTRAINT "error_logs_pkey" PRIMARY KEY ("id")
)
WITH (oids = false);

CREATE INDEX ix_error_logs_id ON public.error_logs USING btree (id);


DROP TABLE IF EXISTS "invoices";
DROP SEQUENCE IF EXISTS "public".invoices_id_seq;
CREATE SEQUENCE "public".invoices_id_seq INCREMENT 1 MINVALUE 1 MAXVALUE 2147483647 CACHE 1;

CREATE TABLE "public"."invoices" (
    "id" integer DEFAULT nextval('invoices_id_seq') NOT NULL,
    "invoice_number" character varying(300),
    "total_amount" double precision,
    "status" character varying(100),
    "error_message" character varying(200),
    "cae" character varying(300),
    "cae_due_date" date,
    "invoice_date" date,
    "pdf_url" character varying(300),
    "raw_afip_response" json,
    "created_at" timestamp,
    CONSTRAINT "invoices_pkey" PRIMARY KEY ("id")
)
WITH (oids = false);

CREATE UNIQUE INDEX invoices_invoice_number_key ON public.invoices USING btree (invoice_number);

CREATE INDEX ix_invoices_id ON public.invoices USING btree (id);


DROP TABLE IF EXISTS "logs_invoice";
DROP SEQUENCE IF EXISTS "public".logs_invoice_id_seq;
CREATE SEQUENCE "public".logs_invoice_id_seq INCREMENT 1 MINVALUE 1 MAXVALUE 2147483647 CACHE 1;

CREATE TABLE "public"."logs_invoice" (
    "id" integer DEFAULT nextval('logs_invoice_id_seq') NOT NULL,
    "error" character varying(300) NOT NULL,
    "created_at" timestamp,
    CONSTRAINT "logs_invoice_pkey" PRIMARY KEY ("id")
)
WITH (oids = false);

CREATE INDEX ix_logs_invoice_id ON public.logs_invoice USING btree (id);


DROP TABLE IF EXISTS "payment_invoice";
DROP SEQUENCE IF EXISTS "public".payment_invoice_id_seq;
CREATE SEQUENCE "public".payment_invoice_id_seq INCREMENT 1 MINVALUE 1 MAXVALUE 2147483647 CACHE 1;

CREATE TABLE "public"."payment_invoice" (
    "id" integer DEFAULT nextval('payment_invoice_id_seq') NOT NULL,
    "payment_id" integer NOT NULL,
    "invoice_id" integer NOT NULL,
    CONSTRAINT "payment_invoice_pkey" PRIMARY KEY ("id")
)
WITH (oids = false);

CREATE INDEX ix_payment_invoice_id ON public.payment_invoice USING btree (id);


DROP TABLE IF EXISTS "payments";
DROP SEQUENCE IF EXISTS "public".payments_id_seq;
CREATE SEQUENCE "public".payments_id_seq INCREMENT 1 MINVALUE 1 MAXVALUE 2147483647 CACHE 1;

CREATE TABLE "public"."payments" (
    "id" integer DEFAULT nextval('payments_id_seq') NOT NULL,
    "id_payment_mp" character varying(50) NOT NULL,
    "status" character varying(50) NOT NULL,
    "status_detail" character varying(150),
    "mont" double precision,
    "type_of_paid" character varying(50),
    "date_approved" timestamp,
    "bill" boolean,
    "registered_arca" boolean,
    "id_arca" character varying(200),
    "raw_json" json,
    "created_at" timestamp,
    CONSTRAINT "payments_pkey" PRIMARY KEY ("id")
)
WITH (oids = false);

CREATE INDEX ix_payments_id ON public.payments USING btree (id);

CREATE INDEX ix_payments_id_payment_mp ON public.payments USING btree (id_payment_mp);


ALTER TABLE ONLY "public"."payment_invoice" ADD CONSTRAINT "payment_invoice_invoice_id_fkey" FOREIGN KEY (invoice_id) REFERENCES invoices(id);
ALTER TABLE ONLY "public"."payment_invoice" ADD CONSTRAINT "payment_invoice_payment_id_fkey" FOREIGN KEY (payment_id) REFERENCES payments(id);

-- 2026-10-15 19:33:54 UTC
