# -*- coding: utf-8 -*-
"""Core wholesale product menu dataset (Section 4)."""

CORE_PRODUCT_MENU = [
    {"name_ar": "حبشي بليند", "name_en": "Habashi Blend", "price": 275, "category": "Blend", "division": "blend"},
    {"name_ar": "كولومبي بليند", "name_en": "Colombian Blend", "price": 340, "category": "Blend", "division": "blend"},
    {"name_ar": "اسبريسو بليند", "name_en": "Espresso Blend", "price": 400, "category": "Espresso Base", "division": "blend"},
    {"name_ar": "هندي روبستا", "name_en": "Indian Robusta", "price": 235, "category": "Single-Origin Robusta", "division": "commercial"},
    {"name_ar": "فيتنامي روبستا", "name_en": "Vietnamese Robusta", "price": 220, "category": "Single-Origin Robusta", "division": "commercial"},
    {"name_ar": "اندونيسي", "name_en": "Indonesian", "price": 235, "category": "Single-Origin", "division": "commercial"},
    {"name_ar": "برازيلي", "name_en": "Brazilian", "price": 400, "category": "Single-Origin Arabica Base", "division": "b2b"},
    {"name_ar": "كولومبي", "name_en": "Colombian", "price": 440, "category": "Single-Origin Specialty", "division": "specialty"},
    {"name_ar": "حبشي", "name_en": "Habashi", "price": 360, "category": "Single-Origin Specialty", "division": "specialty"},
    {"name_ar": "كوستاريكي", "name_en": "Costa Rican", "price": 600, "category": "Premium Single-Origin", "division": "specialty"},
    {"name_ar": "جواتيمالا", "name_en": "Guatemalan", "price": 520, "category": "Premium Single-Origin", "division": "specialty"},
]

TASTING_NOTES = {
    "كوستاريكي": "حموضة مشرقة، عسل، تفاح أخضر",
    "جواتيمالا": "شوكولاتة، جوز، جسم كامل",
    "كولومبي": "كراميل، مكسرات، متوازن",
    "حبشي": "توت، زهور، حلاوة خفيفة",
    "برازيلي": "جوز برازيلي، كاكاو، نعومة",
}


def menu_by_division(division):
    return [p for p in CORE_PRODUCT_MENU if p["division"] == division]


def seed_inv_type(category):
    if "Robusta" in category or category == "Blend" or "Espresso" in category:
        return "أخضر"
    if "Premium" in category or "Specialty" in category:
        return "أخضر"
    return "أخضر"
