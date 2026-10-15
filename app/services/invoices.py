"""Comprobante local: datos persistidos, reparto decimal y QR propio de cada factura."""
from base64 import b64encode
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image, KeepTogether


def split_amount(amount):
    total = Decimal(str(amount)).quantize(Decimal("0.01"))
    first = (total / 2).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return first, total - first


def qr_value(invoice, simulated=False):
    fiscal = invoice.fiscal_snapshot or {}
    if simulated or fiscal.get("simulation"):
        return f"SIMULACION|Factura:{invoice.invoice_number}|Fecha:{invoice.invoice_date}|Total:{invoice.total_amount}"
    required = ["cuit", "point", "number", "voucher_type", "name", "tax_condition"]
    if any(not fiscal.get(key) for key in required):
        return None
    payload = {"ver": 1, "fecha": invoice.invoice_date.isoformat(), "cuit": int(fiscal["cuit"]),
        "ptoVta": int(fiscal["point"]), "tipoCmp": 11, "nroCmp": int(fiscal["number"]),
        "importe": float(Decimal(str(invoice.total_amount))), "moneda": "PES", "ctz": 1,
        "tipoDocRec": 99, "nroDocRec": 0, "tipoCodAut": "E", "codAut": int(invoice.cae)}
    encoded = b64encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()).decode()
    return "https://www.arca.gob.ar/fe/qr/?p=" + quote(encoded, safe="")


def render_invoice_pdf(invoice, *, simulated=False):
    snapshot = invoice.fiscal_snapshot or {}
    simulated = simulated or bool(snapshot.get("simulation"))
    legacy = not simulated and any(not snapshot.get(k) for k in ["name", "address", "cuit", "tax_condition", "gross_income", "start_date", "point", "number"])
    stream = BytesIO()
    document = SimpleDocTemplate(stream, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=30, bottomMargin=30,
                                  title=f"Factura C {invoice.invoice_number}", author="ARCA DYS")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("SmallPrint", parent=styles["Normal"], fontSize=9, leading=13))
    styles.add(ParagraphStyle("CenterLabel", parent=styles["Normal"], alignment=TA_CENTER, fontSize=9))
    styles.add(ParagraphStyle("TotalRight", parent=styles["Heading2"], alignment=TA_RIGHT))
    p = lambda text, style="SmallPrint": Paragraph(text, styles[style])
    amount = Decimal(str(invoice.total_amount)).quantize(Decimal("0.01"))
    money = lambda value: "$ " + f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    title = "SIMULACION - SIN VALIDEZ FISCAL" if simulated else ("REGISTRO HISTORICO - DATOS FISCALES INCOMPLETOS" if legacy else "ORIGINAL")
    story = [p(title, "CenterLabel"), Spacer(1, 15)]
    logo = Image(str(Path(__file__).resolve().parents[1] / "assets/logo-dulce-salado.jpg"), width=55, height=55, kind="proportional")
    issuer = "<b>" + escape(snapshot.get("name") or "Emisor no conservado en el registro") + "</b><br/>"
    issuer += escape(snapshot.get("address") or "Domicilio no conservado") + "<br/>"
    issuer += "CUIT: " + escape(snapshot.get("cuit") or "Sin dato histórico") + "<br/>"
    issuer += "Condición frente al IVA: " + escape(snapshot.get("tax_condition") or "Sin dato histórico") + "<br/>"
    issuer += "Ingresos Brutos: " + escape(snapshot.get("gross_income") or "Sin dato histórico") + "<br/>"
    issuer += "Inicio de actividades: " + escape(snapshot.get("start_date") or "Sin dato histórico")
    date_string = invoice.invoice_date.strftime("%d/%m/%Y") if invoice.invoice_date else "Sin fecha"
    header = Table([[logo, p(issuer), p("<b>FACTURA C</b><br/>Código 011<br/><br/><b>" + escape(str(invoice.invoice_number)) + "</b><br/>Fecha: " + date_string)]], colWidths=[70, 275, 178])
    header.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("BOTTOMPADDING", (0,0), (-1,-1), 15),
                               ("LINEBELOW", (0,0), (-1,-1), 1, colors.HexColor("#28594e"))]))
    story.extend([header, Spacer(1, 18), p("<b>Cliente:</b> Consumidor Final<br/><b>Documento:</b> Sin identificar (tipo 99)<br/><b>Condición de venta:</b> Efectivo"), Spacer(1, 18)])
    first, second = split_amount(amount)
    table = Table([["Descripción", "Cantidad", "Precio unitario", "Subtotal"],
        ["Cotillón", "1", money(first), money(first)], ["Repostería", "1", money(second), money(second)]], colWidths=[238, 65, 110, 110])
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#edf3ef")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 12), ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ("ALIGN", (1,0), (-1,-1), "RIGHT"), ("LINEBELOW", (0,0), (-1,-1), .4, colors.HexColor("#d5ded9"))]))
    story.extend([table, Spacer(1, 16), p("TOTAL: " + money(amount), "TotalRight"), Spacer(1, 25)])
    value = qr_value(invoice, simulated=simulated)
    if value:
        code = QrCodeWidget(value, barLevel="M", barBorder=4)
        x0, y0, x1, y1 = code.getBounds()
        drawing = Drawing(135, 135, transform=[135/(x1-x0), 0, 0, 135/(y1-y0), -x0, -y0])
        drawing.add(code)
    else:
        drawing = p("No se genera QR fiscal: faltan datos históricos del emisor.")
    due = invoice.cae_due_date.strftime("%d/%m/%Y") if invoice.cae_due_date else "Sin dato"
    auth = p("<b>CAE:</b> " + escape(str(invoice.cae or "Sin dato")) + "<br/><b>Vencimiento del CAE:</b> " + due +
             ("<br/><br/>Documento de prueba. No fue enviado a ARCA." if simulated else
              ("<br/><br/>Esta reconstrucción no reemplaza el comprobante original." if legacy else "<br/><br/>Comprobante autorizado. La descarga no genera otra emisión.")))
    tail = Table([[drawing, auth]], colWidths=[160, 363])
    tail.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
    story.append(KeepTogether([tail, Spacer(1, 14), p("Cotillón y repostería: distribución 50/50, ajustada al centavo.", "CenterLabel")]))
    document.build(story)
    return stream.getvalue()


def generar_pdf_factura(invoice):
    from app.core.config import INTEGRATIONS_MODE
    return render_invoice_pdf(invoice, simulated=INTEGRATIONS_MODE == "mock")
