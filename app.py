# -*- coding: utf-8 -*-
"""كوبي جرين | KOBE GREEN — ERP & CRM | The Ultimate Master Code V9 (Admin Panel)"""
import base64
import os
import re
import sqlite3
import urllib.parse
import json
import requests
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# محاولة استدعاء Plotly 
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# ==========================================
# 🌐 Supabase Cloud Database Support
# ==========================================
IS_DEPLOYED = False
SUPABASE_DB_URL = None

try:
    if hasattr(st, 'secrets') and 'SUPABASE_DB_URL' in st.secrets:
        SUPABASE_DB_URL = st.secrets['SUPABASE_DB_URL']
        IS_DEPLOYED = True
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError:
            st.error("❌ Database driver missing. Contact administrator.")
            st.stop()
except Exception:
    pass

st.set_page_config(page_title="KOBE GREEN ERP", page_icon="☕", layout="wide", initial_sidebar_state="expanded")

DB_NAME = os.environ.get("KOBE_DB_PATH", "kobecup_master_erp_v7.db")
DEFAULT_COMPANY = "كوبي جرين | KOBE GREEN"
TAGLINE = "نظام تخطيط الموارد وإدارة الأعمال"
FONT_URL = "https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&family=Tajawal:wght@400;500;700;800&display=swap"

PAY_METHODS = ["كاش", "تحويل بنكي", "محفظة", "آجل"]
ITEM_TYPES = ["أخضر", "مطحون", "محمص", "كوبي كاب", "إضافات", "تعبئة"]
PRICING_TIERS = ["قطاعي", "جملة", "موزعين"]

# ==========================================
# 0. تهيئة المتغيرات والجلسات وقاعدة البيانات
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['role'] = None
    st.session_state['username'] = None
    st.session_state['cart'] = []
    st.session_state['kc_cart'] = []

def get_conn():
    """Smart connection - SQLite for local dev, PostgreSQL for cloud"""
    if IS_DEPLOYED:
        return psycopg2.connect(SUPABASE_DB_URL)
    else:
        return sqlite3.connect(DB_NAME, check_same_thread=False)

def migrate_schema():
    if IS_DEPLOYED:
        # Auto-migrate Supabase on first cloud run
        try:
            from auto_migrate_kobe import migrate_supabase_kobe
            migrate_supabase_kobe(SUPABASE_DB_URL)
        except Exception as e:
            st.error(f"Database setup: {e}")
        return
    
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT, is_done INTEGER DEFAULT 0, created_at TEXT)")
        conn.commit()

def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, company_name TEXT, phone TEXT, address TEXT, gemini_key TEXT DEFAULT '')")
        c.execute("CREATE TABLE IF NOT EXISTS inv (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, type TEXT, qty REAL DEFAULT 0, buy_price REAL DEFAULT 0, sell_price REAL DEFAULT 0, wholesale_price REAL DEFAULT 0, dist_price REAL DEFAULT 0, UNIQUE(name, type))")
        c.execute("CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, phone TEXT, address TEXT, opening_balance REAL DEFAULT 0, pricing_tier TEXT DEFAULT 'قطاعي', credit_limit REAL DEFAULT 10000.0)")
        c.execute("CREATE TABLE IF NOT EXISTS suppliers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, phone TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, time TEXT, inv_no TEXT, client TEXT, item TEXT, type TEXT, qty REAL, unit_p REAL, total REAL, paid REAL, discount REAL, pay_method TEXT, shipping_method TEXT, is_return INTEGER DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, time TEXT, supplier TEXT, item TEXT, type TEXT, qty REAL, total REAL, paid REAL, pay_method TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS treasury (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, time TEXT, movement_type TEXT, category TEXT, description TEXT, amount REAL, pay_method TEXT, method_details TEXT DEFAULT '---')")
        c.execute("CREATE TABLE IF NOT EXISTS banks (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)")
        c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT)")
        
        c.execute("CREATE TABLE IF NOT EXISTS roasting_log (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, green_bean TEXT, roasted_bean TEXT, in_qty REAL, loss_pct REAL, net_qty REAL, cost REAL, sell_price REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS shipping (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, order_ref TEXT, client TEXT, awb TEXT, is_delivered INTEGER DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, name TEXT, phone TEXT, requests TEXT, status TEXT, source TEXT, notes TEXT DEFAULT '')")
        c.execute("CREATE TABLE IF NOT EXISTS kc_customers (id INTEGER PRIMARY KEY, name TEXT UNIQUE, phone TEXT)")
        
        c.execute("CREATE TABLE IF NOT EXISTS platforms (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)")
        c.execute("CREATE TABLE IF NOT EXISTS ecommerce_inv (id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT, item TEXT, type TEXT, qty REAL DEFAULT 0, UNIQUE(platform, item, type))")
        c.execute("CREATE TABLE IF NOT EXISTS ecommerce_sales (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, platform TEXT, item TEXT, qty REAL, gross_price REAL, fees REAL, net_profit REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT, is_done INTEGER DEFAULT 0, created_at TEXT)")

        c.execute("INSERT OR IGNORE INTO settings (id, company_name, phone, address) VALUES (1,?,?,?)", (DEFAULT_COMPANY, "01027766055", "مصر — القاهرة"))
        c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', '123', 'مدير')")
        c.execute("INSERT OR IGNORE INTO platforms (name) VALUES ('أمازون (FBA)'), ('نون (FBN)'), ('المتجر الإلكتروني')")
        
        c.execute("SELECT COUNT(*) FROM banks")
        if c.fetchone()[0] == 0:
            for b in ["البنك الأهلي المصري", "بنك مصر", "CIB", "InstaPay"]: c.execute("INSERT OR IGNORE INTO banks (name) VALUES (?)", (b,))
        conn.commit()
    migrate_schema()

init_db()

# ==========================================
# 1. الدوال المساعدة وتصميم الـ HTML
# ==========================================
def get_settings():
    with get_conn() as conn: row = conn.execute("SELECT company_name, phone, address, gemini_key FROM settings WHERE id=1").fetchone()
    if row: return {"company_name": row[0] or DEFAULT_COMPANY, "phone": row[1] or "", "address": row[2] or "", "gemini_key": row[3] or ""}
    return {"company_name": DEFAULT_COMPANY, "phone": "", "address": "", "gemini_key": ""}

def get_banks():
    with get_conn() as conn: rows = conn.execute("SELECT name FROM banks ORDER BY name").fetchall()
    return [r[0] for r in rows] if rows else ["بنك افتراضي"]

def plotly_layout():
    return dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Cairo", color="#e8d5b5"), legend=dict(font=dict(color="#e8d5b5")), xaxis=dict(gridcolor="rgba(193,155,98,0.15)", tickfont=dict(color="#e8d5b5")), yaxis=dict(gridcolor="rgba(193,155,98,0.15)", tickfont=dict(color="#e8d5b5")))

def wrap_capture_document(inner_html, file_base, a4=False):
    a4_css = "width: 800px !important; min-width: 800px !important; max-width: 800px !important; margin: 0 auto; background-color: #fff; padding: 20px; box-sizing: border-box;"
    if a4: a4_css = "width: 210mm !important; min-height: 297mm !important; margin: 0 auto !important; background: #fff !important; padding: 12mm !important; box-sizing: border-box !important;"
    fb = file_base.replace("\\", "\\\\").replace("'", "\\'")
    return f"""<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><link href="{FONT_URL}" rel="stylesheet"><script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script><script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script><style>body{{margin:0;padding:16px;font-family:'Cairo',sans-serif;background:#f0ebe3;direction:rtl;}}[data-html2canvas-ignore]{{text-align:center;margin-bottom:16px;padding:12px;background:#143d2a;border-radius:12px;}}[data-html2canvas-ignore] button{{font-family:'Cairo',sans-serif;font-weight:700;padding:10px 20px;margin:5px;border-radius:8px;cursor:pointer;background:#c19b62;color:#143d2a;border:none;}}#capture-area{{ {a4_css} }}</style></head><body><div data-html2canvas-ignore><button onclick="downloadJPG()">حفظ JPG</button><button onclick="downloadPDF()">حفظ PDF</button></div><div style="overflow-x:auto;"><div id="capture-area">{inner_html}</div></div><script>const FILE_BASE = '{fb}';async function captureCanvas() {{const el = document.getElementById('capture-area');return await html2canvas(el, {{scale: 2, windowWidth: { '793' if a4 else '800' }, useCORS: true}});}}async function downloadJPG() {{const canvas = await captureCanvas();const link = document.createElement('a');link.download = FILE_BASE + '.jpg';link.href = canvas.toDataURL('image/jpeg', 0.95);link.click();}}async function downloadPDF() {{const canvas = await captureCanvas();const img = canvas.toDataURL('image/jpeg', 0.95);const {{jsPDF}} = window.jspdf;const pdf = new jsPDF('p','mm','a4');const pw = pdf.internal.pageSize.getWidth();const ph = pdf.internal.pageSize.getHeight();const ratio = Math.min(pw/canvas.width, ph/canvas.height);pdf.addImage(img,'JPEG',(pw-canvas.width*ratio)/2,10,canvas.width*ratio,canvas.height*ratio);pdf.save(FILE_BASE + '.pdf');}}</script></body></html>"""

def show_capture_component(inner_html, file_base, a4=False):
    components.html(wrap_capture_document(inner_html, file_base, a4), height=900, scrolling=True)

def load_logo_html():
    if os.path.exists("logo.png"):
        with open("logo.png", "rb") as f: b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" style="max-height:80px; display:block; margin: 0 auto;">'
    return f'<div style="text-align:center; color:#c19b62; font-weight:bold; font-size:24px;">{DEFAULT_COMPANY}</div>'

