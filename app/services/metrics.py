"""Agregaciones SQL sobre registros vigentes. Ninguna fuente crea ingresos en otra."""
from datetime import date, datetime, time
from decimal import Decimal
from calendar import monthrange
from sqlalchemy import select, func, case, Integer
from app.models.business import BusinessEntry, Supplier
from app.models.payment import Payment
from app.models.invoice import Invoice
from app.models.registers import SalaryPayment, EMPLOYEES

MONTHS = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
ZERO = Decimal("0.00")


def bounds(year, month=0):
    if not 1 <= year <= 9998 or not 0 <= month <= 12:
        raise ValueError("Elegí un año y mes válidos")
    if month:
        return date(year, month, 1), date(year, month, monthrange(year, month)[1])
    return date(year, 1, 1), date(year, 12, 31)


def finish(row):
    row["result"] = ((row["sale"] or ZERO) - (row["expense"] or ZERO) - (row["salary"] or ZERO)) if row["entries"] or row["salary_count"] else None
    row["average"] = (row["sale"] / row["days"]).quantize(Decimal("0.01")) if row["days"] else None
    return row


def year_metrics(db, year):
    start, end = bounds(year)
    return collect_metrics(db, start, end, monthly=True)


def period_metrics(db, start, end):
    return collect_metrics(db, start, end, monthly=False)[0]


def collect_metrics(db, start, end, *, monthly):
    rows = [{"month": n, "label": MONTHS[n-1], "sale": None, "sale_cash": None, "sale_mp": None, "sale_unknown": None,
        "expense_white": None, "expense_black": None, "expense_unknown": None, "expense": None,
        "salary": None, "salary_count": 0, "employees": {name: None for name in EMPLOYEES},
        "result": None, "days": 0, "entries": 0, "min_sale": None, "max_sale": None,
        "mp": None, "mp_count": 0, "invoices": None, "invoice_count": 0} for n in (range(1, 13) if monthly else [1])]
    def group(column):
        return func.extract("month", column) if monthly else func.cast(1, Integer)
    month = group(BusinessEntry.entry_date)
    for number, kind, expense_type, count, amount, minimum, maximum, cash, mp, unknown in db.execute(select(month, BusinessEntry.kind, BusinessEntry.expense_type,
        func.count(), func.sum(BusinessEntry.amount), func.min(BusinessEntry.amount), func.max(BusinessEntry.amount),
        func.sum(BusinessEntry.cash_amount), func.sum(BusinessEntry.mp_amount),
        func.sum(case((BusinessEntry.cash_amount.is_(None), BusinessEntry.amount), else_=None))).where(
        BusinessEntry.active.is_(True), BusinessEntry.entry_date.between(start, end)).group_by(month, BusinessEntry.kind, BusinessEntry.expense_type)):
        row = rows[int(number)-1]
        row[kind], row["entries"] = (row[kind] or ZERO) + amount, row["entries"] + count
        if kind == "expense":
            row[{"white": "expense_white", "black": "expense_black"}.get(expense_type, "expense_unknown")] = amount
        if kind == "sale":
            row["days"], row["min_sale"], row["max_sale"] = count, minimum, maximum
            row["sale_cash"], row["sale_mp"], row["sale_unknown"] = cash, mp, unknown
    salary_month = group(SalaryPayment.entry_date)
    for number, employee, count, amount in db.execute(select(salary_month, SalaryPayment.employee, func.count(), func.sum(SalaryPayment.amount)).where(
        SalaryPayment.entry_date.between(start, end)).group_by(salary_month, SalaryPayment.employee)):
        row = rows[int(number)-1]
        row["salary"] = (row["salary"] or ZERO) + amount
        row["salary_count"] += count
        row["employees"][employee] = amount
    mp_month = group(Payment.date_approved)
    for number, count, amount in db.execute(select(mp_month, func.count(), func.sum(Payment.mont)).where(
        Payment.status == "approved", Payment.mont > 0,
        Payment.date_approved.between(datetime.combine(start, time.min), datetime.combine(end, time.max))).group_by(mp_month)):
        rows[int(number)-1]["mp"], rows[int(number)-1]["mp_count"] = amount, count
    invoice_month = group(Invoice.invoice_date)
    for number, count, amount in db.execute(select(invoice_month, func.count(), func.sum(Invoice.total_amount)).where(
        Invoice.invoice_date.between(start, end), Invoice.cae.isnot(None), Invoice.cae != "",
        Invoice.invoice_number.isnot(None), Invoice.total_amount.isnot(None)).group_by(invoice_month)):
        rows[int(number)-1]["invoices"], rows[int(number)-1]["invoice_count"] = amount, count
    return [finish(row) for row in rows]


def period_total(rows):
    result = {"days": sum(row["days"] for row in rows), "entries": sum(row["entries"] for row in rows),
        "salary_count": sum(row["salary_count"] for row in rows),
        "mp_count": sum(row["mp_count"] for row in rows), "invoice_count": sum(row["invoice_count"] for row in rows)}
    result["employees"] = {name: sum((row["employees"][name] for row in rows if row["employees"][name] is not None), ZERO) if any(row["employees"][name] is not None for row in rows) else None for name in EMPLOYEES}
    for key in ("sale", "sale_cash", "sale_mp", "sale_unknown", "salary", "expense_white", "expense_black", "expense_unknown", "expense", "mp", "invoices"):
        values = [row[key] for row in rows if row[key] is not None]
        result[key] = sum(values, ZERO) if values else None
    for key, reducer in (("min_sale", min), ("max_sale", max)):
        values = [row[key] for row in rows if row[key] is not None]
        result[key] = reducer(values) if values else None
    return finish(result)


def change(current, previous):
    if current is None or previous is None:
        return {"difference": None, "percent": None}
    return {"difference": current - previous,
        "percent": ((current - previous) / previous * 100).quantize(Decimal("0.1")) if previous > 0 else None}


def expense_groups(start, end, *, suppliers=False):
    if suppliers:
        label = func.coalesce(Supplier.name, "Sin proveedor")
        statement = select(label.label("label"), func.sum(BusinessEntry.amount).label("amount"), func.count().label("count")).outerjoin(
            Supplier, Supplier.id == BusinessEntry.supplier_id).group_by(Supplier.id, Supplier.name)
    else:
        label = case((BusinessEntry.expense_type == "white", "En Blanco"),
                     (BusinessEntry.expense_type == "black", "En Negro"), else_="Sin tipo")
        statement = select(label.label("label"), func.sum(BusinessEntry.amount).label("amount"), func.count().label("count")).group_by(label)
    return statement.where(BusinessEntry.active.is_(True), BusinessEntry.kind == "expense",
        BusinessEntry.entry_date.between(start, end)).order_by(func.sum(BusinessEntry.amount).desc(), label)


def chart_bars(rows):
    maximum = max((row[key] or ZERO for row in rows for key in ("sale", "expense", "salary")), default=ZERO)
    bars = []
    for n, row in enumerate(rows):
        record = dict(row, x=60+n*68)
        for key in ("sale", "expense", "salary"):
            record[key + "_height"] = float((row[key] or ZERO) / maximum * 190) if maximum else 0
        bars.append(record)
    return bars, maximum
