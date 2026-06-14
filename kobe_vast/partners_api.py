# -*- coding: utf-8 -*-
"""API key management for external partners / integrations."""
import hashlib
import secrets
from datetime import datetime

import streamlit as st

from kobe_vast.mobile_ui import styled_dataframe


def _hash_key(raw_key):
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _is_active(val):
    return val is True or int(val or 0) == 1


from kobe_vast.db_ensure import ensure_partners_table


def generate_partner_key(conn, partner_name, partner_type="متعاون", notes="", webhook_url=""):
    ensure_partners_table(conn)
    raw = f"kobe_{secrets.token_urlsafe(24)}"
    prefix = raw[:12]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute(
        """
        INSERT INTO api_partners
        (partner_name, partner_type, api_key_hash, api_key_prefix, is_active, created_at, notes, webhook_url)
        VALUES (?,?,?,?,1,?,?,?)
        """,
        (partner_name.strip(), partner_type, _hash_key(raw), prefix, now, notes, webhook_url),
    )
    conn.commit()
    return raw


def revoke_partner(conn, partner_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute(
        "UPDATE api_partners SET is_active=0, revoked_at=? WHERE id=?",
        (now, partner_id),
    )
    conn.commit()


def delete_partner(conn, partner_id):
    conn.execute("DELETE FROM api_partners WHERE id=?", (partner_id,))
    conn.commit()


def verify_api_key(conn, raw_key):
    """Return partner row dict if key valid and active, else None."""
    if not raw_key or not str(raw_key).startswith("kobe_"):
        return None
    ensure_partners_table(conn)
    h = _hash_key(raw_key.strip())
    row = conn.execute(
        "SELECT id, partner_name, partner_type, is_active FROM api_partners WHERE api_key_hash=? AND is_active=1",
        (h,),
    ).fetchone()
    if not row:
        return None
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute("UPDATE api_partners SET last_used_at=? WHERE id=?", (now, row[0]))
    conn.commit()
    return {"id": row[0], "partner_name": row[1], "partner_type": row[2]}


def list_partners(conn, sql_df):
    ensure_partners_table(conn)
    df = sql_df(
        """
        SELECT id, partner_name, partner_type, api_key_prefix, is_active,
               created_at, revoked_at, last_used_at, notes, webhook_url
        FROM api_partners ORDER BY id DESC
        """,
        conn,
    )
    return df


def render_partners_page(conn, sql_df):
    st.markdown("## 🔗 المتعاونون والربط API")
    st.info(
        "أنشئ **API Key** لكل متعاون خارجي. المفتاح يُعرض **مرة واحدة** عند الإنشاء — "
        "احفظه فوراً. يمكنك **فك الربط** لإلغاء المفتاح."
    )

    ensure_partners_table(conn)

    if st.session_state.get("_new_api_key"):
        st.success("✅ تم إنشاء المفتاح — انسخه الآن (لن يظهر مرة أخرى):")
        st.code(st.session_state["_new_api_key"], language=None)
        if st.button("تم النسخ — إخفاء المفتاح", key="hide_api_key"):
            del st.session_state["_new_api_key"]
            st.rerun()

    st.markdown("### ➕ ربط متعاون جديد")
    c1, c2 = st.columns(2)
    p_name = c1.text_input("اسم المتعاون / النظام", key="partner_name_in")
    p_type = c2.selectbox(
        "نوع الربط",
        ["متعاون", "متجر إلكتروني", "تطبيق موبايل", "نظام محاسبة", "أخرى"],
        key="partner_type_in",
    )
    p_webhook = st.text_input("Webhook URL (اختياري)", key="partner_webhook")
    p_notes = st.text_area("ملاحظات", key="partner_notes", height=60)

    if st.button("🔑 توليد API Key", type="primary", key="gen_api_key") and p_name.strip():
        raw = generate_partner_key(conn, p_name, p_type, p_notes, p_webhook)
        st.session_state["_new_api_key"] = raw
        st.rerun()

    st.markdown("---")
    st.markdown("### 📋 قائمة المتعاونين")
    df = list_partners(conn, sql_df)
    if df is None or df.empty:
        st.caption("لا يوجد متعاونون مربوطون بعد")
    else:
        show = df.copy()
        show["الحالة"] = show["is_active"].apply(lambda x: "🟢 مربوط" if _is_active(x) else "🔴 مفكوك")
        show = show.rename(columns={
            "partner_name": "المتعاون",
            "partner_type": "النوع",
            "api_key_prefix": "بادئة المفتاح",
            "created_at": "تاريخ الربط",
            "last_used_at": "آخر استخدام",
            "revoked_at": "تاريخ فك الربط",
            "webhook_url": "Webhook",
            "notes": "ملاحظات",
        })
        styled_dataframe(show[[
            "المتعاون", "النوع", "بادئة المفتاح", "الحالة",
            "تاريخ الربط", "آخر استخدام", "Webhook", "ملاحظات",
        ]])

        st.markdown("#### إدارة الربط")
        opts = {
            f"{r['partner_name']} ({'مربوط' if _is_active(r['is_active']) else 'مفكوك'})": int(r["id"])
            for _, r in df.iterrows()
        }
        sel = st.selectbox("اختر متعاون", list(opts.keys()), key="partner_manage_sel")
        pid = opts[sel]
        row = df[df["id"] == pid].iloc[0]

        c_a, c_b = st.columns(2)
        if _is_active(row["is_active"]) and c_a.button("🔓 فك الربط (إلغاء المفتاح)", key=f"revoke_{pid}", use_container_width=True):
            revoke_partner(conn, pid)
            st.success("تم فك الربط")
            st.rerun()
        if c_b.button("🗑️ حذف نهائي", key=f"del_partner_{pid}", use_container_width=True):
            delete_partner(conn, pid)
            st.success("تم الحذف")
            st.rerun()

    st.markdown("---")
    st.markdown("### 📖 طريقة الاستخدام")
    st.markdown(
        """
        أرسل المفتاح في ترويسة الطلب:

        ```
        X-Kobe-API-Key: kobe_xxxxxxxxxxxxxxxx
        ```

        **نقاط الربط المتاحة:**
        - `GET /api/v1/stock` — المخزون (قريباً)
        - `POST /api/v1/leads` — إرسال عميل محتمل (قريباً)
        - `GET /api/v1/invoices/{inv_no}` — استعلام فاتورة (قريباً)

        عند **فك الربط** يتوقف المفتاح فوراً ولا يقبل أي طلب.
        """
    )
