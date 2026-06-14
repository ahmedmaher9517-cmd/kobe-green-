# -*- coding: utf-8 -*-
"""Three-platform definitions: أخضر | محمص | كوبي كاب"""

PLATFORMS = {
    "green": {
        "key": "green",
        "label": "🟢 أخضر",
        "label_short": "أخضر",
        "types": ["أخضر"],
        "color": "#2e7d32",
        "bg": "rgba(46,125,50,0.12)",
    },
    "roast": {
        "key": "roast",
        "label": "🟤 محمص",
        "label_short": "محمص",
        "types": ["محمص"],
        "color": "#6d4c41",
        "bg": "rgba(109,76,65,0.12)",
    },
    "kobecup": {
        "key": "kobecup",
        "label": "🟧 كوبي كاب",
        "label_short": "كوبي كاب",
        "types": ["كوبي كاب", "مطحون"],
        "color": "#e85d04",
        "bg": "rgba(232,93,4,0.12)",
    },
}


def platform_for_type(item_type):
    for pk, p in PLATFORMS.items():
        if item_type in p["types"]:
            return pk
    return "green"


def filter_items_by_platform(items_df, platform_key):
    if items_df is None or items_df.empty:
        return items_df
    types = PLATFORMS[platform_key]["types"]
    return items_df[items_df["type"].isin(types)].copy()


def platform_badge(platform_key):
    p = PLATFORMS.get(platform_key, PLATFORMS["green"])
    return f'<span style="background:{p["bg"]};color:{p["color"]};padding:4px 10px;border-radius:8px;font-weight:700;font-size:13px;">{p["label"]}</span>'
