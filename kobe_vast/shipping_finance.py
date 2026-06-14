# -*- coding: utf-8 -*-
"""Track COD / settlements with shipping companies — separate per brand."""
import streamlit as st

from kobe_vast.mobile_ui import styled_dataframe

BRANDS = {
    "green": {"label": "🟢 كوبي جرين", "key": "green"},
    "kobecup": {"label": "🟧 كوبي كاب", "key": "kobecup"},
}


from kobe_vast.db_ensure import ensure_shipping_tables


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def company_balance(conn, company_id):
    rows = conn.execute(
        "SELECT cod_amount, shipping_fee, net_due, status FROM shipping_cod WHERE company_id=?",
        (company_id,),
    ).fetchall()
    pending = sum(_f(r[2]) for r in rows if (r[3] or "") == "pending")
    settled = sum(_f(r[0]) - _f(r[1]) for r in rows if (r[3] or "") == "settled")
    return pending, settled


def render_brand_shipping(conn, sql_df, lux_box_fn, brand_key, now_dt_fn, insert_treasury_fn, banks_list):
    b = BRANDS[brand_key]
    st.markdown(f"### {b['label']} — شركات الشحن")

    ensure_shipping_tables(conn)

    companies = sql_df(
        "SELECT id, name, phone, contact_name, notes, is_active FROM shipping_companies WHERE brand=? ORDER BY name",
        conn,
        params=(brand_key,),
    )

    with st.expander("➕ إضافة شركة شحن", expanded=companies is None or companies.empty):
        c1, c2 = st.columns(2)
        n_name = c1.text_input("اسم الشركة", key=f"ship_name_{brand_key}")
        n_phone = c2.text_input("الهاتف", key=f"ship_phone_{brand_key}")
        n_contact = st.text_input("مسؤول التواصل", key=f"ship_contact_{brand_key}")
        n_notes = st.text_input("ملاحظات", key=f"ship_notes_{brand_key}")
        if st.button("حفظ الشركة", key=f"ship_add_{brand_key}") and n_name.strip():
            try:
                conn.execute(
                    "INSERT INTO shipping_companies (name, brand, phone, contact_name, notes) VALUES (?,?,?,?,?)",
                    (n_name.strip(), brand_key, n_phone, n_contact, n_notes),
                )
                conn.commit()
                st.success("تمت الإضافة")
                st.rerun()
            except Exception:
                st.error("الشركة مسجلة مسبقاً لهذا الفرع")

    if companies is None or companies.empty:
        st.info("أضف شركة شحن للبدء")
        return

    st.markdown("#### أرصدة المستحقات")
    if len(companies) > 0:
        cols = st.columns(min(len(companies), 4))
        for i, (_, co) in enumerate(companies.iterrows()):
            pending, settled = company_balance(conn, int(co["id"]))
            with cols[i % len(cols)]:
                lux_box_fn(cols[i % len(cols)], co["name"], f"معلق: {pending:,.0f} ج.م")
                st.caption(f"تم تحصيله: {settled:,.0f} ج.م")

    st.markdown("---")
    st.markdown("#### تسجيل شحنة / COD")
    co_opts = {r["name"]: int(r["id"]) for _, r in companies.iterrows() if int(r.get("is_active", 1))}
    if not co_opts:
        st.warning("لا شركات نشطة")
        return

    c1, c2, c3 = st.columns(3)
    sel_co = c1.selectbox("شركة الشحن", list(co_opts.keys()), key=f"ship_co_{brand_key}")
    inv_no = c2.text_input("رقم الفاتورة / الطلب", key=f"ship_inv_{brand_key}")
    client = c3.text_input("العميل", key=f"ship_client_{brand_key}")

    c4, c5, c6 = st.columns(3)
    cod_amt = c4.number_input("المبلغ المحصل من العميل (COD)", 0.0, key=f"ship_cod_{brand_key}")
    ship_fee = c5.number_input("رسوم الشحن المخصومة", 0.0, key=f"ship_fee_{brand_key}")
    net_due = cod_amt - ship_fee
    c6.metric("صافي المستحق لنا", f"{net_due:,.2f} ج.م")
    notes = st.text_input("ملاحظات", key=f"ship_cod_notes_{brand_key}")

    if st.button("📦 تسجيل شحنة", type="primary", key=f"ship_reg_{brand_key}") and sel_co:
        d, _ = now_dt_fn()
        conn.execute(
            """
            INSERT INTO shipping_cod
            (company_id, date, inv_no, client, cod_amount, shipping_fee, net_due, status, notes)
            VALUES (?,?,?,?,?,?,?,'pending',?)
            """,
            (co_opts[sel_co], d, inv_no, client, cod_amt, ship_fee, net_due, notes),
        )
        conn.commit()
        st.success("تم التسجيل")
        st.rerun()

    st.markdown("---")
    st.markdown("#### تحصيل مستحقات من شركة الشحن")
    c1, c2, c3 = st.columns(3)
    settle_co = c1.selectbox("الشركة", list(co_opts.keys()), key=f"settle_co_{brand_key}")
    settle_amt = c2.number_input("المبلغ المحصّل", 0.01, key=f"settle_amt_{brand_key}")
    settle_pm = c3.selectbox("إيداع في", ["كاش", "تحويل بنكي", "محفظة"], key=f"settle_pm_{brand_key}")
    settle_bank = (
        st.selectbox("الحساب البنكي", banks_list, key=f"settle_bank_{brand_key}")
        if settle_pm in ["تحويل بنكي", "محفظة"]
        else "---"
    )

    pending_rows = sql_df(
        """
        SELECT id, date, inv_no, client, net_due
        FROM shipping_cod
        WHERE company_id=? AND status='pending' ORDER BY id DESC LIMIT 50
        """,
        conn,
        params=(co_opts[settle_co],),
    )
    if pending_rows is not None and not pending_rows.empty:
        st.caption("شحنات معلقة:")
        styled_dataframe(pending_rows.rename(columns={
            "date": "التاريخ", "inv_no": "الفاتورة", "client": "العميل", "net_due": "المستحق",
        }))

    if st.button("✅ تأكيد التحصيل", key=f"settle_btn_{brand_key}") and settle_co:
        d, _ = now_dt_fn()
        cid = co_opts[settle_co]
        remaining = settle_amt
        pend = conn.execute(
            "SELECT id, net_due FROM shipping_cod WHERE company_id=? AND status='pending' ORDER BY id",
            (cid,),
        ).fetchall()
        for pid, nd in pend:
            if remaining <= 0:
                break
            nd = _f(nd)
            if remaining >= nd:
                conn.execute(
                    "UPDATE shipping_cod SET status='settled', settled_date=? WHERE id=?",
                    (d, pid),
                )
                remaining -= nd
            else:
                conn.execute(
                    "UPDATE shipping_cod SET net_due=?, notes=notes || ' | جزئي' WHERE id=?",
                    (nd - remaining, pid),
                )
                remaining = 0
        insert_treasury_fn(
            conn, "إيداع", "تحصيل شحن",
            f"{settle_co} ({b['label']})", settle_amt, settle_pm, settle_bank,
        )
        conn.commit()
        st.success(f"تم تحصيل {settle_amt:,.2f} ج.م من {settle_co}")
        st.rerun()

    st.markdown("---")
    hist = sql_df(
        """
        SELECT c.name AS company, s.date, s.inv_no, s.client, s.cod_amount,
               s.shipping_fee, s.net_due, s.status, s.settled_date
        FROM shipping_cod s
        JOIN shipping_companies c ON c.id = s.company_id
        WHERE c.brand = ?
        ORDER BY s.id DESC LIMIT 100
        """,
        conn,
        params=(brand_key,),
    )
    if hist is not None and not hist.empty:
        styled_dataframe(hist.rename(columns={
            "company": "الشركة", "date": "التاريخ", "inv_no": "الفاتورة",
            "client": "العميل", "cod_amount": "COD", "shipping_fee": "رسوم",
            "net_due": "صافي", "status": "الحالة", "settled_date": "تاريخ التحصيل",
        }))


def render_shipping_finance_page(conn, sql_df, lux_box_fn, now_dt_fn, insert_treasury_fn, banks_list):
    st.markdown("## 🚚 متابعة الفلوس مع شركات الشحن")
    st.caption("حسابات منفصلة — كوبي جرين عن كوبي كاب — أضف أكثر من شركة لكل فرع")

    t_green, t_kc = st.tabs([BRANDS["green"]["label"], BRANDS["kobecup"]["label"]])
    with t_green:
        render_brand_shipping(conn, sql_df, lux_box_fn, "green", now_dt_fn, insert_treasury_fn, banks_list)
    with t_kc:
        render_brand_shipping(conn, sql_df, lux_box_fn, "kobecup", now_dt_fn, insert_treasury_fn, banks_list)