def build_invoice_html(res, cfg):
    rows = "".join(f"<tr><td style='padding:15px 10px; border-bottom:1px solid #eee; text-align:right;'><b>{i['item']}</b><br><span style='font-size:12px;color:#777;'>النوع: {i.get('type', '-')}</span></td><td style='padding:15px 10px; border-bottom:1px solid #eee;text-align:center;'>{i['qty']:,.2f}</td><td style='padding:15px 10px; border-bottom:1px solid #eee;text-align:center;'>{i['p']:,.2f}</td><td style='padding:15px 10px; border-bottom:1px solid #eee; font-weight:900; color:#143d2a;text-align:center;'>{i['t']:,.2f}</td></tr>" for i in res["cart"])
    return f"""<style>@import url('{FONT_URL}');.inv-container {{ width: 100%; margin: 0 auto; font-family: 'Cairo', 'Tajawal', sans-serif; background: #fff; padding: 40px; border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); direction: rtl; color: #333; }}.inv-header {{ display: flex; justify-content: space-between; border-bottom: 4px solid #143d2a; padding-bottom: 20px; margin-bottom: 30px; align-items: flex-start; }}.inv-company-info {{ text-align: right; flex: 1; }}.inv-company-info h2 {{ color: #143d2a; margin: 10px 0 5px 0; font-family: 'Tajawal', sans-serif; font-weight: 900; font-size: 28px; }}.inv-company-info p {{ margin: 4px 0; color: #555; font-size: 14px; }}.inv-details {{ text-align: left; flex: 1; }}.inv-details h1 {{ color: #c19b62; font-size: 42px; margin: 0 0 10px 0; font-family: 'Tajawal', sans-serif; text-transform: uppercase; letter-spacing: 2px; line-height: 1; }}.inv-details p {{ margin: 5px 0; font-size: 15px; color: #444; font-weight: 600; }}.inv-bill-to {{ background: #f9fbf9; border-right: 5px solid #143d2a; padding: 20px; border-radius: 8px; margin-bottom: 30px; border: 1px solid #eee; }}.inv-bill-to h4 {{ margin: 0 0 8px 0; color: #777; font-size: 14px; font-weight: 600; }}.inv-bill-to h3 {{ margin: 0; color: #143d2a; font-size: 22px; font-weight: 900; }}.inv-table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; }}.inv-table th {{ background: #143d2a; color: #c19b62; padding: 15px 10px; font-weight: 900; border-bottom: 3px solid #c19b62; text-align: center; font-size: 16px; }}.inv-table th:first-child {{ text-align: right; }}.inv-table td {{ text-align: center; font-size: 15px; }}.inv-summary {{ display: flex; justify-content: flex-end; }}.inv-summary-box {{ width: 380px; background: #fcfaf5; border: 1px solid #e8e0d0; border-radius: 8px; padding: 20px; }}.inv-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px dashed #e8e0d0; font-size: 15px; color: #555; font-weight: 600; }}.inv-row.net {{ font-size: 22px; font-weight: 900; color: #143d2a; border-bottom: 2px solid #c19b62; padding-bottom: 15px; margin-bottom: 5px; }}.inv-row.paid {{ color: #2e7d32; font-weight: 800; }}.inv-row.rem {{ border: none; font-size: 18px; font-weight: 900; color: #d32f2f; padding-top: 15px; }}.inv-footer {{ text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #888; font-size: 14px; font-weight: 700; }}</style>\n<div class="inv-container"><div class="inv-header"><div class="inv-company-info"><div style="text-align: right;">{load_logo_html().replace('margin: 0 auto', 'margin: 0')}</div><h2>{cfg['company_name']}</h2><p><b>📍 العنوان:</b> {cfg['address']}</p><p><b>📞 الهاتف:</b> {cfg['phone']}</p></div><div class="inv-details"><h1>فاتورة</h1><p>INVOICE #{res['no']}</p><p><b>تاريخ الإصدار:</b> {res['d']}</p></div></div><div class="inv-bill-to"><h4>فاتورة إلى السادة:</h4><h3>{res['c']}</h3><div style="margin-top: 12px; font-size: 15px; color: #444;"><b>طريقة الدفع:</b> {res['pay']}</div></div><table class="inv-table"><thead><tr><th style="width: 40%;">الصنف والبيان</th><th style="width: 20%;">الكمية</th><th style="width: 20%;">سعر الوحدة</th><th style="width: 20%;">الإجمالي</th></tr></thead><tbody>{rows}</tbody></table><div class="inv-summary"><div class="inv-summary-box"><div class="inv-row"><span>الإجمالي الفرعي:</span><span>{res['gross']:,.2f} ج.م</span></div><div class="inv-row" style="color: #d32f2f;"><span>الخصم:</span><span>- {res['disc']:,.2f} ج.م</span></div><div class="inv-row net"><span>الصافي المستحق:</span><span>{res['net']:,.2f} ج.م</span></div><div class="inv-row paid"><span>المبلغ المدفوع:</span><span>{res['paid']:,.2f} ج.م</span></div><div class="inv-row rem"><span>الرصيد المتبقي:</span><span>{res['rem']:,.2f} ج.م</span></div></div></div><div class="inv-footer">شكراً لثقتكم في {cfg['company_name']} 🌱</div></div>"""

def build_statement_html(client, rows_html, balance, stmt_date, cfg):
    return f"""<style>@import url('{FONT_URL}');.st{{width:100%;font-family:'Cairo',sans-serif;}}.tbl{{width:100%;border-collapse:collapse;margin:20px 0;}}.tbl th{{background:#143d2a;color:#c19b62;padding:10px;border:1px solid #ccc;}}.tbl td{{text-align:center;padding:8px;border:1px solid #eee;}}</style>\n<div class="st"><div style="text-align:center;border-bottom:3px solid #143d2a;padding-bottom:15px;">{load_logo_html()}<h2>كشف حساب تفصيلي</h2></div><div style="display:flex;justify-content:space-between;margin:20px 0;background:#f9f9f9;padding:15px;"><div><b>العميل:</b> {client}</div><div><b>التاريخ:</b> {stmt_date}</div></div><table class="tbl"><thead><tr><th>التاريخ</th><th>البيان</th><th>الكمية</th><th>مدين (عليه)</th><th>دائن (سدد)</th><th>الرصيد</th></tr></thead><tbody>{rows_html}</tbody></table><div style="text-align:center;background:#143d2a;color:#fff;padding:15px;font-size:20px;border-radius:8px;font-weight:bold;">الرصيد النهائي المستحق: {balance:,.2f} ج.م</div></div>"""

def build_kobecup_invoice_html(res, cfg):
    rows = "".join(f"<tr><td style='padding:12px 10px;border-bottom:1px solid #eee;text-align:right;'><b>{i['item']}</b><br><span style='font-size:12px;color:#777;'>النوع: {i.get('type', '-')}</span></td><td style='padding:15px 10px;border-bottom:1px solid #eee;text-align:center;'>{i['qty']:,.2f}</td><td style='padding:15px 10px;border-bottom:1px solid #eee;text-align:center;'>{i['p']:,.2f}</td><td style='padding:15px 10px;border-bottom:1px solid #eee;font-weight:bold;color:#e85d04;text-align:center;'>{i['t']:,.2f}</td></tr>" for i in res["cart"])
    return f"""<style>@import url('{FONT_URL}');.inv{{width:100%;font-family:'Cairo',sans-serif;color:#333;background:#fff;padding:40px;border:1px solid #e0e0e0;border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,0.08);direction:rtl;}}.tbl{{width:100%;border-collapse:collapse;margin:30px 0;}}.tbl th{{background:#e85d04;color:#fff;padding:15px 10px;text-align:center;}}.tbl th:first-child{{text-align:right;}}.tbl td{{text-align:center;}}.sum-box{{float:left;width:350px;background:#fffaf5;padding:20px;border:1px solid #fbdba7;border-radius:8px;}}.r{{display:flex;justify-content:space-between;margin-bottom:10px;font-weight:600;color:#555;}}</style>\n<div class="inv"><div style="display:flex;justify-content:space-between;border-bottom:4px solid #e85d04;padding-bottom:20px;"><div><h1 style="color:#e85d04;margin:0;font-size:40px;">KOBE CUP</h1><p><b>الهاتف:</b> {cfg['phone']}</p></div><div style="text-align:left;"><h2>إيصال مبيعات التجزئة</h2><b>رقم:</b> #{res['no']}<br><b>التاريخ:</b> {res['d']}<br><br><div style="background:#fff5eb;padding:10px;border-right:4px solid #e85d04;"><b>العميل:</b> {res['c']}<br><b>الدفع:</b> {res['pay']}</div></div></div>\n<table class="tbl"><thead><tr><th style="width:40%;">الصنف والبيان</th><th>الكمية</th><th>السعر</th><th>الإجمالي</th></tr></thead><tbody>{rows}</tbody></table>\n<div class="sum-box"><div class="r"><span>الإجمالي:</span><span>{res['gross']:,.2f} ج.م</span></div><div class="r" style="color:red;"><span>الخصم:</span><span>{res['disc']:,.2f} ج.م</span></div><div class="r" style="font-weight:900;font-size:22px;color:#e85d04;border-bottom:2px solid #e85d04;padding-bottom:10px;margin-bottom:10px;"><span>الصافي:</span><span>{res['net']:,.2f} ج.م</span></div></div><div style="clear:both;"></div><div style="text-align:center;margin-top:40px;padding-top:20px;border-top:1px solid #eee;color:#e85d04;font-weight:bold;font-size:16px;">شكراً لتسوقكم من كوبي كاب ☕🟧</div></div>"""

def build_quote_html(cname, rows_html, exp, qdate, cfg, brand="green"):
    mc = "#143d2a" if brand == "green" else "#e85d04"
    bg = "#f9fbf9" if brand == "green" else "#fff5eb"
    logo_or_title = load_logo_html() if brand == "green" else f"<h1 style='color:{mc};margin:0;font-size:48px;'>KOBE CUP</h1>"
    return f"""<style>@import url('{FONT_URL}');.q{{width:100%;font-family:'Cairo',sans-serif;background:#fff;padding:40px;border-radius:10px;border:1px solid #eee;}}.q-h{{text-align:center;border-bottom:4px solid {mc};padding-bottom:20px;margin-bottom:30px;}}.q-h h2{{color:{mc};font-size:2rem;margin:10px 0;}}.tbl{{width:100%;border-collapse:collapse;}}.tbl th{{background:{mc};color:#fff;padding:15px;}}.tbl td{{padding:15px;border-bottom:1px solid #eee;text-align:center;font-weight:bold;}}</style>\n<div class="q"><div class="q-h">{logo_or_title}<h2>عرض أسعار (Quotation)</h2></div><div style="display:flex;justify-content:space-between;background:{bg};padding:20px;border-right:5px solid {mc};margin-bottom:30px;"><div><b>مقدم إلى السادة:</b><br><span style="font-size:20px;font-weight:bold;">{cname}</span></div><div><b>التاريخ:</b> {qdate}<br><b>صالح حتى:</b> {exp}</div></div><table class="tbl"><thead><tr><th style="width:60%;">الصنف والبيان</th><th>سعر الكيلو (ج.م)</th></tr></thead><tbody>{rows_html}</tbody></table><div style="text-align:center;margin-top:40px;color:{mc};font-weight:bold;font-size:18px;">للتواصل وتأكيد الطلب: {cfg['phone']}</div></div>"""

