# -*- coding: utf-8 -*-
"""Invoice archive — all saved forever; browse 1000/page; recall any by number."""
import streamlit as st

from kobe_vast.mobile_ui import styled_dataframe

BATCH_SIZE = 1000
_SALES_FILTER = "item != 'سداد دفعة نقدية'"

PLAT_MAP = {
    "الكل": None,
    "🟢 أخضر": ["أخضر"],
    "🟤 محمص": ["محمص"],
    "🟧 كوبي كاب": ["كوبي كاب", "مطحون"],
}


def _invoice_payload(inv_row, lines_df):
    cart = [
        {"item": r["item"], "type": r["type"], "qty": float(r["qty"]),
         "p": float(r["unit_p"]), "t": float(r["total"])}
        for _, r in lines_df.iterrows()
    ]
    gross = sum(x["t"] for x in cart)
    disc = float(lines_df["discount"].max() or 0) if "discount" in lines_df.columns else 0.0
    paid = float(inv_row.get("paid") or 0)
    net = gross - disc
    return {
        "no": inv_row["inv_no"], "d": inv_row["date"], "c": inv_row["client"],
        "cart": cart, "gross": gross, "disc": disc, "net": net,
        "paid": paid, "rem": net - paid, "pay": inv_row.get("pay") or inv_row.get("pay_method") or "—",
    }


def _count_invoices(conn, sql_df):
    r = sql_df(f"SELECT COUNT(DISTINCT inv_no) AS c FROM sales WHERE {_SALES_FILTER}", conn)
    return int(r.iloc[0]["c"] or 0)


def _lines_for(conn, sql_df, inv_no):
    return sql_df(
        f"""
        SELECT inv_no, date, client, item, type, qty, unit_p, total, paid, discount,
               pay_method, is_return
        FROM sales WHERE {_SALES_FILTER} AND inv_no = ? ORDER BY id
        """,
        conn, params=(inv_no,),
    )


def _search_all(conn, sql_df, inv_q="", client_q="", platform=None):
    parts = [_SALES_FILTER]
    params = []
    if inv_q:
        parts.append("inv_no LIKE ?")
        params.append(f"%{inv_q}%")
    if client_q:
        parts.append("LOWER(client) LIKE LOWER(?)")
        params.append(f"%{client_q}%")
    if platform:
        ph = ",".join(["?"] * len(platform))
        parts.append(f"type IN ({ph})")
        params.extend(platform)
    df = sql_df(
        f"""
        SELECT inv_no, date, client, item, type, qty, unit_p, total, paid, discount,
               pay_method, is_return
        FROM sales WHERE {" AND ".join(parts)} ORDER BY id DESC
        """,
        conn, params=tuple(params) if params else None,
    )
    if df.empty:
        return df
    return (
        df.groupby(["inv_no", "date", "client", "is_return"])
        .agg(items=("item", "count"), total=("total", "sum"),
             paid=("paid", "max"), pay=("pay_method", "first"))
        .reset_index().sort_values(["date", "inv_no"], ascending=False)
    )


def _batch_list(conn, sql_df, page, platform=None):
    offset = page * BATCH_SIZE
    plat = ""
    params = []
    if platform:
        ph = ",".join(["?"] * len(platform))
        plat = f" AND type IN ({ph})"
        params.extend(platform)
    params.extend([BATCH_SIZE, offset])
    return sql_df(
        f"""
        SELECT inv_no, MAX(date) AS date, MAX(client) AS client,
               MAX(is_return) AS is_return, SUM(total) AS total,
               MAX(paid) AS paid, MAX(pay_method) AS pay, COUNT(*) AS items
        FROM sales WHERE {_SALES_FILTER}{plat}
        GROUP BY inv_no ORDER BY MAX(id) DESC LIMIT ? OFFSET ?
        """,
        conn, params=tuple(params),
    )


def _reprint_block(payload, inv_no, is_kc, show_capture_fn, get_settings):
    st.success("اضغط **PDF** أو **صورة JPG/PNG** — نفس شكل المعاينة")
    pre = "KobeCup" if is_kc else "INV"
    brand = "kobecup" if is_kc else "green"
    show_capture_fn(payload, get_settings(), f"{pre}_{inv_no}", brand=brand)


def _pick_and_reprint(conn, sql_df, inv_summary, show_capture_fn, get_settings, key_prefix):
    if inv_summary is None or inv_summary.empty:
        return
    opts = [
        f"{r['inv_no']} | {r['client']} | {r['date']} | {float(r['total']):,.0f} ج.م"
        for _, r in inv_summary.iterrows()
    ]
    sel = st.selectbox("اختر فاتورة", opts, key=f"{key_prefix}_pick")
    sel_no = sel.split(" | ")[0]
    lines = _lines_for(conn, sql_df, sel_no)
    if lines.empty:
        return
    row = inv_summary[inv_summary["inv_no"] == sel_no].iloc[0]
    styled_dataframe(lines[["item", "type", "qty", "unit_p", "total"]].rename(columns={
        "item": "الصنف", "type": "النوع", "qty": "الكمية", "unit_p": "السعر", "total": "الإجمالي",
    }))
    is_kc = str(sel_no).startswith("KC-")
    payload = _invoice_payload(row.to_dict(), lines)
    if st.button("📥 استدعاء PDF / JPG", type="primary", key=f"{key_prefix}_btn", use_container_width=True):
        st.session_state[f"{key_prefix}_reprint"] = sel_no
    if st.session_state.get(f"{key_prefix}_reprint") == sel_no:
        _reprint_block(payload, sel_no, is_kc, show_capture_fn, get_settings)


