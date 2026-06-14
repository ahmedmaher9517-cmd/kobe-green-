# -*- coding: utf-8 -*-
"""Server-side invoice PDF — Arabic via python-bidi + Amiri font."""
import io
import itertools

from kobe_vast.arabic_fonts import FONT_BOLD, FONT_REGULAR, register_arabic_fonts
from kobe_vast.arabic_text import fix_arabic

_PARA_ID = itertools.count(1)


def _fa(text):
    return fix_arabic(str(text or ""))


def _para(text, size=11, bold=False, color=None):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph

    fn = FONT_BOLD if bold else FONT_REGULAR
    style = ParagraphStyle(
        name=f"ar_para_{next(_PARA_ID)}",
        fontName=fn,
        fontSize=size,
        leading=size * 1.45,
        alignment=TA_RIGHT,
        textColor=color if color is not None else colors.black,
    )
    safe = _fa(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, style)


def build_invoice_pdf_bytes(res, cfg, brand="green", default_company="كوبي جرين"):
    """
    Build A4 invoice PDF with correct Arabic.
    brand: 'green' | 'kobecup'
    Returns (bytes, error_message).
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        return None, "ثبّت reportlab: pip install reportlab"

    try:
        register_arabic_fonts()
    except Exception as exc:
        return None, str(exc)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    company = cfg.get("company_name", default_company)
    accent = colors.HexColor("#ea580c") if brand == "kobecup" else colors.HexColor("#143d2a")
    gold = colors.HexColor("#c19b62")

    story = []
    if brand == "kobecup":
        story.append(_para("كوبي كاب — تجزئة", size=22, bold=True, color=accent))
        story.append(_para("قهوة مختصة", size=11))
    else:
        story.append(_para(company, size=20, bold=True, color=accent))
        if cfg.get("address"):
            story.append(_para(f"العنوان: {cfg['address']}", size=10))
        if cfg.get("phone"):
            story.append(_para(f"الهاتف: {cfg['phone']}", size=10))

    story.append(Spacer(1, 10))
    story.append(_para(f"فاتورة رقم {res['no']}", size=14, bold=True, color=gold))
    story.append(_para(f"التاريخ: {res['d']}", size=10))
    story.append(_para(f"العميل: {res['c']}", size=13, bold=True))
    story.append(Spacer(1, 14))

    table_data = [
        [_fa("الإجمالي"), _fa("سعر الوحدة"), _fa("الكمية"), _fa("الصنف والبيان")],
    ]
    for line in res.get("cart", []):
        table_data.append([
            f"{float(line['t']):,.2f}",
            f"{float(line['p']):,.2f}",
            f"{float(line['qty']):,.2f}",
            _fa(f"{line['item']} — {line.get('type', '-')}") ,
        ])

    col_w = [70, 70, 55, 255]
    tbl = Table(table_data, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), FONT_REGULAR, 10),
        ("FONT", (0, 0), (-1, 0), FONT_BOLD, 10),
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (3, 1), (3, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 16))

    pay = res.get("pay", "—")
    rem = res.get("rem", float(res.get("net", 0)) - float(res.get("paid", 0)))
    summary = [
        [_fa("الإجمالي الفرعي:"), f"{float(res['gross']):,.2f} {_fa('ج.م')}"],
        [_fa("الخصم:"), f"- {float(res['disc']):,.2f} {_fa('ج.م')}"],
        [_fa("الصافي المستحق:"), f"{float(res['net']):,.2f} {_fa('ج.م')}"],
        [_fa("المبلغ المدفوع:"), f"{float(res['paid']):,.2f} {_fa('ج.م')}"],
        [_fa("الرصيد المتبقي:"), f"{float(rem):,.2f} {_fa('ج.م')}"],
        [_fa("طريقة الدفع:"), _fa(pay)],
    ]
    sum_tbl = Table(summary, colWidths=[180, 120])
    sum_tbl.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), FONT_REGULAR, 11),
        ("FONT", (0, 2), (-1, 2), FONT_BOLD, 12),
        ("FONT", (0, -1), (-1, -1), FONT_BOLD, 11),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("ALIGN", (1, 0), (1, -1), "LEFT"),
        ("TEXTCOLOR", (0, 2), (-1, 2), accent),
        ("LINEABOVE", (0, -1), (-1, -1), 1.5, accent),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(sum_tbl)
    story.append(Spacer(1, 20))

    if brand == "kobecup":
        story.append(_para("شكراً لتسوقكم من كوبي كاب ☕", size=11, bold=True, color=accent))
    else:
        story.append(_para(f"شكراً لثقتكم في {company}", size=11, bold=True, color=accent))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue(), None
