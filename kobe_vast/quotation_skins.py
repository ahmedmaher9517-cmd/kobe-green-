# -*- coding: utf-8 -*-
"""Triple-format quotation price matrix (Phase 3)."""
import streamlit as st
import streamlit.components.v1 as components

from kobe_vast.product_menu import CORE_PRODUCT_MENU, TASTING_NOTES, menu_by_division
from kobe_vast.pdf_quotes import build_quote_pdf_bytes


def _b2b_table_html(cfg):
    rows = ""
    for p in CORE_PRODUCT_MENU:
        bulk = p["price"] * 0.85
        rows += f"<tr><td class='arabic-text'>{p['name_ar']}</td><td>{p['name_en']}</td><td>{p['category']}</td><td>{p['price']:,.0f}</td><td>{bulk:,.0f}</td></tr>"
    return f"""
    <div class='arabic-text' style='font-family:Cairo,sans-serif;padding:20px;background:#fff;color:#143d2a;'>
    <h2>B2B Wholesale Pricelist — {cfg.get('company_name','')}</h2>
    <table style='width:100%;border-collapse:collapse;'>
    <thead><tr style='background:#143d2a;color:#c19b62;'>
    <th>الصنف</th><th>English</th><th>الفئة</th><th>سعر/كجم</th><th>جملة (-15%)</th></tr></thead>
    <tbody>{rows}</tbody></table></div>"""


def _specialty_cards_html(cfg):
    items = menu_by_division("specialty") + [p for p in CORE_PRODUCT_MENU if "Premium" in p["category"]]
    cards = ""
    for p in items:
        note = TASTING_NOTES.get(p["name_ar"], "متوازن، جسم متوسط")
        cards += f"""
        <div style='border:1px solid #c19b62;border-radius:12px;padding:16px;margin:10px;background:#faf8f5;'>
        <h3 style='color:#143d2a;margin:0;'>{p['name_ar']}</h3>
        <p style='color:#666;'>{p['name_en']} — {p['category']}</p>
        <p style='font-size:22px;color:#c19b62;font-weight:900;'>{p['price']:,.0f} ج.م/كجم</p>
        <p style='font-style:italic;color:#555;'>{note}</p></div>"""
    return f"<div class='arabic-text' style='font-family:Cairo,sans-serif;'><h2>Specialty Coffee Menu</h2>{cards}</div>"


def _commercial_list_html(cfg):
    items = menu_by_division("commercial") + menu_by_division("blend")
    lis = "".join(
        f"<li style='padding:8px 0;border-bottom:1px dashed #ddd;'>"
        f"<b>{p['name_ar']}</b> — {p['price']:,.0f} ج.م/كجم <span style='color:#888;'>({p['category']})</span></li>"
        for p in items
    )
    return f"""
    <div class='arabic-text' style='font-family:Cairo,sans-serif;padding:20px;background:#fff;'>
    <h2>Commercial Cafe Pricelist</h2>
    <p>📞 {cfg.get('phone','')}</p>
    <ul style='list-style:none;padding:0;'>{lis}</ul></div>"""


def _render_b2b_client_form():
    st.markdown("#### 🎯 بيانات عميل B2B (تُنقل تلقائياً لـ CRM)")
    c1, c2 = st.columns(2)
    company = c1.text_input("اسم الشركة / الكافيه", key="b2b_company")
    contact = c2.text_input("اسم المسؤول *", key="b2b_contact")
    c3, c4 = st.columns(2)
    phone = c3.text_input("الهاتف", key="b2b_phone")
    email = c4.text_input("البريد الإلكتروني", key="b2b_email")
    tier = st.selectbox("الشريحة المستهدفة", ["جملة", "موزعين", "تفاوض"], key="b2b_tier")
    notes = st.text_area("ملاحظات الحملة", key="b2b_notes", height=60)
    return {
        "company": company,
        "contact": contact or company,
        "phone": phone,
        "email": email,
        "tier": tier,
        "notes": notes,
    }


def _push_crm(conn, client_data, products_label="B2B Pricelist"):
    if not conn:
        return
    from kobe_vast.crm_sync import push_b2b_lead
    name = client_data.get("contact") or client_data.get("company")
    ok, msg = push_b2b_lead(
        conn,
        name=name,
        phone=client_data.get("phone", ""),
        company=client_data.get("company", ""),
        email=client_data.get("email", ""),
        tier=client_data.get("tier", ""),
        products=products_label,
        source="B2B Campaign",
        notes_extra=client_data.get("notes", ""),
    )
    if ok:
        st.success(f"📋 CRM: {msg}")
    else:
        st.warning(msg)


def render_triple_quotation_ui(cfg, show_capture_fn, conn=None):
    st.markdown("## 📋 مصفوفة عروض الأسعار — 3 قوالب")
    skin = st.radio(
        "اختر قالب العرض:",
        [
            "B2B Wholesale Pricelist",
            "Specialty Coffee Aesthetic",
            "Commercial Local Cafe",
        ],
        key="quote_skin",
    )

    client_data = None
    if "B2B" in skin:
        client_data = _render_b2b_client_form()

    html = _b2b_table_html(cfg)
    if "Specialty" in skin:
        html = _specialty_cards_html(cfg)
    elif "Commercial" in skin:
        html = _commercial_list_html(cfg)

    c1, c2 = st.columns(2)
    if c1.button("📄 عرض / طباعة", key="quote_preview", use_container_width=True):
        show_capture_fn(html, f"Quote_{skin[:8]}", a4=True)
        if "B2B" in skin and conn and client_data:
            _push_crm(conn, client_data)

    if c2.button("📋 إرسال للـ CRM + عرض", type="primary", key="quote_crm", use_container_width=True):
        if "B2B" in skin:
            if not client_data or not (client_data.get("contact") or client_data.get("company")):
                st.error("أدخل اسم المسؤول أو الشركة")
            else:
                _push_crm(conn, client_data)
                show_capture_fn(html, f"Quote_{skin[:8]}", a4=True)
        else:
            st.info("نقل CRM متاح لحملة B2B فقط — اختر قالب B2B")

    if st.button("تصدير PDF (عربي مضبوط)", key="quote_pdf"):
        pdf, err = build_quote_pdf_bytes(skin, CORE_PRODUCT_MENU, cfg)
        if err:
            st.error(err)
        elif pdf:
            st.download_button("تحميل PDF", pdf, file_name="kobe_quote.pdf", mime="application/pdf", key="dl_quote_pdf")
