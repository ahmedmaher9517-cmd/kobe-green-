# -*- coding: utf-8 -*-
"""Sidebar navigation — radio list, short labels."""
import streamlit as st

PAGE_LABELS = {
    "home": "🏠 الرئيسية",
    "sales": "🛒 المبيعات",
    "invoices": "📋 سجل الفواتير",
    "inventory": "📦 المخزون",
    "treasury": "🏦 الخزينة",
    "reports": "📑 التقارير",
    "kobecup": "🟧 كوبي كاب",
    "kds": "🍳 KDS",
    "settings": "⚙️ الإعدادات",
    "integrations": "🔗 الربط",
    "tools": "🔧 متقدم",
}

ROLE_PAGES = {
    "مدير": ["home", "sales", "invoices", "inventory", "treasury", "reports", "kobecup", "kds", "settings", "integrations", "tools"],
    "محاسب": ["home", "sales", "invoices", "inventory", "treasury", "reports", "kobecup"],
    "كاشير": ["home", "sales", "invoices", "kobecup", "kds"],
    "مخزن": ["home", "inventory", "kds", "tools"],
    "مشاهدة": ["home", "invoices", "reports", "inventory"],
}

DEFAULT_PAGE = "home"


def _pages_for_role(role):
    return ROLE_PAGES.get(role, ROLE_PAGES["مشاهدة"])


def render_nav(role):
    """Sidebar radio — clear and familiar."""
    allowed = _pages_for_role(role)
    if "page" not in st.session_state:
        st.session_state.page = DEFAULT_PAGE
    if st.session_state.page not in allowed:
        st.session_state.page = allowed[0]

    labels = [PAGE_LABELS[k] for k in allowed]
    idx = allowed.index(st.session_state.page)

    st.sidebar.markdown("### القائمة")
    picked = st.sidebar.radio(
        "الصفحات",
        labels,
        index=idx,
        label_visibility="collapsed",
        key="sidebar_nav_radio",
    )
    new_page = allowed[labels.index(picked)]
    if new_page != st.session_state.page:
        st.session_state.page = new_page
        st.rerun()
    return st.session_state.page