def render_invoice_history(conn, sql_df, show_capture_fn, build_invoice_html_fn, build_kobecup_html_fn, get_settings_fn, key_prefix="inv"):
    st.markdown("## 📋 سجل الفواتير")
    total = _count_invoices(conn, sql_df)
    st.info(
        f"**{total:,}** فاتورة محفوظة للأبد في قاعدة البيانات — "
        f"القائمة تعرض **{BATCH_SIZE}** فاتورة في كل دفعة — "
        f"للاستدعاء اكتب **رقم الفاتورة** بالكامل"
    )

    c1, c2, c3 = st.columns(3)
    inv_q = c1.text_input("🔍 رقم الفاتورة", placeholder="INV-120530 أو KC-120530", key=f"{key_prefix}_inv_q")
    client_q = c2.text_input("بحث بالعميل", key=f"{key_prefix}_client_q")
    plat_key = c3.selectbox("المنصة", list(PLAT_MAP.keys()), key=f"{key_prefix}_plat")
    platform = PLAT_MAP[plat_key]

    exact_lines = None
    if inv_q.strip():
        exact_lines = _lines_for(conn, sql_df, inv_q.strip())

    # --- استدعاء مباشر (أي فاتورة في الأرشيف كله) ---
    if exact_lines is not None and not exact_lines.empty:
        exact = inv_q.strip()
        st.markdown("### ✅ فاتورة موجودة")
        row = exact_lines.iloc[0]
        styled_dataframe(exact_lines[["item", "type", "qty", "unit_p", "total"]].rename(columns={
            "item": "الصنف", "type": "النوع", "qty": "الكمية", "unit_p": "السعر", "total": "الإجمالي",
        }))
        payload = _invoice_payload(row.to_dict(), exact_lines)
        is_kc = exact.startswith("KC-")
        reprint_key = f"{key_prefix}_reprint"
        if st.button("📥 استدعاء PDF / JPG الآن", type="primary", key=f"{key_prefix}_exact_btn", use_container_width=True):
            st.session_state[reprint_key] = exact
        if st.session_state.get(reprint_key) == exact:
            _reprint_block(payload, exact, is_kc, show_capture_fn, get_settings_fn)
        st.markdown("---")

    # --- بحث أو تصفح دفعات ---
    if client_q.strip() or (inv_q.strip() and (exact_lines is None or exact_lines.empty)):
        st.markdown("### نتائج البحث")
        found = _search_all(conn, sql_df, inv_q=inv_q.strip(), client_q=client_q.strip(), platform=platform)
        if found.empty:
            st.warning("لا توجد نتائج")
        else:
            st.caption(f"**{len(found)}** فاتورة — من كل الأرشيف")
            styled_dataframe(found.rename(columns={
                "inv_no": "رقم الفاتورة", "date": "التاريخ", "client": "العميل",
                "items": "أصناف", "total": "الإجمالي", "paid": "المدفوع",
                "pay": "الدفع", "is_return": "مرتجع",
            }).head(200))
            _pick_and_reprint(conn, sql_df, found, show_capture_fn, get_settings_fn, f"{key_prefix}_search")
    elif not inv_q.strip():
        max_pg = max(0, (total - 1) // BATCH_SIZE)
        page = st.number_input(
            f"رقم الدفعة (0 = الأحدث، كل دفعة {BATCH_SIZE} فاتورة)",
            0, max_pg, 0, key=f"{key_prefix}_page",
        )
        batch = _batch_list(conn, sql_df, int(page), platform)
        from_n = int(page) * BATCH_SIZE + 1
        to_n = min((int(page) + 1) * BATCH_SIZE, total)
        st.markdown(f"### دفعة {int(page) + 1} — فواتير {from_n} إلى {to_n} من {total:,}")
        if batch.empty:
            st.caption("لا توجد فواتير في هذه الدفعة")
        else:
            styled_dataframe(batch.rename(columns={
                "inv_no": "رقم الفاتورة", "date": "التاريخ", "client": "العميل",
                "items": "أصناف", "total": "الإجمالي", "paid": "المدفوع",
                "pay": "الدفع", "is_return": "مرتجع",
            }))
            _pick_and_reprint(conn, sql_df, batch, show_capture_fn, get_settings_fn, f"{key_prefix}_batch")