def build_menu_html(products, cfg, template=1, title="KOBE GREEN", subtitle="قائمة الأسعار", brand="green"):
    mc = "#143d2a" if brand == "green" else "#e85d04"
    rows = "".join(f"<tr><td style='text-align:right;'>{p['name']}</td><td style='text-align:center;'>{p['type']}</td><td style='text-align:left;color:{mc};font-weight:900;font-size:22px;'>{p['price']:,.0f} ج.م</td></tr>" for p in products)
    
    if template == 1:
        border_c = "#c19b62" if brand == "green" else "#e85d04"
        style = f"""<style>@import url('{FONT_URL}');.sw{{width:100%;min-height:297mm;background:#fffaf0;padding:50px;border:10px double {border_c};font-family:'Cairo',sans-serif;box-sizing:border-box;}}.sw h1{{color:{mc};font-size:4rem;text-align:center;border-bottom:4px dashed {border_c};padding-bottom:15px;margin-bottom:10px;}}.tbl{{width:100%;border-collapse:collapse;margin-top:40px;}}.tbl th{{background:{mc};color:#fff;padding:18px;font-size:22px;}}.tbl td{{padding:18px;border-bottom:2px dotted #fbdba7;font-size:20px;font-weight:bold;color:#333;}}</style>"""
    elif template == 2:
        style = """<style>@import url('{FONT_URL}');.sw{width:100%;min-height:297mm;background:#ffffff;padding:50px;border:2px solid #ccc;font-family:'Cairo',sans-serif;box-sizing:border-box;}.sw h1{color:#333;font-size:3rem;text-align:center;margin-bottom:10px;font-weight:300;letter-spacing:2px;}.tbl{width:100%;border-collapse:collapse;margin-top:40px;}.tbl th{background:#f0f0f0;color:#333;padding:15px;font-size:20px;border-bottom:2px solid #333;}.tbl td{padding:15px;border-bottom:1px solid #eee;font-size:18px;color:#555;}</style>"""
    else:
        style = """<style>@import url('{FONT_URL}');.sw{width:100%;min-height:297mm;background:#0f2a1d;padding:50px;border:8px solid #c19b62;font-family:'Cairo',sans-serif;box-sizing:border-box;color:#fff;}.sw h1{color:#c19b62;font-size:4rem;text-align:center;margin-bottom:10px;text-transform:uppercase;letter-spacing:3px;}.tbl{width:100%;border-collapse:collapse;margin-top:40px;}.tbl th{background:#1a4d35;color:#c19b62;padding:20px;font-size:24px;border-bottom:3px solid #c19b62;}.tbl td{padding:20px;border-bottom:1px solid rgba(193,155,98,0.3);font-size:22px;color:#e8d5b5;}</style>"""

    return f"""{style}<div class="sw"><h1 style="margin-top:0;">{title}</h1><h2 style="text-align:center;color:#555;font-size:28px;">{subtitle}</h2><table class="tbl"><thead><tr><th style='text-align:right;'>الصنف</th><th>النوع</th><th style='text-align:left;'>السعر</th></tr></thead><tbody>{rows}</tbody></table><div style="text-align:center;margin-top:60px;font-size:26px;color:{mc};font-weight:900;">للطلب وتوصيل المنازل: {cfg['phone']}</div></div>"""

# ==========================================
# 2. دوال العمليات الأساسية والمساعد الذكي
# ==========================================
def now_dt(): n = datetime.now(); return n.strftime("%Y-%m-%d"), n.strftime("%I:%M %p")

def insert_treasury(conn, mv, cat, desc, amt, pm, details="---"):
    if amt > 0 and pm != "آجل": conn.execute("INSERT INTO treasury (date,time,movement_type,category,description,amount,pay_method,method_details) VALUES (?,?,?,?,?,?,?,?)", (now_dt()[0], now_dt()[1], mv, cat, desc, amt, pm, details))

def client_debt(conn, client):
    row = conn.execute("SELECT opening_balance FROM customers WHERE name=?", (client,)).fetchone()
    o = float(row[0]) if row else 0
    s = conn.execute("SELECT COALESCE(SUM(total),0)-COALESCE(SUM(paid),0) FROM sales WHERE client=? AND is_return=0", (client,)).fetchone()[0]
    return o + float(s or 0)

def supplier_debt(conn, supplier):
    r = conn.execute("SELECT COALESCE(SUM(total),0)-COALESCE(SUM(paid),0) FROM purchases WHERE supplier=?",(supplier,),).fetchone()[0]
    return float(r or 0)

def weekly_financials(conn, since):
    sales = float(conn.execute("SELECT COALESCE(SUM(total),0) FROM sales WHERE date>=? AND item!='سداد دفعة نقدية' AND is_return=0", (since,)).fetchone()[0] or 0)
    cogs = float(conn.execute("SELECT COALESCE(SUM(s.qty*i.buy_price),0) FROM sales s LEFT JOIN inv i ON s.item=i.name AND s.type=i.type WHERE s.date>=? AND s.item!='سداد دفعة نقدية' AND s.is_return=0", (since,)).fetchone()[0] or 0)
    exp = float(conn.execute("SELECT COALESCE(SUM(amount),0) FROM treasury WHERE date>=? AND movement_type='سحب' AND category!='مشتريات'", (since,)).fetchone()[0] or 0)
    return {"sales": sales, "cogs": cogs, "expenses": exp, "net_profit": sales - cogs - exp}

def wa_phone(phone):
    p = str(phone or "").strip().replace("+", "").replace(" ", "")
    return ("2" + p) if p.startswith("01") and len(p) >= 10 else p

