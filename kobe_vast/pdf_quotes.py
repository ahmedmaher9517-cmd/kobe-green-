# -*- coding: utf-8 -*-
"""PDF quotation generator — Arabic via python-bidi + Amiri font."""
import io

from kobe_vast.arabic_fonts import FONT_BOLD, FONT_REGULAR, register_arabic_fonts
from kobe_vast.arabic_text import fix_arabic


def build_quote_pdf_bytes(title, rows, cfg):
    """rows: list of dicts with name_ar, price, category"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        return None, "ثبّت reportlab: pip install reportlab"

    try:
        register_arabic_fonts()
    except Exception as exc:
        return None, str(exc)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _w, h = A4
    y = h - 50
    c.setFont(FONT_BOLD, 14)
    c.drawRightString(550, y, fix_arabic(title))
    y -= 30
    c.setFont(FONT_REGULAR, 11)
    c.drawRightString(550, y, fix_arabic(cfg.get("company_name", "KOBE GREEN")))
    y -= 40
    for r in rows:
        line = f"{r.get('name_ar', '')} — {r.get('price', 0):,.0f} ج.م/كجم"
        c.setFont(FONT_REGULAR, 11)
        c.drawRightString(550, y, fix_arabic(line))
        y -= 22
        if y < 60:
            c.showPage()
            y = h - 50
    c.save()
    buf.seek(0)
    return buf.getvalue(), None
