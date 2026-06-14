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

try:
    st.set_page_config(page_title="كوبي جرين ERP", page_icon="☕", layout="wide", initial_sidebar_state="expanded")
except Exception:
    pass

# محاولة استدعاء Plotly
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# ==========================================
# 🌐 Supabase PostgreSQL (Kobe Green ERP)
# ==========================================
USE_SUPABASE = False
SUPABASE_DB_URL = None


def _load_env_file():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_env_file()


def _load_secrets_from_file():
    """Fallback when st.secrets unavailable (common on some local setups)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("SUPABASE_DB_URL") and "=" in line:
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return None


try:
    if hasattr(st, "secrets") and "supabase" in st.secrets and "SUPABASE_DB_URL" in st.secrets["supabase"]:
        SUPABASE_DB_URL = st.secrets["supabase"]["SUPABASE_DB_URL"]
    elif hasattr(st, "secrets") and "SUPABASE_DB_URL" in st.secrets:
        SUPABASE_DB_URL = st.secrets["SUPABASE_DB_URL"]
except Exception:
    pass

if not SUPABASE_DB_URL:
    SUPABASE_DB_URL = os.environ.get("SUPABASE_DB_URL")
if not SUPABASE_DB_URL:
    SUPABASE_DB_URL = _load_secrets_from_file()

def _is_streamlit_cloud():
    return os.path.isdir("/mount/src") or os.environ.get("STREAMLIT_RUNTIME_ENV") == "cloud"


# Supabase دائماً — محلي وسيرفر (نفس إعداد secrets.toml)
# SQLite فقط للطوارئ: ضع ALLOW_LOCAL_SQLITE=1 في البيئة
ALLOW_SQLITE_FALLBACK = os.environ.get("ALLOW_LOCAL_SQLITE") == "1"
USE_SUPABASE = bool(SUPABASE_DB_URL)

if not USE_SUPABASE and not ALLOW_SQLITE_FALLBACK:
    where = "Streamlit Cloud → Settings → Secrets" if _is_streamlit_cloud() else ".streamlit/secrets.toml أو .env"
    st.error(
        f"❌ **Kobe Green يعمل على Supabase فقط.**\n\n"
        f"أضف `SUPABASE_DB_URL` في: **{where}**\n\n"
        f"انسخ المحتوى من ملف `STREAMLIT_SECRETS.txt` ثم Reboot.\n\n"
        f"بدون Supabase لن تُحفظ البيانات."
    )
    st.stop()

if _is_streamlit_cloud() and not USE_SUPABASE:
    st.error(
        "❌ **السيرفر غير مربوط بـ Supabase!**\n\n"
        "Streamlit Cloud → Settings → Secrets → الصق من `STREAMLIT_SECRETS.txt` → Save → Reboot."
    )
    st.stop()

if USE_SUPABASE:
    try:
        import psycopg2
        import psycopg2.extras
        from pg_compat import connect as pg_connect
        from pg_compat import read_sql_query as pg_read_sql_query
    except ImportError:
        st.error("❌ psycopg2-binary is required for Supabase. Run: pip install psycopg2-binary")
        st.stop()

DB_NAME = os.environ.get("KOBE_DB_PATH", "kobecup_master_erp_v7.db")
DEFAULT_COMPANY = "كوبي جرين"
DEFAULT_ADDRESS = "25 شارع محمد علي وسط البلد"
BRAND_EN = "KOBE GREEN"
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
    st.session_state['company_id'] = None
    st.session_state['user'] = None
    st.session_state['cart'] = []
    st.session_state['kc_cart'] = []

def sql_df(query, conn, params=None):
    if USE_SUPABASE:
        return pg_read_sql_query(query, conn, params)
    return pd.read_sql_query(query, conn, params=params)


def get_conn():
    """PostgreSQL on Supabase when configured, otherwise local SQLite."""
    if USE_SUPABASE:
        try:
            return pg_connect(SUPABASE_DB_URL, connect_timeout=5)
        except Exception as e:
            st.error(f"⚠️ Supabase connection failed: {str(e)}")
            st.stop()
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def authenticate_user(username, password):
    """Verify credentials — supports hashed and legacy plain passwords."""
    from kobe_vast.auth_security import verify_password

    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT username, password, role, company_id FROM users WHERE username = ?",
                (username.strip(),),
            )
            row = cur.fetchone()
            if not row:
                return False, None, "اسم المستخدم أو كلمة المرور غير صحيحة"
            if not verify_password(password, row[1]):
                return False, None, "اسم المستخدم أو كلمة المرور غير صحيحة"
            user_data = {
                "username": row[0],
                "role": row[2],
                "company_id": row[3] if len(row) > 3 else None,
            }
            return True, user_data, None
    except Exception as e:
        return False, None, f"خطأ في قاعدة البيانات: {e}"

def migrate_schema():
    if USE_SUPABASE:
        return

    with get_conn() as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(leads)").fetchall()]
        if cols and "source" not in cols:
            conn.execute("ALTER TABLE leads ADD COLUMN source TEXT")
        conn.execute(
            "UPDATE settings SET address=? WHERE id=1 AND (address IS NULL OR address='' OR address=?)",
            (DEFAULT_ADDRESS, "مصر — القاهرة"),
        )
        conn.commit()


@st.cache_resource
def _ensure_supabase_schema(db_url):
    """Run once per server — not on every Streamlit rerun."""
    from auto_migrate_kobe import migrate_supabase_kobe
    migrate_supabase_kobe(db_url)
    try:
        with get_conn() as conn:
            from kobe_vast.db_ensure import ensure_all_late_tables
            ensure_all_late_tables(conn)
    except Exception:
        pass
    return True


def init_db():
    if USE_SUPABASE:
        _ensure_supabase_schema(SUPABASE_DB_URL)
        return

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
        c.execute("""
            CREATE TABLE IF NOT EXISTS api_partners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                partner_name TEXT NOT NULL,
                partner_type TEXT DEFAULT 'متعاون',
                api_key_hash TEXT NOT NULL,
                api_key_prefix TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                revoked_at TEXT,
                last_used_at TEXT,
                notes TEXT DEFAULT '',
                webhook_url TEXT DEFAULT ''
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS shipping_companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                brand TEXT NOT NULL DEFAULT 'green',
                phone TEXT DEFAULT '',
                contact_name TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                UNIQUE(name, brand)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS shipping_cod (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                inv_no TEXT DEFAULT '',
                client TEXT DEFAULT '',
                cod_amount REAL DEFAULT 0,
                shipping_fee REAL DEFAULT 0,
                net_due REAL DEFAULT 0,
                status TEXT DEFAULT 'pending',
                settled_date TEXT,
                notes TEXT DEFAULT ''
            )
        """)

        c.execute("INSERT OR IGNORE INTO settings (id, company_name, phone, address) VALUES (1,?,?,?)", (DEFAULT_COMPANY, "01027766055", DEFAULT_ADDRESS))
        c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', '123', 'مدير')")
        c.execute("INSERT OR IGNORE INTO platforms (name) VALUES ('أمازون (FBA)'), ('نون (FBN)'), ('المتجر الإلكتروني')")
        
        c.execute("SELECT COUNT(*) FROM banks")
        if c.fetchone()[0] == 0:
            for b in ["البنك الأهلي المصري", "بنك مصر", "CIB", "InstaPay"]: c.execute("INSERT OR IGNORE INTO banks (name) VALUES (?)", (b,))
        conn.commit()
    migrate_schema()

try:
    init_db()
except Exception as e:
    st.error(
        f"⚠️ **خطأ في قاعدة البيانات:** {e}\n\n"
        f"**حلول محلية:**\n"
        f"1. شغّل `DIAGNOSE_LOCAL.bat` واقرأ `LOCAL_DIAG.txt`\n"
        f"2. تأكد من الإنترنت واتصال Supabase\n"
        f"3. تأكد من `.env` أو `.streamlit/secrets.toml`"
    )
    if st.button("إعادة المحاولة"):
        st.cache_resource.clear()
        st.rerun()
    st.stop()

if USE_SUPABASE and "_db_ok" not in st.session_state:
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1")
        st.session_state["_db_ok"] = True
    except Exception as e:
        st.error(f"❌ فشل الاتصال بـ Supabase: {e}")
        st.stop()

# ==========================================
# 1. الدوال المساعدة وتصميم الـ HTML
# ==========================================
@st.cache_data(ttl=60, show_spinner=False)
def _load_settings():
    with get_conn() as conn:
        row = conn.execute("SELECT company_name, phone, address, gemini_key FROM settings WHERE id=1").fetchone()
    if row:
        addr = row[2] or ""
        if not addr.strip() or addr.strip() == "مصر — القاهرة":
            addr = DEFAULT_ADDRESS
        return {
            "company_name": row[0] or DEFAULT_COMPANY,
            "phone": row[1] or "",
            "address": addr,
            "gemini_key": row[3] or "",
        }
    return {"company_name": DEFAULT_COMPANY, "phone": "", "address": DEFAULT_ADDRESS, "gemini_key": ""}


@st.cache_data(ttl=60, show_spinner=False)
def _load_banks():
    with get_conn() as conn:
        rows = conn.execute("SELECT name FROM banks ORDER BY name").fetchall()
    return [r[0] for r in rows] if rows else ["بنك افتراضي"]


def get_settings():
    return _load_settings()


def get_banks():
    return _load_banks()


@st.cache_data(ttl=30, show_spinner=False)
def _load_customers_df():
    with get_conn() as conn:
        return sql_df("SELECT name, pricing_tier, credit_limit FROM customers", conn)


@st.cache_data(ttl=30, show_spinner=False)
def _load_inv_df():
    with get_conn() as conn:
        return sql_df("SELECT name, type, qty, sell_price, wholesale_price, dist_price FROM inv", conn)

def plotly_layout():
    return dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Cairo", color="#e8d5b5"), legend=dict(font=dict(color="#e8d5b5")), xaxis=dict(gridcolor="rgba(193,155,98,0.15)", tickfont=dict(color="#e8d5b5")), yaxis=dict(gridcolor="rgba(193,155,98,0.15)", tickfont=dict(color="#e8d5b5")))

def wrap_capture_document(inner_html, file_base, a4=False):
    from kobe_vast.arabic_text import INVOICE_AR_CSS

    a4_css = "width: 800px !important; min-width: 800px !important; max-width: 800px !important; margin: 0 auto; background-color: #fff; padding: 20px; box-sizing: border-box;"
    if a4:
        a4_css = "width: 210mm !important; min-height: 297mm !important; margin: 0 auto !important; background: #fff !important; padding: 12mm !important; box-sizing: border-box !important;"
    fb = file_base.replace("\\", "\\\\").replace("'", "\\'")
    return f"""<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="{FONT_URL}" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <style>
    body{{margin:0;padding:16px;font-family:'Cairo','Tajawal',sans-serif;background:#f0ebe3;direction:rtl;}}
    #capture-area,.ar{{font-family:'Cairo','Tajawal',sans-serif!important;}}
    {INVOICE_AR_CSS}
    [data-html2canvas-ignore]{{text-align:center;margin-bottom:16px;padding:14px;background:#143d2a;border-radius:12px;}}
    [data-html2canvas-ignore] button{{font-family:'Cairo',sans-serif;font-weight:700;padding:12px 24px;margin:6px;
    border-radius:8px;cursor:pointer;background:#c19b62;color:#143d2a;border:none;font-size:16px;}}
    #capture-area{{ {a4_css} }}
    </style></head><body>
    <div data-html2canvas-ignore>
    <button onclick="downloadPDF()">📄 تحميل PDF</button>
    <button onclick="downloadJPG()">🖼️ تحميل JPG</button>
    </div>
    <div style="overflow-x:auto;"><div id="capture-area">{inner_html}</div></div>
    <script>
    const FILE_BASE = '{fb}';
    async function waitFonts() {{
        if (document.fonts && document.fonts.ready) await document.fonts.ready;
        await new Promise(r => setTimeout(r, 800));
    }}
    async function captureCanvas() {{
        await waitFonts();
        const el = document.getElementById('capture-area');
        return await html2canvas(el, {{
            scale: 2, useCORS: true, letterRendering: true,
            windowWidth: { '793' if a4 else '800' },
            onclone: function(doc) {{
                doc.querySelectorAll('.ar').forEach(function(n) {{
                    n.style.fontFamily = "Cairo, Tajawal, sans-serif";
                    n.style.direction = "rtl";
                    n.style.unicodeBidi = "embed";
                    n.style.textAlign = "right";
                }});
            }}
        }});
    }}
    async function downloadJPG() {{
        const canvas = await captureCanvas();
        const link = document.createElement('a');
        link.download = FILE_BASE + '.jpg';
        link.href = canvas.toDataURL('image/jpeg', 0.95);
        link.click();
    }}
    async function downloadPDF() {{
        const canvas = await captureCanvas();
        const img = canvas.toDataURL('image/jpeg', 0.95);
        const {{jsPDF}} = window.jspdf;
        const pdf = new jsPDF('p','mm','a4');
        const pw = pdf.internal.pageSize.getWidth();
        const ph = pdf.internal.pageSize.getHeight();
        const ratio = Math.min(pw/canvas.width, ph/canvas.height);
        pdf.addImage(img,'JPEG',(pw-canvas.width*ratio)/2,10,canvas.width*ratio,canvas.height*ratio);
        pdf.save(FILE_BASE + '.pdf');
    }}
    </script></body></html>"""


def show_invoice_capture(res, cfg, file_base, brand="green"):
    """معاينة فاتورة + PDF/صورة بنفس الشكل (html2canvas)."""
    from kobe_vast.invoice_export import wrap_invoice_document

    cfg = dict(cfg or {})
    if not (cfg.get("address") or "").strip():
        cfg["address"] = DEFAULT_ADDRESS

    html = (
        build_kobecup_invoice_html(res, cfg)
        if brand == "kobecup"
        else build_invoice_html(res, cfg)
    )
    components.html(
        wrap_invoice_document(html, file_base, FONT_URL),
        height=820,
        scrolling=True,
    )


def show_capture_component(inner_html, file_base, a4=False):
    components.html(wrap_capture_document(inner_html, file_base, a4), height=900, scrolling=True)

def load_logo_html(show_title=False):
    if os.path.exists("logo.png"):
        with open("logo.png", "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        img = f'<img src="data:image/png;base64,{b64}" style="max-height:72px;display:block;margin:0 auto;">'
        if show_title:
            return f'{img}<div style="text-align:center;color:#c19b62;font-weight:700;font-size:18px;margin-top:6px;">{DEFAULT_COMPANY}</div>'
        return img
    if show_title:
        return f'<div style="text-align:center;color:#c19b62;font-weight:900;font-size:26px;">{DEFAULT_COMPANY}</div>'
    return ""

def build_invoice_html(res, cfg):
    from kobe_vast.invoice_html import build_green_invoice_html
    return build_green_invoice_html(res, cfg, FONT_URL, load_logo_html, DEFAULT_COMPANY)


def build_kobecup_invoice_html(res, cfg):
    from kobe_vast.invoice_html import build_kc_invoice_html
    return build_kc_invoice_html(res, cfg, FONT_URL)

def build_statement_html(client, rows_html, balance, stmt_date, cfg):
    from kobe_vast.arabic_text import INVOICE_AR_CSS, ar_html
    return f"""<style>@import url('{FONT_URL}');{INVOICE_AR_CSS}.st{{width:100%;font-family:'Cairo',sans-serif;direction:rtl;}}.tbl{{width:100%;border-collapse:collapse;margin:20px 0;}}.tbl th{{background:#143d2a;color:#c19b62;padding:10px;border:1px solid #ccc;}}.tbl td{{text-align:center;padding:8px;border:1px solid #eee;}}</style>
<div class="st"><div style="text-align:center;border-bottom:3px solid #143d2a;padding-bottom:15px;">{load_logo_html()}<h2 class="ar">{ar_html('كشف حساب تفصيلي')}</h2></div>
<div style="display:flex;justify-content:space-between;margin:20px 0;background:#f9f9f9;padding:15px;">
<div class="ar"><b>{ar_html('العميل:')}</b> {ar_html(client)}</div>
<div class="ar"><b>{ar_html('التاريخ:')}</b> {ar_html(stmt_date)}</div></div>
<table class="tbl"><thead><tr>
<th class="ar">{ar_html('التاريخ')}</th><th class="ar">{ar_html('البيان')}</th>
<th class="ar">{ar_html('الكمية')}</th><th class="ar">{ar_html('مدين (عليه)')}</th>
<th class="ar">{ar_html('دائن (سدد)')}</th><th class="ar">{ar_html('الرصيد')}</th>
</tr></thead><tbody>{rows_html}</tbody></table>
<div class="ar" style="text-align:center;background:#143d2a;color:#fff;padding:15px;font-size:20px;border-radius:8px;font-weight:bold;">
{ar_html('الرصيد النهائي المستحق:')} {balance:,.2f} {ar_html('ج.م')}</div></div>"""

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
            items_df = sql_df("SELECT name, type, qty, sell_price FROM inv", conn)
            cust_df = sql_df("SELECT name FROM customers", conn)
            df_t = sql_df("SELECT movement_type, amount FROM treasury", conn)
            cash_balance = df_t[df_t['movement_type']=='إيداع']['amount'].sum() - df_t[df_t['movement_type']=='سحب']['amount'].sum() if not df_t.empty else 0
            low_stock = sql_df("SELECT name, qty FROM inv WHERE qty<=10", conn).to_dict('records')
            pending_crm = sql_df("SELECT name, status FROM leads WHERE status NOT LIKE '%مغلق%'", conn).to_dict('records')
            
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
            items = sql_df("SELECT name, type FROM inv", conn)
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
            custs = sql_df("SELECT name FROM customers", conn)
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
    try:
        from kobe_vast.mobile_ui import inject_mobile_css
        inject_mobile_css()
    except Exception:
        pass
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
        st.markdown(f'<div class="main-header">{load_logo_html(show_title=True)}<h2>تسجيل الدخول</h2></div>', unsafe_allow_html=True)
        with st.form("login"):
            u = st.text_input("اسم المستخدم", placeholder="أدخل اسم المستخدم")
            p = st.text_input("كلمة المرور", type="password", placeholder="8 أحرف على الأقل")
            from kobe_vast.auth_security import password_strength_hint
            st.caption(password_strength_hint())
            
            if st.form_submit_button("دخول آمن", use_container_width=True):
                if not u.strip() or not p:
                    st.error("⚠️ يرجى إدخال اسم المستخدم وكلمة المرور")
                else:
                    # Authenticate user
                    success, user_data, error_msg = authenticate_user(u, p)
                    
                    if success:
                        # Save user info in session state
                        st.session_state.logged_in = True
                        st.session_state.username = user_data['username']
                        st.session_state.role = user_data['role']
                        st.session_state.company_id = user_data.get('company_id')
                        st.session_state.user = user_data
                        
                        st.success(f"✅ مرحباً {user_data['username']}!")
                        st.rerun()
                    else:
                        st.error(f"❌ {error_msg}")
    
    # Show welcome message or instructions
    st.info("💡 للدخول إلى نظام كوبي جرين ERP، يرجى إدخال بيانات الدخول الخاصة بك")
    st.stop()

cfg = get_settings()
st.sidebar.markdown(f"👤 **{st.session_state.username}** | {st.session_state.role}")
if USE_SUPABASE:
    st.sidebar.success("🟢 Supabase — بيانات دائمة")
    try:
        with get_conn() as _kc:
            _pending = _kc.execute(
                "SELECT COUNT(*) FROM kds_orders WHERE status IN ('pending','preparing')"
            ).fetchone()[0]
        if int(_pending or 0) > 0:
            st.sidebar.warning(f"🍳 KDS: {_pending} طلب معلّق")
    except Exception:
        pass
else:
    st.sidebar.error("🔴 SQLite — للتجربة فقط")
if st.sidebar.button("🚪 تسجيل الخروج", key="btn_logout_master"): st.session_state.logged_in = False; st.rerun()
st.sidebar.markdown("---")

def _gemini_context(conn):
    try:
        items_df = sql_df("SELECT name, type, qty, sell_price FROM inv", conn)
        df_t = sql_df("SELECT movement_type, amount FROM treasury", conn)
        cash = (
            df_t[df_t["movement_type"] == "إيداع"]["amount"].sum()
            - df_t[df_t["movement_type"] == "سحب"]["amount"].sum()
            if not df_t.empty
            else 0
        )
        today = now_dt()[0]
        s_today = float(
            conn.execute(
                "SELECT COALESCE(SUM(total),0) FROM sales WHERE date=? AND is_return=0",
                (today,),
            ).fetchone()[0]
            or 0
        )
        low = sql_df("SELECT name, qty FROM inv WHERE qty<=10", conn).to_dict("records")
        return {
            "cash_balance": float(cash),
            "sales_today": s_today,
            "low_stock": low[:10],
            "products": items_df.head(30).to_dict("records"),
            "cart_items": len(st.session_state.get("cart", [])),
        }
    except Exception:
        return {}


def _build_gemini_handlers(conn):
    def execute_sale(data):
        cur = conn.cursor()
        items_df = sql_df("SELECT name, type, qty, sell_price FROM inv", conn)
        qty = float(data.get("qty", 0))
        price = float(data.get("price", 0) or 0)
        item_name = data.get("item", "")
        item_type = data.get("type", "أخضر")
        client = data.get("client", "عميل نقدي (AI)")
        if price == 0 and not items_df.empty:
            m = items_df[(items_df["name"] == item_name) & (items_df["type"] == item_type)]
            if m.empty:
                m = items_df[items_df["name"].str.contains(item_name, na=False)]
            if not m.empty:
                price = float(m.iloc[0]["sell_price"] or 0)
                item_type = str(m.iloc[0]["type"])
        total = qty * price
        d, t = now_dt()
        inv_no = f"AI-{datetime.now().strftime('%M%S')}"
        cur.execute(
            "INSERT INTO sales (date, time, inv_no, client, item, type, qty, unit_p, total, paid, discount, is_return, pay_method, shipping_method) VALUES (?,?,?,?,?,?,?,?,?,?,?,0,?,'---')",
            (d, t, inv_no, client, item_name, item_type, qty, price, total, total, 0, "كاش"),
        )
        cur.execute("UPDATE inv SET qty = qty - ? WHERE name=? AND type=?", (qty, item_name, item_type))
        insert_treasury(conn, "إيداع", "مبيعات (AI)", f"فاتورة {inv_no}", total, "كاش", "---")
        conn.commit()
        return f"✅ تم تسجيل بيع {qty} {item_name} بـ {total:,.2f} ج.م."

    def execute_payment(data):
        amt = float(data.get("amount", 0))
        client = data.get("client", "عميل")
        conn.execute(
            "INSERT INTO sales (date, time, inv_no, client, item, type, qty, unit_p, total, paid, discount, is_return, pay_method, shipping_method) VALUES (?,?,?,?,?,?,?,?,?,?,?,0,?,'---')",
            (now_dt()[0], now_dt()[1], f"AI-REC-{datetime.now().strftime('%M%S')}", client, "سداد دفعة (AI)", "-", 0, 0, 0, amt, 0, "كاش"),
        )
        insert_treasury(conn, "إيداع", "تحصيل ديون", f"سداد من {client}", amt, "كاش", "---")
        conn.commit()
        return f"✅ تم تحصيل {amt:,.2f} ج.م من {client}."

    def execute_report(data):
        msg = data.get("message", "")
        today = now_dt()[0]
        wf = weekly_financials(conn, today)
        ctx = _gemini_context(conn)
        return (
            f"🤖 {msg}\n"
            f"مبيعات اليوم: {ctx.get('sales_today', 0):,.2f} ج.م | "
            f"السيولة: {ctx.get('cash_balance', 0):,.2f} ج.م | "
            f"صافي الأسبوع: {wf['net_profit']:,.2f} ج.م"
        )

    def add_to_cart(data):
        qty = float(data.get("qty", 1))
        price = float(data.get("price", 0) or 0)
        item_name = data.get("item", "")
        item_type = data.get("type", "أخضر")
        if price == 0:
            items_df = sql_df("SELECT name, type, sell_price FROM inv", conn)
            m = items_df[(items_df["name"] == item_name)]
            if not m.empty:
                price = float(m.iloc[0]["sell_price"] or 0)
                item_type = str(m.iloc[0]["type"])
        st.session_state.setdefault("cart", []).append(
            {"item": item_name, "type": item_type, "qty": qty, "p": price, "t": qty * price}
        )
        return f"✅ أضفت {qty} كجم {item_name} للسلة — افتح المبيعات لإصدار الفاتورة"

    return {
        "context": _gemini_context(conn),
        "execute_sale": execute_sale,
        "execute_payment": execute_payment,
        "execute_report": execute_report,
        "add_to_cart": add_to_cart,
    }


try:
    from kobe_vast.gemini_assistant import render_gemini_sidebar

    with st.sidebar.expander("🤖 المساعد الذكي", expanded=False):
        with get_conn() as _gconn:
            render_gemini_sidebar(cfg, _build_gemini_handlers(_gconn))
except Exception as _ge:
    st.sidebar.caption(f"المساعد: {_ge}")
st.sidebar.markdown("---")

from kobe_vast.nav_menu import render_nav

page = render_nav(st.session_state.role)

st.markdown(
    f'<div class="main-header">{load_logo_html(show_title=True)}'
    f'<span style="color:#a89a82;font-size:14px;">{TAGLINE}</span></div>',
    unsafe_allow_html=True,
)
banks_list = get_banks()

# ==========================================
# الصفحات البرمجية
# ==========================================

if page == "home":
    st.markdown("## 📊 نظرة عامة على البيزنس")
    with get_conn() as conn:
        s_today = conn.execute("SELECT SUM(total) FROM sales WHERE date=? AND is_return=0", (now_dt()[0],)).fetchone()[0] or 0
        c_in = conn.execute("SELECT SUM(amount) FROM treasury WHERE movement_type='إيداع'").fetchone()[0] or 0
        c_out = conn.execute("SELECT SUM(amount) FROM treasury WHERE movement_type='سحب'").fetchone()[0] or 0
        inv_val = sql_df("SELECT SUM(qty * buy_price) FROM inv", conn).iloc[0,0] or 0
        
        c1, c2, c3, c4 = st.columns(4)
        lux_box(c1, "مبيعات اليوم", f"{s_today:,.2f} ج.م")
        lux_box(c2, "السيولة بالخزينة والبنوك", f"{(c_in - c_out):,.2f} ج.م")
        lux_box(c3, "تكلفة المخزون الحالي", f"{inv_val:,.2f} ج.م")
        lux_box(c4, "عدد الفواتير اليوم", f"{conn.execute('SELECT COUNT(*) FROM sales WHERE date=?', (now_dt()[0],)).fetchone()[0]}")

elif page == "invoices":
    with get_conn() as conn:
        try:
            from kobe_vast.invoice_registry import render_invoice_history
            render_invoice_history(
                conn, sql_df, show_invoice_capture,
                build_invoice_html, build_kobecup_invoice_html, get_settings,
                key_prefix="inv_main",
            )
        except Exception as e:
            st.error(f"خطأ سجل الفواتير: {e}")

elif page == "sales":
    st.markdown("## 🛒 إدارة المبيعات والمشتريات")
    t_sale, t_hist, t_buy, t_ret = st.tabs([
        "🛒 نقطة البيع (إصدار فاتورة)", "📋 سجل الفواتير",
        "📥 إدخال مشتريات للمخزن", "🔙 المرتجعات",
    ])

    with t_sale:
        c_df = _load_customers_df()
        items = _load_inv_df()
        with get_conn() as conn:
            try:
                from kobe_vast.pos_sales import render_pos_sale_tab
                render_pos_sale_tab(
                    conn, sql_df, items, c_df, banks_list,
                    now_dt, client_debt, insert_treasury,
                    show_invoice_capture, build_invoice_html, get_settings,
                    PAY_METHODS, _load_inv_df.clear, _load_customers_df.clear,
                )
            except Exception as e:
                st.error(f"خطأ نقطة البيع: {e}")

    with t_hist:
        with get_conn() as conn:
            try:
                from kobe_vast.invoice_registry import render_invoice_history
                render_invoice_history(
                    conn, sql_df, show_invoice_capture,
                    build_invoice_html, build_kobecup_invoice_html, get_settings,
                    key_prefix="inv_sales",
                )
            except Exception as e:
                st.error(f"خطأ سجل الفواتير: {e}")

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
            c_df = sql_df("SELECT name FROM customers", conn)
            items = sql_df("SELECT name, type FROM inv", conn)
        
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

        with st.expander("🔙 مرتجع فاتورة دفع مقسّم (كاش + بنكين)"):
            try:
                from kobe_vast.finance_split import render_split_returns_ui
                with get_conn() as conn:
                    render_split_returns_ui(conn, banks_list)
            except Exception as e:
                st.error(str(e))

elif page == "inventory":
    with get_conn() as conn:
        try:
            from kobe_vast.inventory_dashboard import render_inventory_page
            render_inventory_page(conn, sql_df, lux_box)
        except Exception as e:
            st.error(f"خطأ المخزون: {e}")
            st.markdown("## 📦 الجرد وحالة المخزون")
            df = sql_df("SELECT name, type, qty, buy_price, sell_price FROM inv ORDER BY type", conn)
            if not df.empty:
                df = df.rename(columns={"name": "الصنف", "type": "النوع", "qty": "الكمية", "buy_price": "تكلفة الشراء", "sell_price": "سعر البيع"})
                st.dataframe(df, use_container_width=True)

elif page == "treasury":
    st.markdown("## 🏦 الخزينة ودفتر اليومية")
    t_trs, t_ship, t_day = st.tabs(["💰 أرصدة الخزينة والبنوك", "🚚 شركات الشحن", "📓 دفتر حركات اليوم"])
    with get_conn() as conn:
        with t_ship:
            try:
                from kobe_vast.shipping_finance import render_shipping_finance_page
                render_shipping_finance_page(conn, sql_df, lux_box, now_dt, insert_treasury, banks_list)
            except Exception as e:
                st.error(f"خطأ متابعة الشحن: {e}")
        with t_trs:
            df_t = sql_df("SELECT movement_type, pay_method, method_details, amount FROM treasury", conn)
            
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
                custs = sql_df("SELECT name FROM customers", conn)['name'].tolist()
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
                supps = sql_df("SELECT name FROM suppliers", conn)['name'].tolist()
                if supps:
                    sel_s = st.selectbox("المورد", supps, key="tr_s")
                    amt_s = st.number_input("المبلغ المسدد", 0.01, key="tr_amt_s")
                    pm_s = st.selectbox("سحب من حساب", ["كاش", "تحويل بنكي", "محفظة"], key="tr_pm_s")
                    det_s = st.selectbox("الحساب البنكي:", banks_list, key="tr_b_s") if pm_s in ["تحويل بنكي", "محفظة"] else "---"
                    if st.button("تأكيد السداد (سند صرف)", key="tr_btn_s"):
                        conn.execute("INSERT INTO purchases (date,time,supplier,item,type,qty,total,paid,pay_method) VALUES (?,?,?,?,?,?,?,?,?)", (now_dt()[0], now_dt()[1], sel_s, "سداد دفعة نقدية", "-", 0, 0, amt_s, pm_s))
                        insert_treasury(conn, "سحب", "سداد ديون", f"سداد لـ {sel_s}", amt_s, pm_s, det_s)
                        conn.commit(); st.success("تم السداد بنجاح!"); st.rerun()
            
            df_tr = sql_df(
                "SELECT date, time, movement_type, category, amount, pay_method, method_details FROM treasury ORDER BY id DESC LIMIT 100",
                conn,
            )
            if not df_tr.empty:
                df_tr = df_tr.rename(columns={
                    "date": "التاريخ", "time": "الوقت", "movement_type": "النوع",
                    "category": "البند", "amount": "المبلغ", "pay_method": "الوسيلة",
                    "method_details": "تفاصيل الحساب",
                })
            st.dataframe(df_tr, use_container_width=True)

        with t_day:
            day = st.date_input("اختر التاريخ", datetime.now()).strftime("%Y-%m-%d")
            parts = [
                sql_df("SELECT time, client, total FROM sales WHERE date=? AND is_return=0", conn, params=(day,)).assign(النوع="مبيعات").rename(columns={"time": "الوقت", "client": "الطرف", "total": "المبلغ"}),
                sql_df("SELECT time, supplier, total FROM purchases WHERE date=?", conn, params=(day,)).assign(النوع="مشتريات").rename(columns={"time": "الوقت", "supplier": "الطرف", "total": "المبلغ"}),
                sql_df("SELECT time, movement_type, category, amount FROM treasury WHERE date=?", conn, params=(day,)).assign(النوع=lambda d: "خزينة (" + d["movement_type"] + ")").rename(columns={"time": "الوقت", "category": "الطرف", "amount": "المبلغ"}),
            ]
            df_day = pd.concat(parts, ignore_index=True)
            if df_day.empty: st.info("لا توجد حركات في هذا اليوم.")
            else: st.dataframe(df_day.sort_values(by="الوقت", ascending=False).reset_index(drop=True), use_container_width=True)

elif page == "reports":
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
            
            new_clients = sql_df("SELECT DISTINCT client FROM sales WHERE date=? AND client NOT IN (SELECT DISTINCT client FROM sales WHERE date < ?)", conn, params=(sel_date, sel_date))
            hot_leads = sql_df("SELECT name, phone, status, notes FROM leads WHERE status IN ('تفاوض', 'إرسال عينة')", conn)
            
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
                ds = sql_df("SELECT date, SUM(total) AS sales FROM sales WHERE date>=? AND is_return=0 GROUP BY date", conn, params=(since,))
                if not ds.empty: st.plotly_chart(px.bar(ds, x="date", y="sales", title="تريند المبيعات اليومية", color_discrete_sequence=["#c19b62"]).update_layout(**plotly_layout()), use_container_width=True)

        with t_stmt:
            custs = sql_df("SELECT name, opening_balance FROM customers", conn)
            if not custs.empty:
                sel = st.selectbox("اختر العميل لطباعة كشف حسابه:", custs['name'].tolist())
                info = custs[custs['name'] == sel].iloc[0]
                moves = sql_df("SELECT date, item, qty, total, paid, pay_method FROM sales WHERE client=? ORDER BY date, id", conn, params=(sel,))
                
                run = float(info['opening_balance'])
                rows = f"<tr><td>-</td><td>رصيد افتتاحي</td><td>-</td><td>{run:,.2f}</td><td>-</td><td><b>{run:,.2f}</b></td></tr>" if run else ""
                for _, r in moves.iterrows():
                    run += float(r['total']) - float(r['paid'])
                    rows += f"<tr><td>{r['date']}</td><td>{r['item']}</td><td>{r['qty']}</td><td>{r['total']:,.2f}</td><td>{r['paid']:,.2f}</td><td><b>{run:,.2f}</b></td></tr>"
                
                show_capture_component(build_statement_html(sel, rows, run, now_dt()[0], get_settings()), f"STMT_{sel}")

elif page == "tools":
    from kobe_vast.advanced_tools import render_tools_page
    render_tools_page(
        st.session_state.role,
        get_conn,
        sql_df,
        lux_box,
        banks_list,
        get_settings,
        show_capture_component,
        build_quote_html,
        build_menu_html,
        wa_phone,
        now_dt,
        PRICING_TIERS,
    )

elif page == "kobecup":
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#f97316,#ea580c);padding:20px;border-radius:12px;'
        f'color:#fff;text-align:center;margin-bottom:20px;">'
        f'<h2 style="margin:0;font-size:28px;font-weight:900;">🟧 كوبي كاب — التجزئة</h2>'
        f'<p style="margin:6px 0 0;opacity:0.9;font-size:14px;">فواتير · مخزون · أونلاين · عملاء</p></div>',
        unsafe_allow_html=True,
    )
    
    with get_conn() as conn:
        t_pos, t_inv, t_ecom, t_cust = st.tabs(["🛒 كاشير التجزئة", "📦 مخزون ونقل داخلي", "🌐 التجارة الإلكترونية", "👥 عملاء التجزئة"])
        
        with t_inv:
            st.markdown("### 📦 مخزون التجزئة (كوبي كاب)")
            kc_types = "('مطحون', 'محمص', 'كوبي كاب')"
            df_kc_inv = sql_df(f"SELECT name, type, qty, sell_price FROM inv WHERE type IN {kc_types} AND qty > 0", conn)
            if not df_kc_inv.empty:
                df_kc_inv = df_kc_inv.rename(columns={"name": "الصنف", "type": "النوع", "qty": "الكمية", "sell_price": "السعر"})
            st.dataframe(df_kc_inv, use_container_width=True)

            st.markdown("### 🔄 نقل بضاعة من مخزن الجملة للتجزئة")
            src_inv = sql_df(f"SELECT name, type, qty, buy_price FROM inv WHERE type NOT IN {kc_types} AND qty > 0", conn)
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
                plats = sql_df("SELECT name FROM platforms", conn)
                st.info("المنصات الحالية: " + "، ".join(plats['name'].tolist()))
                new_plat = st.text_input("اسم المنصة الجديدة:")
                if st.button("➕ إضافة منصة") and new_plat:
                    try:
                        conn.execute("INSERT INTO platforms (name) VALUES (?)", (new_plat,))
                        conn.commit(); st.success("تم الإضافة!"); st.rerun()
                    except: st.error("موجودة مسبقاً.")
            with ec1:
                plats_list = [r[0] for r in conn.execute("SELECT name FROM platforms").fetchall()]
                inv_all = sql_df("SELECT name, type, qty FROM inv WHERE qty > 0", conn)
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
                df_ec = sql_df("SELECT platform, item, type, qty FROM ecommerce_inv WHERE qty > 0 ORDER BY platform", conn)
                if not df_ec.empty:
                    df_ec = df_ec.rename(columns={"platform": "المنصة", "item": "الصنف", "type": "النوع", "qty": "الكمية"})
                st.dataframe(df_ec, use_container_width=True)
            with ec2:
                ei = sql_df("SELECT platform, item, type, qty FROM ecommerce_inv WHERE qty > 0", conn)
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
                df_es = sql_df(
                    "SELECT date, platform, item, qty, gross_price, fees, net_profit FROM ecommerce_sales ORDER BY id DESC LIMIT 50",
                    conn,
                )
                if not df_es.empty:
                    df_es = df_es.rename(columns={
                        "date": "التاريخ", "platform": "المنصة", "item": "الصنف",
                        "qty": "الكمية", "gross_price": "الإجمالي", "fees": "العمولة", "net_profit": "الصافي",
                    })
                st.dataframe(df_es, use_container_width=True)

        with t_cust:
            c1, c2 = st.columns(2)
            nc_name = c1.text_input("اسم العميل الجديد")
            nc_phone = c2.text_input("رقم الهاتف")
            if st.button("➕ حفظ عميل التجزئة"):
                try:
                    conn.execute("INSERT INTO kc_customers (name,phone) VALUES (?,?)", (nc_name, nc_phone))
                    conn.commit(); st.success("تم!")
                except: st.error("مسجل مسبقاً.")
            df_kc = sql_df("SELECT name, phone FROM kc_customers ORDER BY id DESC", conn)
            if not df_kc.empty:
                df_kc = df_kc.rename(columns={"name": "اسم العميل", "phone": "رقم الهاتف"})
            st.dataframe(df_kc, use_container_width=True)

        with t_pos:
            from kobe_vast.mobile_ui import add_item_button
            from kobe_vast.pos_sales import render_editable_cart

            kc_types = "('مطحون', 'محمص', 'كوبي كاب')"
            kc_items = sql_df(f"SELECT name, type, qty, sell_price FROM inv WHERE type IN {kc_types} AND qty > 0", conn)
            kc_clients = [r[0] for r in conn.execute("SELECT name FROM kc_customers").fetchall()]

            cl, cr = st.columns([1, 1.2])
            with cl:
                st.markdown("### 🟧 كاشير كوبي كاب")
                client = st.selectbox("العميل", ["عميل نقدي (تجزئة)"] + kc_clients, key="kc_client")

                st.markdown('<div class="add-item-box platform-card-kobecup">', unsafe_allow_html=True)
                st.markdown("#### ➕ إضافة صنف للفاتورة")
                if kc_items.empty:
                    st.warning("لا يوجد مخزون تجزئة — انقل بضاعة من تبويب المخزون")
                else:
                    options = [f"{r['name']} | {r['type']} ({r['qty']:,.1f} كجم)" for _, r in kc_items.iterrows()]
                    sel = st.selectbox("اختر الصنف", options, key="kc_sel")
                    idx = options.index(sel)
                    i_row = kc_items.iloc[idx]
                    c1, c2, c3 = st.columns(3)
                    qty = c1.number_input("الكمية", 0.1, value=1.0, key="kc_qty", step=0.1)
                    up = c2.number_input("السعر", 0.0, float(i_row["sell_price"]), key="kc_price")
                    c3.metric("السطر", f"{qty * up:,.2f} ج.م")
                    if add_item_button(f"➕ أضف {i_row['name']}", key="kc_add"):
                        st.session_state.setdefault("kc_cart", []).append({
                            "item": str(i_row["name"]), "type": str(i_row["type"]),
                            "qty": qty, "p": up, "t": round(qty * up, 2),
                            "platform": "kobecup",
                        })
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

                if st.session_state.get("kc_cart"):
                    cart = render_editable_cart(st.session_state["kc_cart"], cart_key="kc")
                    st.session_state["kc_cart"] = cart
                    if not cart:
                        st.session_state["kc_cart"] = []
                        st.rerun()

                    gross = sum(x["t"] for x in cart)
                    c1, c2 = st.columns(2)
                    disc = c1.number_input("الخصم", 0.0, gross, 0.0, key="kc_disc")
                    net = gross - disc
                    paid = c2.number_input("المدفوع", 0.0, float(net), key="kc_paid")
                    pm = st.selectbox("طريقة الدفع", PAY_METHODS, key="kc_pm")
                    bank_ch = st.selectbox("إلى حساب:", banks_list, key="kc_bank") if pm in ["تحويل بنكي", "محفظة"] else "---"

                    if st.button("🟧 إصدار فاتورة كوبي كاب", type="primary", use_container_width=True):
                        d, tm = now_dt()
                        inv_no = f"KC-{datetime.now().strftime('%H%M%S')}"
                        for i, ln in enumerate(cart):
                            ld, lp = (disc, paid) if i == 0 else (0, 0)
                            conn.execute(
                                "INSERT INTO sales (date,time,inv_no,client,item,type,qty,unit_p,total,paid,discount,pay_method,is_return) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)",
                                (d, tm, inv_no, client, ln["item"], ln["type"], ln["qty"], ln["p"], ln["t"] - ld, lp, ld, pm),
                            )
                            conn.execute("UPDATE inv SET qty=qty-? WHERE name=? AND type=?", (ln["qty"], ln["item"], ln["type"]))
                        if paid > 0 and pm != "آجل":
                            insert_treasury(conn, "إيداع", "مبيعات كوبي كاب", f"إيصال {inv_no}", paid, pm, bank_ch)
                        conn.commit()
                        st.session_state.kc_res = {
                            "no": inv_no, "d": d, "c": client, "cart": list(cart),
                            "gross": gross, "disc": disc, "net": net, "paid": paid,
                            "rem": net - paid, "pay": pm,
                        }
                        st.session_state["kc_cart"] = []
                        st.rerun()

            with cr:
                if "kc_res" in st.session_state:
                    show_invoice_capture(
                        st.session_state.kc_res, get_settings(),
                        f"KobeCup_{st.session_state.kc_res['no']}", brand="kobecup",
                    )
                elif st.session_state.get("kc_cart"):
                    st.info("👈 عدّل الأصناف ثم اضغط إصدار الفاتورة")
                else:
                    st.markdown(
                        '<div style="background:linear-gradient(135deg,#fff7ed,#ffedd5);border:2px solid #fdba74;'
                        'border-radius:14px;padding:40px;text-align:center;color:#9a3412;">'
                        '<h2 style="margin:0;">🟧 كوبي كاب</h2>'
                        '<p>أضف أصناف التجزئة من اليسار</p></div>',
                        unsafe_allow_html=True,
                    )

elif page == "integrations":
    if st.session_state.role != "مدير":
        st.warning("صفحة الربط متاحة للمدير فقط")
    else:
        with get_conn() as conn:
            try:
                from kobe_vast.partners_api import render_partners_page
                render_partners_page(conn, sql_df)
            except Exception as e:
                st.error(f"خطأ صفحة الربط: {e}")

elif page == "settings":
    st.markdown("## ⚙️ الإعدادات")
    t1, t2, t3 = st.tabs(["الإعدادات و Gemini", "تعديل الأسعار والشرائح", "العملاء والائتمان"])
    with get_conn() as conn:
        with t1:
            sc = get_settings()
            cn = st.text_input("الشركة", sc["company_name"])
            ph = st.text_input("الهاتف", sc["phone"])
            ad = st.text_input("العنوان", sc["address"], placeholder=DEFAULT_ADDRESS)
            gk = st.text_input("Gemini API Key (مفتاح الذكاء الاصطناعي)", sc.get("gemini_key", ""), type="password")
            if st.button("💾 حفظ الإعدادات الأساسية"):
                conn.execute("UPDATE settings SET company_name=?,phone=?,address=?,gemini_key=? WHERE id=1", (cn, ph, ad, gk))
                conn.commit()
                _load_settings.clear()
                st.success("تم الحفظ!"); st.rerun()
        with t2:
            st.info("حدد أسعار القطاعي، الجملة، والموزعين لكل صنف بدقة.")
            ed_i = st.data_editor(sql_df("SELECT id, name, type, qty, sell_price, wholesale_price, dist_price FROM inv", conn), disabled=["id", "name", "type", "qty"], use_container_width=True)
            if st.button("💾 حفظ أسعار الشرائح"):
                for _, r in ed_i.iterrows(): conn.execute("UPDATE inv SET sell_price=?, wholesale_price=?, dist_price=? WHERE id=?", (r['sell_price'], r['wholesale_price'], r['dist_price'], r['id']))
                conn.commit(); st.success("تم التحديث!"); st.rerun()
        with t3:
            st.info("حدد الحد الأقصى للديون (Credit Limit) لكل عميل وشريحة التسعير الخاصة به.")
            ed_c = st.data_editor(sql_df("SELECT id, name, pricing_tier, credit_limit, opening_balance FROM customers", conn), column_config={"pricing_tier": st.column_config.SelectboxColumn("الشريحة", options=PRICING_TIERS)}, disabled=["id", "name"], use_container_width=True)
            if st.button("💾 حفظ الائتمان والشرائح"):
                for _, r in ed_c.iterrows(): conn.execute("UPDATE customers SET pricing_tier=?, credit_limit=?, opening_balance=? WHERE id=?", (r['pricing_tier'], r['credit_limit'], r['opening_balance'], r['id']))
                conn.commit(); st.success("تم التحديث!"); st.rerun()

elif page == "kds":
    with get_conn() as conn:
        try:
            from kobe_vast.kds_ticket import render_kds_ui
            render_kds_ui(conn, sql_df, st.session_state.get("username", ""))
        except Exception as e:
            st.error(f"خطأ في KDS: {e}")