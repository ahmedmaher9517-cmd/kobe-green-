# -*- coding: utf-8 -*-
"""Download & register Arabic TTF fonts for ReportLab PDF."""
import urllib.request
from pathlib import Path

FONTS_DIR = Path(__file__).resolve().parent / "fonts"

_FONT_URLS = {
    "Amiri-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Regular.ttf",
    "Amiri-Bold.ttf": "https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Bold.ttf",
}

_REGISTERED = False
FONT_REGULAR = "Amiri"
FONT_BOLD = "Amiri-Bold"


def ensure_arabic_fonts():
    """Download Amiri fonts if missing."""
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, url in _FONT_URLS.items():
        dest = FONTS_DIR / name
        if not dest.exists() or dest.stat().st_size < 5000:
            try:
                urllib.request.urlretrieve(url, dest)
            except Exception as exc:
                raise RuntimeError(f"تعذّر تحميل خط {name}: {exc}") from exc
        paths[name] = dest
    return paths["Amiri-Regular.ttf"], paths["Amiri-Bold.ttf"]


def register_arabic_fonts():
    """Register Amiri with ReportLab (idempotent)."""
    global _REGISTERED
    if _REGISTERED:
        return FONT_REGULAR, FONT_BOLD
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular, bold = ensure_arabic_fonts()
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(regular)))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold)))
    _REGISTERED = True
    return FONT_REGULAR, FONT_BOLD
