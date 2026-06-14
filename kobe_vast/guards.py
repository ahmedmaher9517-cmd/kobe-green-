# -*- coding: utf-8 -*-
"""Value assertion guards before DB mutations."""


class GuardError(Exception):
    pass


def assert_positive(value, label="القيمة"):
    v = float(value)
    if v <= 0:
        raise GuardError(f"{label} يجب أن تكون أكبر من صفر")
    return v


def assert_non_negative(value, label="القيمة"):
    v = float(value)
    if v < 0:
        raise GuardError(f"{label} لا يمكن أن تكون سالبة")
    return v


def assert_split_payment(cash, bank_1, bank_2, gross_total, tolerance=0.01):
    c = assert_non_negative(cash, "كاش")
    b1 = assert_non_negative(bank_1, "بنك 1")
    b2 = assert_non_negative(bank_2, "بنك 2")
    gross = float(gross_total)
    paid = c + b1 + b2
    if abs(paid - gross) > tolerance:
        raise GuardError(
            f"مجموع الدفع ({paid:,.2f}) لا يساوي إجمالي الفاتورة ({gross:,.2f})"
        )
    return {"cash": c, "bank_1": b1, "bank_2": b2}


def assert_recipe_ratios(recipe):
    if not recipe:
        raise GuardError("الوصفة فارغة")
    total = sum(float(v) for v in recipe.values())
    if abs(total - 1.0) > 0.001:
        raise GuardError(f"نسب الوصفة يجب أن تساوي 100% (الحالي: {total * 100:.1f}%)")
    for k, v in recipe.items():
        assert_positive(v, f"نسبة {k}")
    return recipe


def assert_sufficient_stock(available, needed, item_name):
    a, n = float(available), float(needed)
    if a < n:
        raise GuardError(f"رصيد غير كافٍ لـ {item_name}: متاح {a:.3f} كجم، مطلوب {n:.3f} كجم")
    return True
