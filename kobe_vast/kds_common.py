# -*- coding: utf-8 -*-
"""KDS shared helpers — avoids circular imports."""

DIVISION_MAP = {
    "أخضر": ("green", "🟢 قسم البن الأخضر"),
    "محمص": ("roast", "🟤 قسم البن المحمص"),
    "مطحون": ("ground", "☕ قسم البن المطحون"),
    "كوبي كاب": ("ground", "☕ قسم البن المطحون"),
}


def classify_line(item_type):
    key, label = DIVISION_MAP.get(item_type, ("green", "🟢 قسم البن الأخضر"))
    return key, label
