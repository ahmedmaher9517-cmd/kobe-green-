# -*- coding: utf-8 -*-
"""Mobile-responsive CSS + shared UI helpers."""
MOBILE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap');
div[data-testid="stAppViewContainer"] { padding: 4px 8px !important; }
    section[data-testid="stSidebar"] { min-width: 240px !important; }
    div[data-testid="stSidebar"] .stSelectbox > div { font-size: 16px !important; }
    div[data-testid="stSidebar"] .stSelectbox label { font-size: 14px !important; }
div[data-testid="stColumn"] { min-width: 100% !important; flex: 1 1 100% !important; }
@media (min-width: 768px) {
    div[data-testid="stColumn"] { min-width: unset !important; flex: unset !important; }
}
.arabic-text { direction: rtl; text-align: right; font-family: 'Cairo', 'Tajawal', sans-serif; unicode-bidi: embed; }
.lux-card {
    background: linear-gradient(145deg, #111d17, #0f1a14);
    border: 1px solid #c19b62; border-radius: 14px;
    padding: 16px; margin-bottom: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.25);
}
.platform-card-green {
    border-right: 6px solid #2e7d32; background: linear-gradient(135deg, rgba(46,125,50,0.18), rgba(46,125,50,0.06));
    padding: 18px; border-radius: 14px; margin: 8px 0;
    border: 1px solid rgba(46,125,50,0.35);
}
.platform-card-roast {
    border-right: 6px solid #6d4c41; background: linear-gradient(135deg, rgba(109,76,65,0.18), rgba(109,76,65,0.06));
    padding: 18px; border-radius: 14px; margin: 8px 0;
    border: 1px solid rgba(109,76,65,0.35);
}
.platform-card-kobecup {
    border-right: 6px solid #e85d04; background: linear-gradient(135deg, rgba(232,93,4,0.18), rgba(232,93,4,0.06));
    padding: 18px; border-radius: 14px; margin: 8px 0;
    border: 1px solid rgba(232,93,4,0.35);
}
.add-item-box {
    background: #0f1f18; border: 2px dashed #c19b62; border-radius: 14px;
    padding: 16px; margin: 10px 0;
}
.add-item-box h4 { color: #c19b62; margin: 0 0 10px 0; font-size: 16px; }
.cart-panel {
    background: #111d17; border: 2px solid #c19b62; border-radius: 14px;
    padding: 16px; margin-top: 12px;
}
.cart-line {
    background: #1a2e24; border: 1px solid rgba(193,155,98,0.35);
    border-radius: 12px; padding: 12px; margin-bottom: 10px;
}
.cart-line-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.cart-total-bar {
    background: linear-gradient(90deg, #143d2a, #1a5238);
    border-radius: 10px; padding: 14px; text-align: center;
    font-size: 20px; font-weight: 900; color: #c19b62; margin: 12px 0;
}
.kpi-row { margin-bottom: 8px; }
.styled-table-wrap {
    border: 1px solid rgba(193,155,98,0.3); border-radius: 12px;
    overflow: hidden; margin: 10px 0;
}
div[data-testid="stDataFrame"] table, div[data-testid="stDataEditor"] table {
    border-collapse: separate !important; border-spacing: 0 !important;
}
div[data-testid="stDataFrame"] thead th, div[data-testid="stDataEditor"] thead th {
    background: #143d2a !important; color: #c19b62 !important;
    font-weight: 700 !important; padding: 12px 8px !important;
}
div[data-testid="stDataFrame"] tbody tr:nth-child(even), div[data-testid="stDataEditor"] tbody tr:nth-child(even) {
    background: rgba(20,61,42,0.15) !important;
}
.kds-partition-green { border-right: 5px solid #2e7d32; background: rgba(46,125,50,0.12); padding: 12px; border-radius: 8px; margin: 8px 0; }
.kds-partition-roast { border-right: 5px solid #6d4c41; background: rgba(109,76,65,0.12); padding: 12px; border-radius: 8px; margin: 8px 0; }
.kds-partition-ground { border-right: 5px solid #e85d04; background: rgba(232,93,4,0.12); padding: 12px; border-radius: 8px; margin: 8px 0; }
div[data-testid="stButton"] button[kind="secondary"] {
    min-height: 44px !important; font-size: 15px !important;
}
.btn-delete-mobile button, .btn-delete-row button {
    background: #c62828 !important; color: #fff !important;
    border: none !important; min-height: 40px !important;
    font-weight: 700 !important; border-radius: 10px !important; font-size: 14px !important;
}
.btn-delete-mobile button:hover, .btn-delete-row button:hover { background: #b71c1c !important; }
.btn-add-item button {
    background: linear-gradient(135deg, #1a5238, #143d2a) !important;
    color: #c19b62 !important; border: 2px solid #c19b62 !important;
    min-height: 52px !important; font-size: 17px !important; font-weight: 900 !important;
    border-radius: 12px !important;
}
.btn-add-item button:hover { background: #c19b62 !important; color: #143d2a !important; }
div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
    overflow-x: auto !important; -webkit-overflow-scrolling: touch;
}
div[data-testid="stDataEditor"] td { font-size: 14px !important; padding: 8px 4px !important; }
.main-header h3 { margin: 4px 0 !important; }
@media (max-width: 768px) {
    .main-header h3 { font-size: 16px !important; }
    div[data-testid="stMetric"] { padding: 8px !important; }
    div[data-testid="stTabs"] button { font-size: 13px !important; padding: 8px 10px !important; }
    section[data-testid="stSidebar"] { z-index: 999980 !important; }
}
"""


def inject_mobile_css():
    import streamlit as st
    st.markdown(f"<style>{MOBILE_CSS}</style>", unsafe_allow_html=True)


def delete_button(label, key, css_class="btn-delete-mobile"):
    import streamlit as st
    st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
    clicked = st.button(f"🗑️ {label}", key=key, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
    return clicked


def add_item_button(label, key):
    import streamlit as st
    st.markdown('<div class="btn-add-item">', unsafe_allow_html=True)
    clicked = st.button(label, key=key, use_container_width=True, type="primary")
    st.markdown("</div>", unsafe_allow_html=True)
    return clicked


def styled_dataframe(df, **kwargs):
    import streamlit as st
    st.markdown('<div class="styled-table-wrap">', unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True, hide_index=True, **kwargs)
    st.markdown("</div>", unsafe_allow_html=True)
