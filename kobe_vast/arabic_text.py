# -*- coding: utf-8 -*-
"""
Arabic text utilities.

- HTML invoices: logical Arabic + browser RTL (no get_display).
- PDF / ReportLab: reshape + python-bidi get_display + Amiri TTF font.
"""
import html as html_mod
import re

_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")

# Browser preview — native RTL
INVOICE_AR_CSS = """
.ar {
    direction: rtl;
    unicode-bidi: embed;
    text-align: right;
    font-family: 'Cairo', 'Tajawal', 'Amiri', sans-serif;
}
"""

AR_NODE_STYLE = (
    "direction:rtl;unicode-bidi:embed;text-align:right;"
    "font-family:'Cairo','Tajawal',sans-serif;"
)

_AR_STYLE = AR_NODE_STYLE


def _has_arabic(text):
    return bool(_ARABIC_RE.search(str(text or "")))


def reshape_arabic(text):
    """Join Arabic letter forms (arabic-reshaper)."""
    s = str(text or "")
    if not _has_arabic(s):
        return s
    try:
        import arabic_reshaper

        if hasattr(arabic_reshaper, "reshape") and callable(arabic_reshaper.reshape):
            return arabic_reshaper.reshape(s)
        return arabic_reshaper.ArabicReshaper().reshape(s)
    except Exception:
        return s


def fix_arabic(text):
    """
    Full Arabic fix for LTR renderers (ReportLab PDF).
    arabic-reshaper + python-bidi get_display.
    """
    if text is None:
        return ""
    s = str(text)
    if not _has_arabic(s):
        return s
    try:
        from bidi.algorithm import get_display

        return get_display(reshape_arabic(s))
    except Exception:
        return reshape_arabic(s)


def ar_html(text):
    """Logical Arabic for HTML — browser handles BiDi."""
    return html_mod.escape(str(text or ""))


def ar_invoice_row(item, item_type, qty, price, total):
    return (
        f"<tr>"
        f"<td class='ar' style='padding:15px 10px;border-bottom:1px solid #eee;{AR_NODE_STYLE}'>"
        f"<b>{ar_html(item)}</b><br>"
        f"<span style='font-size:12px;color:#777;'>{ar_html(f'النوع: {item_type}')}</span></td>"
        f"<td style='padding:15px 10px;border-bottom:1px solid #eee;text-align:center;'>{qty:,.2f}</td>"
        f"<td style='padding:15px 10px;border-bottom:1px solid #eee;text-align:center;'>{price:,.2f}</td>"
        f"<td style='padding:15px 10px;border-bottom:1px solid #eee;font-weight:900;color:#143d2a;"
        f"text-align:center;'>{total:,.2f}</td>"
        f"</tr>"
    )


def kc_invoice_row(item, item_type, qty, price, total):
    return (
        f"<tr>"
        f"<td class='ar' style='padding:14px 12px;border-bottom:1px solid #ffe0c2;{AR_NODE_STYLE}'>"
        f"<b style='color:#9a3412;font-size:15px;'>{ar_html(item)}</b><br>"
        f"<span style='font-size:12px;color:#c2410c;background:#fff7ed;padding:2px 8px;border-radius:6px;'>"
        f"{ar_html(item_type)}</span></td>"
        f"<td style='padding:14px;text-align:center;font-weight:600;'>{qty:,.2f}</td>"
        f"<td style='padding:14px;text-align:center;'>{price:,.2f}</td>"
        f"<td style='padding:14px;text-align:center;font-weight:900;color:#ea580c;font-size:16px;'>{total:,.2f}</td>"
        f"</tr>"
    )


# Back-compat for tests
_reshape = reshape_arabic