def ai_copilot_parser(cmd, api_key=""):
    conn = get_conn()
    cur = conn.cursor()
    msg = "🤖 لم أفهم الأمر."
    if api_key:
        try:
            items_df = pd.read_sql_query("SELECT name, type, qty, sell_price FROM inv", conn)
            cust_df = pd.read_sql_query("SELECT name FROM customers", conn)
            df_t = pd.read_sql_query("SELECT movement_type, amount FROM treasury", conn)
            cash_balance = df_t[df_t['movement_type']=='إيداع']['amount'].sum() - df_t[df_t['movement_type']=='سحب']['amount'].sum() if not df_t.empty else 0
            low_stock = pd.read_sql_query("SELECT name, qty FROM inv WHERE qty<=10", conn).to_dict('records')
            pending_crm = pd.read_sql_query("SELECT name, status FROM leads WHERE status NOT LIKE '%مغلق%'", conn).to_dict('records')
            
            prompt = f"""أنت مساعد مدير مالي وتسويق لنظام Kobe Green.
            حالة النظام الآن للتحليل:
            - السيولة المتاحة: {cash_balance} ج.م
            - نواقص المخزون: {low_stock}
            - عملاء CRM مفتوحين يحتاجون متابعة: {pending_crm}
            - المنتجات: {items_df.to_json(orient="records", force_ascii=False)}
            
            حلل طلب المستخدم التالي: "{cmd}"
            أرجع النتيجة بـ JSON فقط:
            للبيع: {{"action": "sale", "item": "اسم الصنف", "type": "النوع", "qty": رقم, "price": السعر أو 0, "client": "اسم العميل"}}
            للسداد: {{"action": "payment", "amount": رقم, "client": "اسم العميل"}}
            للتحليلات، الاستفسارات، أو التنبيهات: {{"action": "chat", "message": "نص الرد والتنبيه باللغة العربية بناءً على البيانات"}}
            """
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            resp = requests.post(url, headers={"Content-Type": "application/json"}, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
            if resp.status_code == 200:
                text_out = resp.json()['candidates'][0]['content']['parts'][0]['text'].replace('```json', '').replace('```', '').strip()
                ai_data = json.loads(text_out)
                if ai_data.get('action') == 'chat': return f"🤖 (Gemini) {ai_data['message']}"
                elif ai_data.get('action') == 'sale':
                    qty, price, item_name, item_type, client = float(ai_data['qty']), float(ai_data.get('price', 0)), ai_data['item'], ai_data.get('type', ''), ai_data.get('client', 'عميل نقدي (AI)')
                    if price == 0: price = float(items_df[(items_df['name']==item_name)]['sell_price'].values[0] or 0)
                    total = qty * price
                    d, t = now_dt()
                    inv_no = f"AI-{datetime.now().strftime('%M%S')}"
                    cur.execute("INSERT INTO sales (date, time, inv_no, client, item, type, qty, unit_p, total, paid, discount, is_return, pay_method, shipping_method) VALUES (?,?,?,?,?,?,?,?,?,?,?,0,?,'---')", (d, t, inv_no, client, item_name, item_type, qty, price, total, total, 0, "كاش"))
                    cur.execute("UPDATE inv SET qty = qty - ? WHERE name=? AND type=?", (qty, item_name, item_type))
                    insert_treasury(conn, "إيداع", "مبيعات (AI)", f"فاتورة {inv_no}", total, "كاش", "---")
                    conn.commit()
                    return f"✅ تم تسجيل بيع {qty} {item_name} بـ {total:,.2f} ج.م."
                elif ai_data.get('action') == 'payment':
                    amt, client = float(ai_data['amount']), ai_data['client']
                    cur.execute("INSERT INTO sales (date, time, inv_no, client, item, type, qty, unit_p, total, paid, discount, is_return, pay_method, shipping_method) VALUES (?,?,?,?,?,?,?,?,?,?,?,0,?,'---')", (now_dt()[0], now_dt()[1], f"AI-REC-{datetime.now().strftime('%M%S')}", client, "سداد دفعة (AI)", "-", 0, 0, 0, amt, 0, "كاش"))
                    insert_treasury(conn, "إيداع", "تحصيل ديون", f"سداد من {client}", amt, "كاش", "---")
                    conn.commit()
                    return f"✅ تم تحصيل {amt:,.2f} ج.م من {client}."
        except Exception as e: st.sidebar.warning(f"⚠️ فشل الاتصال بـ Gemini API.")

    cmd_cl = cmd.lower().replace("كيلو", "").replace("كجم", "").replace("بـ", "").replace("بسعر", "").strip()
    nums = re.findall(r'\d+(?:\.\d+)?', cmd_cl)
    try:
        if "بيع" in cmd_cl and len(nums) >= 2:
            qty, price = float(nums[0]), float(nums[1])
            items = pd.read_sql_query("SELECT name, type FROM inv", conn)
            found = next((r for _, r in items.iterrows() if r['name'].split()[0].lower() in cmd_cl), None)
            if found is not None:
                total = qty * price
                cur.execute("INSERT INTO sales (date, time, inv_no, client, item, type, qty, unit_p, total, paid, discount, is_return, pay_method, shipping_method) VALUES (?,?,?,?,?,?,?,?,?,?,?,0,?,'---')", (now_dt()[0], now_dt()[1], f"AI-{datetime.now().strftime('%M%S')}", "عميل نقدي (AI)", found['name'], found['type'], qty, price, total, total, 0, "كاش"))
                cur.execute("UPDATE inv SET qty = qty - ? WHERE name=? AND type=?", (qty, found['name'], found['type']))
                insert_treasury(conn, "إيداع", "مبيعات (AI)", "---", total, "كاش", "---")
                conn.commit()
                msg = f"✅ تم تسجيل بيع {qty} {found['name']} بإجمالي {total:,.2f} ج.م."
        elif "سداد" in cmd_cl and len(nums) >= 1:
            amt = float(nums[0])
            custs = pd.read_sql_query("SELECT name FROM customers", conn)
            found_c = next((r['name'] for _, r in custs.iterrows() if r['name'].split()[0].lower() in cmd_cl), None)
            if found_c:
                cur.execute("INSERT INTO sales (date, time, inv_no, client, item, type, qty, unit_p, total, paid, discount, is_return, pay_method, shipping_method) VALUES (?,?,?,?,?,?,?,?,?,?,?,0,?,'---')", (now_dt()[0], now_dt()[1], f"AI-REC-{datetime.now().strftime('%M%S')}", found_c, "سداد دفعة (AI)", "-", 0, 0, 0, amt, 0, "كاش"))
                insert_treasury(conn, "إيداع", "تحصيل ديون", f"سداد من {found_c}", amt, "كاش", "---")
                conn.commit()
                msg = f"✅ تم تحصيل {amt:,.2f} ج.م من {found_c}."
    except: pass
    conn.close()
    return msg

def apply_theme():
    st.markdown(f"""<style>@import url('{FONT_URL}'); html, body, [class*="css"] {{ font-family: 'Cairo', sans-serif !important; }}
    .stApp {{ background: #0a110d; color: #ece6da; }}
    .main-header {{ background: linear-gradient(145deg, #1a5238, #143d2a); padding: 20px; border-radius: 15px; text-align: center; border: 1px solid #c19b62; margin-bottom: 20px; box-shadow: 0 5px 15px rgba(0,0,0,0.3);}}
    .lux-metric {{ background: #111d17; border: 1px solid #c19b62; border-radius: 10px; padding: 15px; text-align: center; }}
    .lux-metric .lbl {{ color: #a89a82; font-size: 14px; }}
    .lux-metric .val {{ color: #c19b62; font-size: 24px; font-weight: 900; margin-top: 5px; }}
    .stButton>button {{ background: #143d2a !important; color: #c19b62 !important; border: 1px solid #c19b62 !important; border-radius: 8px !important; }}
    .stButton>button:hover {{ background: #c19b62 !important; color: #143d2a !important; }}
    </style>""", unsafe_allow_html=True)

def lux_box(col, label, value, css=""): col.markdown(f'<div class="lux-metric {css}"><div class="lbl">{label}</div><div class="val">{value}</div></div>', unsafe_allow_html=True)

# ==========================================
# 3. دورة التشغيل الأساسية والواجهة
# ==========================================
apply_theme()

if not st.session_state.logged_in:
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown(f'<div class="main-header">{load_logo_html()}<br><h2>تسجيل الدخول</h2></div>', unsafe_allow_html=True)
        with st.form("login"):
            u, p = st.text_input("اسم المستخدم"), st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("دخول", use_container_width=True):
                with get_conn() as conn: row = conn.execute("SELECT role FROM users WHERE username=? AND password=?", (u.strip(), p)).fetchone()
                if row: st.session_state.logged_in, st.session_state.role, st.session_state.username = True, row[0], u.strip(); st.rerun()
                st.error("بيانات خاطئة")
    st.stop()

cfg = get_settings()
st.sidebar.markdown(f"👤 **{st.session_state.username}**")
if st.sidebar.button("🚪 تسجيل الخروج", key="btn_logout_master"): st.session_state.logged_in = False; st.rerun()
st.sidebar.markdown("---")

st.sidebar.markdown("### 🤖 المساعد الذكي (Gemini Analyst)")
ai_cmd = st.sidebar.chat_input("اطلب تحليل، بيع، أو اسأل (بالصوت أو الكتابة)")
if ai_cmd:
    with st.spinner("جاري التفكير والتحليل..."):
        ai_response = ai_copilot_parser(ai_cmd, cfg.get("gemini_key", ""))
        st.sidebar.success(ai_response)
st.sidebar.markdown("---")

MENU = [
    "🏠 الرئيسية (الداشبورد)", "🛒 المبيعات والمشتريات", "📦 إدارة المخزون", 
    "🏦 الخزينة واليومية", "📑 التقارير وكشوف الحسابات", "🎯 لوحة المبيعات والمهام (CRM)", 
    "عروض الأسعار والكتالوج", "☕ كوبي كاب (Kobe Cup)", "🔥 غرفة التحميص", "📱 التسويق بالواتساب", 
    "🛠️ الإعدادات والتعديل اليدوي", "👑 لوحة تحكم المدير"
]
choice = st.sidebar.radio("القائمة الرئيسية:", MENU)
st.markdown(f'<div class="main-header">{load_logo_html()}<h3 style="color:#c19b62;margin:5px 0;">{DEFAULT_COMPANY}</h3><span style="color:#a89a82">{TAGLINE}</span></div>', unsafe_allow_html=True)
banks_list = get_banks()

# ==========================================
# الصفحات البرمجية
# ==========================================

if choice == "🏠 الرئيسية (الداشبورد)":
    st.markdown("## 📊 نظرة عامة على البيزنس")
    with get_conn() as conn:
        s_today = conn.execute("SELECT SUM(total) FROM sales WHERE date=? AND is_return=0", (now_dt()[0],)).fetchone()[0] or 0
        c_in = conn.execute("SELECT SUM(amount) FROM treasury WHERE movement_type='إيداع'").fetchone()[0] or 0
        c_out = conn.execute("SELECT SUM(amount) FROM treasury WHERE movement_type='سحب'").fetchone()[0] or 0
        inv_val = pd.read_sql_query("SELECT SUM(qty * buy_price) FROM inv", conn).iloc[0,0] or 0
        
        c1, c2, c3, c4 = st.columns(4)
        lux_box(c1, "مبيعات اليوم", f"{s_today:,.2f} ج.م")
        lux_box(c2, "السيولة بالخزينة والبنوك", f"{(c_in - c_out):,.2f} ج.م")
        lux_box(c3, "تكلفة المخزون الحالي", f"{inv_val:,.2f} ج.م")
        lux_box(c4, "عدد الفواتير اليوم", f"{conn.execute('SELECT COUNT(*) FROM sales WHERE date=?', (now_dt()[0],)).fetchone()[0]}")

elif choice == "🛒 المبيعات والمشتريات":
    st.markdown("## 🛒 إدارة المبيعات والمشتريات")
    t_sale, t_buy, t_ret = st.tabs(["🛒 نقطة البيع (إصدار فاتورة)", "📥 إدخال مشتريات للمخزن", "🔙 المرتجعات"])
    
    with t_sale:
        with get_conn() as conn:
            c_df = pd.read_sql_query("SELECT name, pricing_tier, credit_limit FROM customers", conn)
            items = pd.read_sql_query("SELECT name, type, qty, sell_price, wholesale_price, dist_price FROM inv", conn)
        
        cl, cr = st.columns([1, 1.2])
        with cl:
            client = st.selectbox("العميل", ["عميل نقدي"] + c_df['name'].tolist() + ["+ عميل جديد"])
            c_tier, c_limit = "قطاعي", 10000.0
            if client == "+ عميل جديد":
                client = st.text_input("اسم العميل الجديد")
            elif client != "عميل نقدي":
                c_info = c_df[c_df['name'] == client].iloc[0]
                c_tier, c_limit = c_info['pricing_tier'], float(c_info['credit_limit'])
                with get_conn() as conn: st.info(f"شريحة العميل: **{c_tier}** | الديون الحالية: **{client_debt(conn, client):,.2f}**")

            if not items.empty:
                options = [f"{r['name']} | {r['type']}" for _, r in items.iterrows()]
                sel = st.selectbox("الصنف", options)
                idx = options.index(sel)
                i_row = items.iloc[idx]
                i_n, i_t = str(i_row['name']), str(i_row['type'])
                
                def_p = i_row['sell_price']
                if c_tier == "جملة" and i_row['wholesale_price'] > 0: def_p = i_row['wholesale_price']
                elif c_tier == "موزعين" and i_row['dist_price'] > 0: def_p = i_row['dist_price']
                
                qty = st.number_input("الكمية", 0.1, value=1.0)
                up = st.number_input("السعر", 0.0, value=float(def_p))
                if st.button("➕ إضافة للفاتورة"): st.session_state.cart.append({"item": i_n, "type": i_t, "qty": qty, "p": up, "t": qty*up}); st.rerun()
                    
            if st.session_state.cart:
                st.dataframe(pd.DataFrame(st.session_state.cart), use_container_width=True)
                if st.button("🗑️ مسح الكل"): st.session_state.cart = []; st.rerun()
                
                gross = sum(x["t"] for x in st.session_state.cart)
                disc = st.number_input("خصم", 0.0, gross, 0.0)
                net = gross - disc
                paid = st.number_input("المدفوع", 0.0, value=float(net))
                pm = st.selectbox("الدفع", PAY_METHODS)
                bank_ch = st.selectbox("إلى حساب:", banks_list) if pm in ["تحويل بنكي", "محفظة"] else "---"
                
                if st.button("✅ إصدار الفاتورة وتأكيد البيع"):
                    d, tm = now_dt()
                    inv_no = f"INV-{datetime.now().strftime('%M%S')}"
                    cf = client or "عميل نقدي"
                    with get_conn() as conn:
                        if cf != "عميل نقدي": conn.execute("INSERT OR IGNORE INTO customers (name) VALUES (?)", (cf,))
                        for i, ln in enumerate(st.session_state.cart):
                            ld, lp = (disc, paid) if i == 0 else (0, 0)
                            conn.execute("INSERT INTO sales (date,time,inv_no,client,item,type,qty,unit_p,total,paid,discount,pay_method,is_return) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)", (d, tm, inv_no, cf, ln["item"], ln["type"], ln["qty"], ln["p"], ln["t"]-ld, lp, ld, pm))
                            conn.execute("UPDATE inv SET qty=qty-? WHERE name=? AND type=?", (ln["qty"], ln["item"], ln["type"]))
                        insert_treasury(conn, "إيداع", "مبيعات", f"فاتورة {inv_no}", paid, pm, bank_ch)
                        conn.commit()
                    st.session_state.inv_res = {"no": inv_no, "d": d, "c": cf, "cart": list(st.session_state.cart), "gross": gross, "disc": disc, "net": net, "paid": paid, "rem": net-paid, "pay": pm}
                    st.session_state.cart = []; st.rerun()

        with cr:
            if "inv_res" in st.session_state: show_capture_component(build_invoice_html(st.session_state.inv_res, get_settings()), f"INV_{st.session_state.inv_res['no']}")

    with t_buy:
        with get_conn() as conn: supps = [r[0] for r in conn.execute("SELECT name FROM suppliers").fetchall()]
        c1, c2 = st.columns(2)
        sup = c1.selectbox("المورد", ["+ مورد جديد"] + supps)
        if sup == "+ مورد جديد": sup = c1.text_input("اسم المورد الجديد")
        item, ity, qty = c1.text_input("اسم الصنف الوارد"), c1.selectbox("النوع", ITEM_TYPES), c1.number_input("كمية الشراء", min_value=0.01)
        bp, sp = c2.number_input("تكلفة الشراء للوحدة", 0.0), c2.number_input("سعر البيع للجمهور", 0.0)
        tot = qty * bp
        paid = c2.number_input("المدفوع للمورد", value=float(tot))
        ppm = c2.selectbox("طريقة سداد المورد", PAY_METHODS)
        bank_ch = c2.selectbox("من حساب:", banks_list) if ppm in ["تحويل بنكي", "محفظة"] else "---"
        
        if st.button("📥 دخول المخزن وتأكيد الشراء") and sup and item:
            with get_conn() as conn:
                conn.execute("INSERT OR IGNORE INTO suppliers (name) VALUES (?)", (sup,))
                conn.execute("INSERT INTO purchases (date,time,supplier,item,type,qty,total,paid,pay_method) VALUES (?,?,?,?,?,?,?,?,?)", (now_dt()[0], now_dt()[1], sup, item, ity, qty, tot, paid, ppm))
                conn.execute("INSERT INTO inv (name,type,qty,buy_price,sell_price) VALUES (?,?,?,?,?) ON CONFLICT(name,type) DO UPDATE SET qty=qty+?,buy_price=?,sell_price=?", (item, ity, qty, bp, sp, qty, bp, sp))
                insert_treasury(conn, "سحب", "مشتريات", sup, paid, ppm, bank_ch)
                conn.commit(); st.success("تم الشراء والتحديث!"); st.rerun()
                
    with t_ret:
        st.markdown("### 🔙 تسجيل مرتجع من عميل")
        with get_conn() as conn:
            c_df = pd.read_sql_query("SELECT name FROM customers", conn)
            items = pd.read_sql_query("SELECT name, type FROM inv", conn)
        
        c_ret = st.selectbox("العميل (المرتجع):", ["عميل نقدي"] + c_df['name'].tolist(), key="ret_client")
        if not items.empty:
            ret_item_opts = [f"{r['name']} | {r['type']}" for _, r in items.iterrows()]
            ret_sel = st.selectbox("الصنف المرتجع:", ret_item_opts, key="ret_item")
            ret_n, ret_t = ret_sel.split(" | ")
            ret_qty = st.number_input("الكمية المرتجعة:", 0.1, value=1.0, key="ret_qty")
            ret_price = st.number_input("سعر الوحدة (للاسترداد):", 0.0, value=0.0, key="ret_price")
            ret_pm = st.selectbox("طريقة رد المبلغ للعميل:", PAY_METHODS, key="ret_pm")
            ret_bank = st.selectbox("سحب من حساب:", banks_list, key="ret_bank") if ret_pm in ["تحويل بنكي", "محفظة"] else "---"

            if st.button("🔙 تأكيد المرتجع"):
                ret_total = ret_qty * ret_price
                d, tm = now_dt()
                inv_no = f"RET-{datetime.now().strftime('%M%S')}"
                with get_conn() as conn:
                    conn.execute("INSERT INTO sales (date,time,inv_no,client,item,type,qty,unit_p,total,paid,discount,pay_method,is_return) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)", (d, tm, inv_no, c_ret, ret_n, ret_t, ret_qty, ret_price, ret_total, ret_total, 0, ret_pm))
                    conn.execute("UPDATE inv SET qty=qty+? WHERE name=? AND type=?", (ret_qty, ret_n, ret_t))
                    if ret_total > 0 and ret_pm != "آجل":
                        insert_treasury(conn, "سحب", "مرتجعات مبيعات", f"مرتجع {inv_no}", ret_total, ret_pm, ret_bank)
                    conn.commit()
                st.success("تم تسجيل المرتجع وإعادة البضاعة للمخزن بنجاح!")
                st.rerun()

elif choice == "📦 إدارة المخزون":
    st.markdown("## 📦 الجرد وحالة المخزون")
    with get_conn() as conn:
        t_stock, t_sales_track, t_purch_track = st.tabs(["📊 حالة المخزون الحالية", "📤 حركة المبيعات المنصرفة", "📥 حركة المشتريات الواردة"])
        
        with t_stock:
            df = pd.read_sql_query("SELECT name الصنف, type النوع, qty الكمية, buy_price 'تكلفة الشراء', sell_price 'سعر البيع' FROM inv ORDER BY type", conn)
            if not df.empty:
                st.warning(f"إجمالي قيمة المخزون الحالية (بالتكلفة): **{(df['الكمية'] * df['تكلفة الشراء']).sum():,.2f} ج.م**")
                st.dataframe(df, use_container_width=True)
                
        with t_sales_track:
            st.markdown("#### 📤 سجل البضاعة المباعة (المنصرف)")
            df_s = pd.read_sql_query("SELECT date 'التاريخ', time 'الوقت', inv_no 'رقم الفاتورة', client 'العميل', item 'الصنف', type 'النوع', qty 'الكمية', total 'الإجمالي' FROM sales WHERE is_return=0 AND item!='سداد دفعة نقدية' ORDER BY id DESC LIMIT 200", conn)
            st.dataframe(df_s, use_container_width=True)
            
        with t_purch_track:
            st.markdown("#### 📥 سجل البضاعة المشتراة (الوارد)")
            df_p = pd.read_sql_query("SELECT date 'التاريخ', time 'الوقت', supplier 'المورد', item 'الصنف', type 'النوع', qty 'الكمية', total 'الإجمالي' FROM purchases WHERE item!='سداد دفعة نقدية' AND supplier!='نقل داخلي لكوبي كاب' ORDER BY id DESC LIMIT 200", conn)
            st.dataframe(df_p, use_container_width=True)

elif choice == "🏦 الخزينة واليومية":
    st.markdown("## 🏦 الخزينة ودفتر اليومية")
    t_trs, t_day = st.tabs(["💰 أرصدة الخزينة والبنوك", "📓 دفتر حركات اليوم"])
    with get_conn() as conn:
        with t_trs:
            df_t = pd.read_sql_query("SELECT movement_type, pay_method, method_details, amount FROM treasury", conn)
            
            c_in = df_t[(df_t.movement_type=='إيداع') & (df_t.pay_method=='كاش')].amount.sum() - df_t[(df_t.movement_type=='سحب') & (df_t.pay_method=='كاش')].amount.sum() if not df_t.empty else 0
            
            st.markdown("### 💵 السيولة النقدية (الكاش)")
            lux_box(st.columns(1)[0], "الكاش بالخزينة", f"{c_in:,.2f} ج.م")
            
            st.markdown("### 🏦 أرصدة البنوك والمحافظ")
            bank_df = df_t[df_t['pay_method'].isin(['تحويل بنكي', 'محفظة'])]
            if not bank_df.empty:
                b_summary = {}
                for _, r in bank_df.iterrows():
                    b_name = r['method_details']
                    if b_name == "---" or not b_name: continue
                    b_summary[b_name] = b_summary.get(b_name, 0) + (r['amount'] if r['movement_type'] == 'إيداع' else -r['amount'])
                
                if b_summary:
                    b_cols = st.columns(len(b_summary))
                    for i, (b_name, b_amt) in enumerate(b_summary.items()):
                        lux_box(b_cols[i], b_name, f"{b_amt:,.2f} ج.م")
                else:
                    st.info("لا توجد حركات بنكية مسجلة بتفاصيل.")
            else:
                st.info("لا توجد أرصدة بنكية حالياً.")
            
            st.markdown("---")
            st.markdown("### 📝 إصدار سندات وإيصالات")
            tr1, tr2, tr3 = st.tabs(["💸 مصروفات/إيرادات عامة", "⬇️ تحصيل من عميل", "⬆️ سداد لمورد"])
            
            with tr1:
                mv, cat = st.selectbox("نوع الحركة", ["إيداع", "سحب"]), st.text_input("التصنيف (مثال: نثريات، كهرباء، إيجار)")
                amt, pm = st.number_input("المبلغ", 0.01, key="gen_amt"), st.selectbox("الحساب", ["كاش", "تحويل بنكي", "محفظة"], key="gen_pm")
                det_g = st.selectbox("الحساب البنكي:", banks_list, key="gen_b") if pm in ["تحويل بنكي", "محفظة"] else "---"
                if st.button("تسجيل الحركة", key="gen_btn"): 
                    insert_treasury(conn, mv, cat, "حركة يدوية", amt, pm, det_g)
                    conn.commit(); st.rerun()
            
            with tr2:
                custs = pd.read_sql_query("SELECT name FROM customers", conn)['name'].tolist()
                if custs:
                    sel_c = st.selectbox("العميل", custs, key="tr_c")
                    amt_c = st.number_input("المبلغ المحصل", 0.01, key="tr_amt_c")
                    pm_c = st.selectbox("إيداع في حساب", ["كاش", "تحويل بنكي", "محفظة"], key="tr_pm_c")
                    det_c = st.selectbox("الحساب البنكي:", banks_list, key="tr_b_c") if pm_c in ["تحويل بنكي", "محفظة"] else "---"
                    if st.button("تأكيد التحصيل (سند قبض)", key="tr_btn_c"):
                        conn.execute("INSERT INTO sales (date, time, inv_no, client, item, type, qty, unit_p, total, paid, discount, is_return, pay_method, shipping_method) VALUES (?,?,?,?,?,?,?,?,?,?,?,0,?,'---')", (now_dt()[0], now_dt()[1], f"REC-{datetime.now().strftime('%M%S')}", sel_c, "سداد دفعة نقدية", "-", 0, 0, 0, amt_c, 0, pm_c))
                        insert_treasury(conn, "إيداع", "تحصيل ديون", f"سداد من {sel_c}", amt_c, pm_c, det_c)
                        conn.commit(); st.success("تم التحصيل بنجاح!"); st.rerun()
            
            with tr3:
                supps = pd.read_sql_query("SELECT name FROM suppliers", conn)['name'].tolist()
                if supps:
                    sel_s = st.selectbox("المورد", supps, key="tr_s")
                    amt_s = st.number_input("المبلغ المسدد", 0.01, key="tr_amt_s")
                    pm_s = st.selectbox("سحب من حساب", ["كاش", "تحويل بنكي", "محفظة"], key="tr_pm_s")
                    det_s = st.selectbox("الحساب البنكي:", banks_list, key="tr_b_s") if pm_s in ["تحويل بنكي", "محفظة"] else "---"
                    if st.button("تأكيد السداد (سند صرف)", key="tr_btn_s"):
                        conn.execute("INSERT INTO purchases (date,time,supplier,item,type,qty,total,paid,pay_method) VALUES (?,?,?,?,?,?,?,?,?)", (now_dt()[0], now_dt()[1], sel_s, "سداد دفعة نقدية", "-", 0, 0, amt_s, pm_s))
                        insert_treasury(conn, "سحب", "سداد ديون", f"سداد لـ {sel_s}", amt_s, pm_s, det_s)
                        conn.commit(); st.success("تم السداد بنجاح!"); st.rerun()
            
            st.dataframe(pd.read_sql_query("SELECT date التاريخ, time الوقت, movement_type النوع, category البند, amount المبلغ, pay_method الوسيلة, method_details 'تفاصيل الحساب' FROM treasury ORDER BY id DESC LIMIT 100", conn), use_container_width=True)

        with t_day:
            day = st.date_input("اختر التاريخ", datetime.now()).strftime("%Y-%m-%d")
            parts = [
                pd.read_sql_query("SELECT time الوقت,'مبيعات' النوع,client الطرف,total المبلغ FROM sales WHERE date=? AND is_return=0", conn, params=(day,)),
                pd.read_sql_query("SELECT time الوقت,'مشتريات' النوع,supplier الطرف,total المبلغ FROM purchases WHERE date=?", conn, params=(day,)),
                pd.read_sql_query("SELECT time الوقت,'خزينة ('||movement_type||')' النوع,category الطرف,amount المبلغ FROM treasury WHERE date=?", conn, params=(day,)),
            ]
            df_day = pd.concat(parts, ignore_index=True)
            if df_day.empty: st.info("لا توجد حركات في هذا اليوم.")
            else: st.dataframe(df_day.sort_values(by="الوقت", ascending=False).reset_index(drop=True), use_container_width=True)

elif choice == "📑 التقارير وكشوف الحسابات":
    st.markdown("## 📑 التقارير المالية وحسابات العملاء")
    t_daily, t_prof, t_stmt = st.tabs(["📅 تقرير إقفال اليوم", "📈 التقرير الأسبوعي للأرباح", "👥 كشوف حسابات العملاء"])
    with get_conn() as conn:
        with t_daily:
            sel_date = st.date_input("اختر اليوم للتقرير:", datetime.now()).strftime("%Y-%m-%d")
            st.markdown(f"### 📊 ملخص يوم: {sel_date}")
            
            day_sales = conn.execute("SELECT COALESCE(SUM(total),0) FROM sales WHERE date=? AND item!='سداد دفعة نقدية' AND is_return=0", (sel_date,)).fetchone()[0]
            day_purchases = conn.execute("SELECT COALESCE(SUM(total),0) FROM purchases WHERE date=? AND item!='سداد دفعة نقدية' AND supplier!='نقل داخلي لكوبي كاب'", (sel_date,)).fetchone()[0]
            day_in = conn.execute("SELECT COALESCE(SUM(amount),0) FROM treasury WHERE date=? AND movement_type='إيداع'", (sel_date,)).fetchone()[0]
            day_out = conn.execute("SELECT COALESCE(SUM(amount),0) FROM treasury WHERE date=? AND movement_type='سحب'", (sel_date,)).fetchone()[0]
            
            new_clients = pd.read_sql_query("SELECT DISTINCT client FROM sales WHERE date=? AND client NOT IN (SELECT DISTINCT client FROM sales WHERE date < ?)", conn, params=(sel_date, sel_date))
            hot_leads = pd.read_sql_query("SELECT name, phone, status, notes FROM leads WHERE status IN ('تفاوض', 'إرسال عينة')", conn)
            
            d1, d2, d3, d4 = st.columns(4)
            lux_box(d1, "مبيعات بضاعة", f"{day_sales:,.2f} ج.م")
            lux_box(d2, "مشتريات بضاعة", f"{day_purchases:,.2f} ج.م")
            lux_box(d3, "أموال محصلة (إيداع)", f"{day_in:,.2f} ج.م", "profit")
            lux_box(d4, "أموال مدفوعة (سحب)", f"{day_out:,.2f} ج.م", "expense")
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("#### 🌟 عملاء اشتروا لأول مرة هذا اليوم")
                valid_new = [c for c in new_clients['client'].tolist() if "عميل نقدي" not in c]
                if valid_new:
                    for c in valid_new: st.success(f"🤝 {c}")
                else:
                    st.info("لا يوجد عملاء جدد اليوم.")
            with col_b:
                st.markdown("#### 🔥 عملاء CRM اقتربوا من الشراء (Hot Leads)")
                if not hot_leads.empty:
                    st.dataframe(hot_leads, use_container_width=True)
                else:
                    st.info("لا يوجد عملاء في مرحلة التفاوض أو إرسال العينات حالياً.")

        with t_prof:
            since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            fin = weekly_financials(conn, since)
            c1, c2, c3, c4 = st.columns(4)
            lux_box(c1, "مبيعات آخر 7 أيام", f"{fin['sales']:,.2f}")
            lux_box(c2, "تكلفة البضاعة المباعة", f"{fin['cogs']:,.2f}")
            lux_box(c3, "المصروفات النثرية", f"{fin['expenses']:,.2f}")
            lux_box(c4, "صافي الربح التقديري", f"{fin['net_profit']:,.2f}")
            if PLOTLY_AVAILABLE:
                ds = pd.read_sql_query("SELECT date, SUM(total) AS sales FROM sales WHERE date>=? AND is_return=0 GROUP BY date", conn, params=(since,))
                if not ds.empty: st.plotly_chart(px.bar(ds, x="date", y="sales", title="تريند المبيعات اليومية", color_discrete_sequence=["#c19b62"]).update_layout(**plotly_layout()), use_container_width=True)

        with t_stmt:
            custs = pd.read_sql_query("SELECT name, opening_balance FROM customers", conn)
            if not custs.empty:
                sel = st.selectbox("اختر العميل لطباعة كشف حسابه:", custs['name'].tolist())
                info = custs[custs['name'] == sel].iloc[0]
                moves = pd.read_sql_query("SELECT date, item, qty, total, paid, pay_method FROM sales WHERE client=? ORDER BY date, id", conn, params=(sel,))
                
                run = float(info['opening_balance'])
                rows = f"<tr><td>-</td><td>رصيد افتتاحي</td><td>-</td><td>{run:,.2f}</td><td>-</td><td><b>{run:,.2f}</b></td></tr>" if run else ""
                for _, r in moves.iterrows():
                    run += float(r['total']) - float(r['paid'])
                    rows += f"<tr><td>{r['date']}</td><td>{r['item']}</td><td>{r['qty']}</td><td>{r['total']:,.2f}</td><td>{r['paid']:,.2f}</td><td><b>{run:,.2f}</b></td></tr>"
                
                show_capture_component(build_statement_html(sel, rows, run, now_dt()[0], get_settings()), f"STMT_{sel}")

elif choice == "🎯 لوحة المبيعات والمهام (CRM)":
    st.markdown("## 🎯 إدارة العملاء المحتملين ومهام العمل (CRM & To-Do)")
    
    col_todo, col_crm = st.columns([1, 2.5])
    
    with get_conn() as conn:
        with col_todo:
            st.markdown("### ✅ قائمة المهام (To-Do)")
            new_task = st.text_input("مهمة جديدة (مثال: كلم كافيه فلان)")
            if st.button("إضافة مهمة") and new_task:
                conn.execute("INSERT INTO todos (task, created_at) VALUES (?,?)", (new_task, now_dt()[0]))
                conn.commit(); st.rerun()
            
            todos_df = pd.read_sql_query("SELECT * FROM todos WHERE is_done=0 ORDER BY id DESC", conn)
            for _, row in todos_df.iterrows():
                cc1, cc2 = st.columns([0.15, 0.85])
                done = cc1.checkbox("", key=f"t_{row['id']}")
                cc2.markdown(f"<span style='font-size:14px;color:#e8d5b5;'>{row['task']}</span>", unsafe_allow_html=True)
                if done:
                    conn.execute("UPDATE todos SET is_done=1 WHERE id=?", (row['id'],))
                    conn.commit(); st.rerun()

        with col_crm:
            st.markdown("### 📊 مسار المبيعات (Pipeline)")
            with st.expander("➕ إضافة عميل محتمل جديد (Lead)"):
                c1, c2 = st.columns(2)
                n_name = c1.text_input("اسم الكافيه / العميل")
                n_phone = c1.text_input("رقم الموبايل (للواتساب)")
                n_src = c2.selectbox("مصدر العميل", ["فيسبوك", "إنستغرام", "توصية", "زيارة ميدانية", "واتساب", "أخرى"])
                n_notes = c2.text_input("الطلبات أو الملاحظات المبدئية")
                if st.button("💾 حفظ الكارت"):
                    conn.execute("INSERT INTO leads (date, name, phone, status, source, notes) VALUES (?,?,?, 'جديد', ?, ?)", (now_dt()[0], n_name, n_phone, n_src, n_notes))
                    conn.commit(); st.rerun()

            leads_df = pd.read_sql_query("SELECT * FROM leads", conn)
            statuses = ["جديد", "جاري التواصل", "إرسال عينة", "تفاوض", "مغلق - فاز", "مغلق - خسر"]
            k_cols = st.columns(len(statuses))
            
            for i, status in enumerate(statuses):
                with k_cols[i]:
                    st.markdown(f'<div style="text-align:center;font-weight:900;font-size:14px;color:#143d2a;background:#d4af6a;padding:5px;border-radius:4px;margin-bottom:10px;">{status}</div>', unsafe_allow_html=True)
                    subset = leads_df[leads_df['status'] == status]
                    for _, row in subset.iterrows():
                        st.markdown(f'<div style="background:#143d2a;padding:10px;border-radius:6px;border-right:3px solid #d4af6a;margin-bottom:8px;"><h4 style="margin:0;color:#fff;font-size:14px;">{row["name"]}</h4><p style="margin:4px 0;color:#ccc;font-size:12px;">📞 {row["phone"]}</p></div>', unsafe_allow_html=True)
                        with st.expander("تعديل", expanded=False):
                            new_stat = st.selectbox("نقل إلى:", statuses, index=statuses.index(status), key=f"s_{row['id']}")
                            add_note = st.text_input("ملاحظة:", key=f"n_{row['id']}")
                            if st.button("حفظ", key=f"b_{row['id']}"):
                                final_notes = f"{row['notes']} | {add_note}" if add_note else row['notes']
                                conn.execute("UPDATE leads SET status=?, notes=? WHERE id=?", (new_stat, final_notes, row['id']))
                                conn.commit(); st.rerun()

elif choice == "عروض الأسعار والكتالوج":
    st.markdown("## 📝 إصدار عروض الأسعار وقوائم المنتجات")
    with get_conn() as conn:
        st.markdown("### ⚙️ إعدادات العرض")
        col1, col2 = st.columns(2)
        b_choice = col1.radio("تخصيص الهوية (البراند):", ["كوبي جرين (جملة وتوريدات - زيتي)", "كوبي كاب (تجزئة - برتقالي)"])
        brand_key = "green" if "جرين" in b_choice else "cup"
        tier_choice = col2.selectbox("شريحة التسعير المطبقة على العرض:", PRICING_TIERS)
        
        t_quote, t_menu = st.tabs(["📝 إصدار كوتيشن (Quotation)", "🎨 توليد المنيو للطباعة (A4)"])
        
        inv_df = pd.read_sql_query("SELECT name, type, sell_price, wholesale_price, dist_price FROM inv WHERE sell_price>0", conn)
        def get_price(r):
            if tier_choice == "جملة" and r['wholesale_price'] > 0: return r['wholesale_price']
            if tier_choice == "موزعين" and r['dist_price'] > 0: return r['dist_price']
            return r['sell_price']
        inv_df['price'] = inv_df.apply(get_price, axis=1)
        
        with t_quote:
            st.markdown("#### 📄 إنشاء عرض أسعار مخصص")
            qcname = st.text_input("موجه إلى السادة:", "عزيزي العميل")
            options_q = [f"{r['name']} | {r['type']}" for _, r in inv_df.iterrows()]
            picked = st.multiselect("اختر الأصناف لعرض السعر:", options_q)
            if picked:
                qrows = ""
                for p in picked:
                    n, t = p.split(" | ")
                    price = inv_df[(inv_df['name']==n) & (inv_df['type']==t)]['price'].values[0]
                    qrows += f"<tr><td>{n} <br><span style='font-size:12px;color:#777;'>النوع: {t}</span></td><td style='font-size:18px;'>{price:,.2f} ج.م</td></tr>"
                exp = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
                show_capture_component(build_quote_html(qcname, qrows, exp, now_dt()[0], get_settings(), brand=brand_key), f"Quote_{qcname}")

        with t_menu:
            st.markdown("#### 🎨 تصميم وتوليد القائمة (المنيو)")
            c1, c2 = st.columns(2)
            menu_title = c1.text_input("عنوان المنيو (اتركه فارغاً للإلغاء):", "KOBE GREEN" if brand_key=="green" else "KOBE CUP")
            menu_sub = c2.text_input("النص الفرعي:", "قائمة أسعار التوريد والجملة" if brand_key=="green" else "أفخر أنواع القهوة المختصة - قطاع التجزئة")
            
            template_choice = st.selectbox(
                "اختر قالب التصميم (A4):",
                [1, 2, 3],
                format_func=lambda x: {
                    1: "1 — Classic Luxury (ذهبي مع هوية البراند)",
                    2: "2 — Minimalist Executive (أبيض وداكن - للطباعة العادية)",
                    3: "3 — Royal Emerald (زمردي ملكي - فخم جداً)",
                }[x]
            )
            
            all_prods = inv_df.to_dict('records')
            if all_prods and st.button("🎨 توليد المنيو الآن"):
                show_capture_component(build_menu_html(all_prods, get_settings(), template=template_choice, title=menu_title, subtitle=menu_sub, brand=brand_key), "Generated_Menu", a4=True)

elif choice == "☕ كوبي كاب (Kobe Cup)":
    st.markdown(f'<div style="background:linear-gradient(135deg, #f97316, #ea580c);padding:25px;border-radius:12px;color:#fff;text-align:center;margin-bottom:25px;box-shadow:0 10px 20px rgba(234, 88, 12, 0.2);"> <h1 style="margin:0;font-size:42px;font-weight:900;letter-spacing:2px;color:#fff;">☕ KOBE CUP</h1><p style="margin:10px 0 0 0;font-size:18px;opacity:0.9;">نظام إدارة التجزئة المنفصل (عملاء، فواتير، وتجارة إلكترونية)</p></div>', unsafe_allow_html=True)
    
    with get_conn() as conn:
        t_pos, t_inv, t_ecom, t_cust = st.tabs(["🛒 كاشير التجزئة", "📦 مخزون ونقل داخلي", "🌐 التجارة الإلكترونية", "👥 عملاء التجزئة"])
        
        with t_inv:
            st.markdown("### 📦 مخزون التجزئة (كوبي كاب)")
            kc_types = "('مطحون', 'محمص', 'كوبي كاب')"
            df_kc_inv = pd.read_sql_query(f"SELECT name الصنف, type النوع, qty الكمية, sell_price السعر FROM inv WHERE type IN {kc_types} AND qty > 0", conn)
            st.dataframe(df_kc_inv, use_container_width=True)

            st.markdown("### 🔄 نقل بضاعة من مخزن الجملة للتجزئة")
            src_inv = pd.read_sql_query(f"SELECT name, type, qty, buy_price FROM inv WHERE type NOT IN {kc_types} AND qty > 0", conn)
            if not src_inv.empty:
                c1, c2 = st.columns(2)
                options_src = [f"{r['name']} | {r['type']}" for _, r in src_inv.iterrows()]
                sel_src = c1.selectbox("الصنف المحول من الجملة:", options_src)
                src_n, src_t = sel_src.split(" | ")
                src_row = src_inv[(src_inv['name']==src_n) & (src_inv['type']==src_t)].iloc[0]

                tgt_type = c2.selectbox("نوع الصنف بعد النقل:", ["مطحون", "محمص", "كوبي كاب"])
                tgt_name = c2.text_input("اسم الصنف في كوبي كاب:", value=src_n)
                
                qx = c1.number_input("الكمية المراد نقلها:", 0.1, value=1.0)
                ic = c2.number_input("تكلفة الكيلو (نقل داخلي):", 0.0, value=float(src_row['buy_price']))

                if st.button("📥 تأكيد النقل الداخلي لكوبي كاب"):
                    conn.execute("UPDATE inv SET qty=qty-? WHERE name=? AND type=?", (qx, src_n, src_t))
                    conn.execute("INSERT INTO inv (name,type,qty,buy_price,sell_price) VALUES (?,?,?,?,?) ON CONFLICT(name,type) DO UPDATE SET qty=qty+?,buy_price=?", (tgt_name, tgt_type, qx, ic, ic*1.3, qx, ic))
                    conn.execute("INSERT INTO purchases (date,time,supplier,item,type,qty,total,paid,pay_method) VALUES (?,?, 'نقل داخلي لكوبي كاب', ?, ?, ?, ?, ?, 'داخلي')", (now_dt()[0], now_dt()[1], tgt_name, tgt_type, qx, qx*ic, qx*ic))
                    conn.commit()
                    st.success("تم نقل البضاعة لمخزن التجزئة بنجاح!")
                    st.rerun()

        with t_ecom:
            st.markdown("### 🌐 التجارة الإلكترونية (أمازون، نون، والمتاجر)")
            ec1, ec2, ec3 = st.tabs(["📤 نقل بضاعة للمنصات", "💰 تسجيل مبيعات المنصات", "⚙️ إدارة المنصات"])
            with ec3:
                plats = pd.read_sql_query("SELECT name FROM platforms", conn)
                st.info("المنصات الحالية: " + "، ".join(plats['name'].tolist()))
                new_plat = st.text_input("اسم المنصة الجديدة:")
                if st.button("➕ إضافة منصة") and new_plat:
                    try:
                        conn.execute("INSERT INTO platforms (name) VALUES (?)", (new_plat,))
                        conn.commit(); st.success("تم الإضافة!"); st.rerun()
                    except: st.error("موجودة مسبقاً.")
            with ec1:
                plats_list = [r[0] for r in conn.execute("SELECT name FROM platforms").fetchall()]
                inv_all = pd.read_sql_query("SELECT name, type, qty FROM inv WHERE qty > 0", conn)
                if plats_list and not inv_all.empty:
                    c1, c2 = st.columns(2)
                    p_sel = c1.selectbox("اختر المنصة:", plats_list)
                    opts_i = [f"{r['name']} | {r['type']}" for _, r in inv_all.iterrows()]
                    i_sel = c2.selectbox("اختر الصنف:", opts_i)
                    in_, it_ = i_sel.split(" | ")
                    qx = c1.number_input("الكمية المشحونة:", 0.1, value=1.0)
                    if st.button("🚚 شحن للمنصة"):
                        conn.execute("UPDATE inv SET qty=qty-? WHERE name=? AND type=?", (qx, in_, it_))
                        conn.execute("INSERT INTO ecommerce_inv (platform,item,type,qty) VALUES (?,?,?,?) ON CONFLICT(platform,item,type) DO UPDATE SET qty=qty+?", (p_sel, in_, it_, qx, qx))
                        conn.commit(); st.success("تم التوجيه!"); st.rerun()
                st.dataframe(pd.read_sql_query("SELECT platform المنصة, item الصنف, type النوع, qty الكمية FROM ecommerce_inv WHERE qty > 0 ORDER BY platform", conn), use_container_width=True)
            with ec2:
                ei = pd.read_sql_query("SELECT platform, item, type, qty FROM ecommerce_inv WHERE qty > 0", conn)
                if not ei.empty:
                    c1, c2 = st.columns(2)
                    pl_sel = c1.selectbox("المنصة:", ei['platform'].unique())
                    sub_ei = ei[ei['platform'] == pl_sel]
                    item_sel = c2.selectbox("الصنف المباع:", [f"{r['item']} | {r['type']}" for _, r in sub_ei.iterrows()])
                    it_n, it_t = item_sel.split(" | ")
                    s_qty = c1.number_input("الكمية المباعة:", 0.1, value=1.0)
                    gross_p = c2.number_input("إجمالي المبيعة للجمهور:", 0.0, value=0.0)
                    fees = c1.number_input("عمولة المنصة والتخزين:", 0.0, value=0.0)
                    net_p = gross_p - fees
                    if st.button("💵 تأكيد وتسجيل الإيراد"):
                        d, tm = now_dt()
                        conn.execute("UPDATE ecommerce_inv SET qty=qty-? WHERE platform=? AND item=? AND type=?", (s_qty, pl_sel, it_n, it_t))
                        conn.execute("INSERT INTO ecommerce_sales (date, platform, item, qty, gross_price, fees, net_profit) VALUES (?,?,?,?,?,?,?)", (d, pl_sel, it_n, s_qty, gross_p, fees, net_p))
                        insert_treasury(conn, "إيداع", "مبيعات أونلاين", f"مبيعات {pl_sel}", net_p, "تحويل بنكي", "---")
                        conn.commit(); st.success("تم تسجيل الإيراد بصافي الربح!"); st.rerun()
                st.dataframe(pd.read_sql_query("SELECT date التاريخ, platform المنصة, item الصنف, qty الكمية, gross_price الإجمالي, fees العمولة, net_profit الصافي FROM ecommerce_sales ORDER BY id DESC LIMIT 50", conn), use_container_width=True)

        with t_cust:
            c1, c2 = st.columns(2)
            nc_name = c1.text_input("اسم العميل الجديد")
            nc_phone = c2.text_input("رقم الهاتف")
            if st.button("➕ حفظ عميل التجزئة"):
                try:
                    conn.execute("INSERT INTO kc_customers (name,phone) VALUES (?,?)", (nc_name, nc_phone))
                    conn.commit(); st.success("تم!")
                except: st.error("مسجل مسبقاً.")
            st.dataframe(pd.read_sql_query("SELECT name as 'اسم العميل', phone as 'رقم الهاتف' FROM kc_customers ORDER BY id DESC", conn), use_container_width=True)

        with t_pos:
            kc_clients = [r[0] for r in conn.execute("SELECT name FROM kc_customers").fetchall()]
            items = pd.read_sql_query("SELECT name, type, qty, sell_price FROM inv", conn)
            
            cl, cr = st.columns([1, 1.2])
            with cl:
                client = st.selectbox("اختر عميل كوبي كاب:", ["عميل نقدي (تجزئة)"] + kc_clients)
                if not items.empty:
                    options = [f"{r['name']} | {r['type']}" for _, r in items.iterrows()]
                    sel = st.selectbox("الصنف:", options, key="kc_sel")
                    idx = options.index(sel)
                    i_row = items.iloc[idx]
                    qty = st.number_input("الكمية", 0.1, value=1.0, key="kc_qty")
                    up = st.number_input("السعر", 0.0, float(i_row['sell_price']), key="kc_price")
                    if st.button("➕ إضافة للسلة (كوبي كاب)", key="kc_add"):
                        st.session_state['kc_cart'].append({"item": str(i_row['name']), "type": str(i_row['type']), "qty": qty, "p": up, "t": qty*up})
                        st.rerun()
                
                if st.session_state.get('kc_cart'):
                    st.dataframe(pd.DataFrame(st.session_state['kc_cart']).rename(columns={"item":"الصنف", "type":"النوع", "qty":"الكمية", "p":"السعر", "t":"الإجمالي"}), use_container_width=True)
                    if st.button("🗑️ إفراغ السلة", key="kc_clr"): st.session_state['kc_cart'] = []; st.rerun()
                    
                    gross = sum(x["t"] for x in st.session_state['kc_cart'])
                    disc = st.number_input("الخصم", 0.0, gross, 0.0, key="kc_disc")
                    net = gross - disc
                    paid = st.number_input("المبلغ المدفوع", 0.0, float(net), key="kc_paid")
                    pm = st.selectbox("طريقة الدفع", PAY_METHODS, key="kc_pm")
                    bank_ch = st.selectbox("إلى حساب:", banks_list, key="kc_bank") if pm in ["تحويل بنكي", "محفظة"] else "---"
                    
                    if st.button("🟧 إصدار الفاتورة البرتقالية"):
                        d, tm = now_dt()
                        inv_no = f"KC-{datetime.now().strftime('%M%S')}"
                        for i, ln in enumerate(st.session_state['kc_cart']):
                            ld, lp = (disc, paid) if i == 0 else (0, 0)
                            conn.execute("INSERT INTO sales (date,time,inv_no,client,item,type,qty,unit_p,total,paid,discount,pay_method,is_return) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)", (d, tm, inv_no, client, ln["item"], ln["type"], ln["qty"], ln["p"], ln["t"]-ld, lp, ld, pm))
                            conn.execute("UPDATE inv SET qty=qty-? WHERE name=? AND type=?", (ln["qty"], ln["item"], ln["type"]))
                        if paid > 0 and pm != "آجل": insert_treasury(conn, "إيداع", "مبيعات كوبي كاب", f"إيصال {inv_no}", paid, pm, bank_ch)
                        conn.commit()
                        st.session_state.kc_res = {"no": inv_no, "d": d, "c": client, "cart": list(st.session_state['kc_cart']), "gross": gross, "disc": disc, "net": net, "paid": paid, "pay": pm}
                        st.session_state['kc_cart'] = []; st.rerun()

            with cr:
                if "kc_res" in st.session_state:
                    show_capture_component(build_kobecup_invoice_html(st.session_state.kc_res, get_settings()), f"KobeCup_{st.session_state.kc_res['no']}")

elif choice == "🔥 غرفة التحميص":
    st.markdown("## 🔥 غرفة التحميص وحساب الهدر والتكلفة")
    with get_conn() as conn:
        greens = pd.read_sql_query("SELECT name, qty, buy_price, sell_price FROM inv WHERE type='أخضر'", conn)
        if greens.empty:
            st.warning("لا يوجد بن أخضر مسجل.")
        else:
            c1, c2 = st.columns(2)
            gn = c1.selectbox("البن الأخضر المراد تحميصه:", greens['name'].tolist())
            iw = c1.number_input("الوزن الداخل للمحمصة (كجم)", min_value=0.1, value=10.0)
            loss = c1.number_input("نسبة الفاقد المتوقعة (الهدر) %", 0.0, 50.0, 15.0)
            rn = c2.text_input("اسم الصنف المحمص الناتج:", value=f"{gn} محمص")
            
            g = greens[greens['name'] == gn].iloc[0]
            nq = iw * (1 - loss / 100)
            total_cost = iw * float(g['buy_price'])
            rc = total_cost / nq if nq > 0 else 0
            rs = rc * 1.3 
            
            c2.info(f"الصافي المتوقع: **{nq:,.2f} كجم** | التكلفة الجديدة للكيلو: **{rc:,.2f} ج.م**")
            
            if st.button("🔥 تأكيد التحميص وتحديث المخزن") and rn:
                conn.execute("UPDATE inv SET qty=qty-? WHERE name=? AND type='أخضر'", (iw, gn))
                conn.execute("INSERT INTO inv (name,type,qty,buy_price,sell_price) VALUES (?,'محمص',?,?,?) ON CONFLICT(name,type) DO UPDATE SET qty=qty+?,buy_price=?", (rn, nq, rc, rs, nq, rc))
                conn.execute("INSERT INTO roasting_log (date, green_bean, roasted_bean, in_qty, loss_pct, net_qty, cost, sell_price) VALUES (?,?,?,?,?,?,?,?)", (now_dt()[0], gn, rn, iw, loss, nq, rc, rs))
                conn.commit(); st.success("تم التحميص وتحديث الأرصدة بنجاح!"); st.rerun()

elif choice == "📱 التسويق بالواتساب":
    st.markdown("## 📱 حملات التسويق بالواتساب (WhatsApp Marketing)")
    with get_conn() as conn:
        q = "SELECT name, phone FROM customers WHERE phone != '' UNION SELECT name, phone FROM kc_customers WHERE phone != '' UNION SELECT name, phone FROM leads WHERE phone != ''"
        tg = pd.read_sql_query(q, conn).to_dict("records")
    
    st.info(f"يوجد عدد **{len(tg)}** عميل مسجل بأرقام هواتف في النظام (جملة + تجزئة + محتملين).")
    msg = st.text_area("نص الحملة أو العرض الترويجي:", "عروض حصرية من كوبي جرين ☕\n\nاطلب الآن...", height=150)
    
    if st.button("🔗 تجهيز روابط الإرسال") and tg:
        cols = st.columns(4)
        enc = urllib.parse.quote(msg)
        for i, t in enumerate(tg):
            with cols[i%4]:
                phone = wa_phone(t['phone'])
                st.markdown(f'<a href="https://wa.me/{phone}?text={enc}" target="_blank" style="background:#25D366;color:#fff;padding:10px;border-radius:8px;display:block;text-align:center;text-decoration:none;margin-bottom:10px;font-weight:bold;">💬 إرسال لـ {t["name"]}</a>', unsafe_allow_html=True)

elif choice == "🛠️ الإعدادات والتعديل اليدوي":
    st.markdown("## 🛠️ إعدادات النظام المتقدمة")
    t1, t2, t3 = st.tabs(["الإعدادات و Gemini", "تعديل الأسعار والشرائح", "العملاء والائتمان"])
    with get_conn() as conn:
        with t1:
            sc = get_settings()
            cn = st.text_input("الشركة", sc["company_name"])
            ph = st.text_input("الهاتف", sc["phone"])
            ad = st.text_input("العنوان", sc["address"])
            gk = st.text_input("Gemini API Key (مفتاح الذكاء الاصطناعي)", sc.get("gemini_key", ""), type="password")
            if st.button("💾 حفظ الإعدادات الأساسية"):
                conn.execute("UPDATE settings SET company_name=?,phone=?,address=?,gemini_key=? WHERE id=1", (cn, ph, ad, gk))
                conn.commit(); st.success("تم الحفظ!"); st.rerun()
        with t2:
            st.info("حدد أسعار القطاعي، الجملة، والموزعين لكل صنف بدقة.")
            ed_i = st.data_editor(pd.read_sql_query("SELECT id, name, type, qty, sell_price, wholesale_price, dist_price FROM inv", conn), disabled=["id", "name", "type", "qty"], use_container_width=True)
            if st.button("💾 حفظ أسعار الشرائح"):
                for _, r in ed_i.iterrows(): conn.execute("UPDATE inv SET sell_price=?, wholesale_price=?, dist_price=? WHERE id=?", (r['sell_price'], r['wholesale_price'], r['dist_price'], r['id']))
                conn.commit(); st.success("تم التحديث!"); st.rerun()
        with t3:
            st.info("حدد الحد الأقصى للديون (Credit Limit) لكل عميل وشريحة التسعير الخاصة به.")
            ed_c = st.data_editor(pd.read_sql_query("SELECT id, name, pricing_tier, credit_limit, opening_balance FROM customers", conn), column_config={"pricing_tier": st.column_config.SelectboxColumn("الشريحة", options=PRICING_TIERS)}, disabled=["id", "name"], use_container_width=True)
            if st.button("💾 حفظ الائتمان والشرائح"):
                for _, r in ed_c.iterrows(): conn.execute("UPDATE customers SET pricing_tier=?, credit_limit=?, opening_balance=? WHERE id=?", (r['pricing_tier'], r['credit_limit'], r['opening_balance'], r['id']))
                conn.commit(); st.success("تم التحديث!"); st.rerun()

elif choice == "👑 لوحة تحكم المدير":
    if st.session_state.role != "مدير":
        st.error("⛔ عذراً، هذه الصفحة مخصصة لمدير النظام فقط.")
    else:
        st.markdown("## 👑 لوحة تحكم المدير (تعديل وحذف السجلات)")
        st.warning("⚠️ تحذير: أي تعديل أو حذف هنا ينعكس مباشرة على قاعدة البيانات. يرجى توخي الحذر الشديد.")
        
        tables = {
            "المخزون (inv)": "inv",
            "العملاء (customers)": "customers",
            "المبيعات (sales)": "sales",
            "الخزينة (treasury)": "treasury",
            "المشتريات (purchases)": "purchases",
            "الموردين (suppliers)": "suppliers"
        }
        
        table_label = st.selectbox("اختر الجدول المراد تعديله:", list(tables.keys()))
        table_name = tables[table_label]
        
        with get_conn() as conn:
            # نجلب البيانات (حد أقصى 500 سطر لتفادي بطء المتصفح)
            df = pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT 500", conn)
            
            st.info("💡 يمكنك تعديل أي خلية مباشرة، أو تحديد صف والضغط على Delete لمسحه.")
            edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, key=f"editor_{table_name}")
            
            if st.button("💾 تأكيد وحفظ التعديلات في قاعدة البيانات"):
                try:
                    cur = conn.cursor()
                    
                    # 1. Update existing or Insert new rows
                    for _, row in edited_df.iterrows():
                        if pd.notna(row['id']):
                            # Update existing record
                            cols = [c for c in row.index if c != 'id']
                            set_clause = ", ".join([f"{c}=?" for c in cols])
                            vals = [None if pd.isna(row[c]) else row[c] for c in cols] + [row['id']]
                            cur.execute(f"UPDATE {table_name} SET {set_clause} WHERE id=?", vals)
                        else:
                            # Insert new record (if added via the UI)
                            cols = [c for c in row.index if c != 'id']
                            col_names = ", ".join(cols)
                            placeholders = ", ".join(["?"] * len(cols))
                            vals = [None if pd.isna(row[c]) else row[c] for c in cols]
                            cur.execute(f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})", vals)
                    
                    # 2. Handle Deletions
                    original_ids = set(df['id'].dropna().astype(int).tolist())
                    edited_ids = set(edited_df['id'].dropna().astype(int).tolist())
                    deleted_ids = original_ids - edited_ids
                    
                    if deleted_ids:
                        for did in deleted_ids:
                            cur.execute(f"DELETE FROM {table_name} WHERE id=?", (did,))
                            
                    conn.commit()
                    st.success(f"✅ تم حفظ التعديلات على جدول {table_name} بنجاح!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ حدث خطأ أثناء الحفظ: {e}")

elif choice == "⚙️ المستخدمين":
    st.markdown("## ⚙️ إدارة المستخدمين والصلاحيات")
    if st.session_state.role != "مدير":
        st.error("عفواً، هذه الصفحة متاحة لمدير النظام فقط.")
    else:
        with get_conn() as conn:
            st.dataframe(pd.read_sql_query("SELECT id, username, role FROM users", conn), use_container_width=True)
            with st.expander("➕ إضافة مستخدم جديد"):
                nu = st.text_input("اسم المستخدم")
                npw = st.text_input("الرقم السري", type="password")
                nr = st.selectbox("الدور", ["مدير", "كاشير"])
                if st.button("إضافة") and nu and npw:
                    try:
                        conn.execute("INSERT INTO users (username,password,role) VALUES (?,?,?)", (nu, npw, nr))
                        conn.commit(); st.success("تم الإضافة!"); st.rerun()
                    except:
                        st.error("اسم المستخدم مسجل مسبقاً.")