# -*- coding: utf-8 -*-
"""Single consolidated KDS ticket interface (Phase 3)."""
import json
import uuid
from datetime import datetime

import streamlit as st

from kobe_vast.kds_common import DIVISION_MAP, classify_line


def _load_sales_invoice(conn, sql_df, inv_no):
    df = sql_df(
        "SELECT item, type, qty, client FROM sales WHERE inv_no=? AND is_return=0",
        conn,
        params=(inv_no,),
    )
    if df.empty:
        return {}, {}, ""
    partitions = {"green": [], "roast": [], "ground": []}
    labels = {}
    client = str(df.iloc[0].get("client", ""))
    for _, r in df.iterrows():
        key, label = classify_line(str(r["type"]))
        partitions[key].append(
            {"item": r["item"], "type": r["type"], "qty": float(r["qty"])}
        )
        labels[key] = label
    return partitions, labels, client


def render_kds_ui(conn, sql_df, username):
    from kobe_vast.kds_service import fetch_pending_kds, load_partitions_from_order

    st.markdown("## 🍳 KDS — تذكرة الطلب الموحدة")

    pending_df = fetch_pending_kds(conn, sql_df)
    pending_opts = []
    if pending_df is not None and not pending_df.empty:
        st.markdown("### 📥 طلبات معلّقة (من الفواتير)")
        for _, row in pending_df.iterrows():
            pending_opts.append(str(row["inv_no"]))
            st.caption(f"⏳ {row['inv_no']} — {row.get('client', '')}")

    sales_df = sql_df(
        """
        SELECT inv_no, client
        FROM sales
        WHERE is_return = 0
        GROUP BY inv_no, client
        ORDER BY MAX(id) DESC
        LIMIT 30
        """,
        conn,
    )
    sales_opts = sales_df["inv_no"].tolist() if not sales_df is not None and not sales_df.empty else []

    all_opts = ["— يدوي —"] + pending_opts + [x for x in sales_opts if x not in pending_opts]
    inv_no = st.selectbox("اختر فاتورة / طلب", all_opts)
    if inv_no == "— يدوي —":
        inv_no = st.text_input("رقم الطلب", value=f"KDS-{datetime.now().strftime('%H%M%S')}")

    partitions = {"green": [], "roast": [], "ground": []}
    labels = {}
    client_name = ""

    if pending_df is not None and not pending_df.empty:
        match = pending_df[pending_df["inv_no"] == inv_no]
        if not match.empty:
            partitions, labels, client_name = load_partitions_from_order(match.iloc[0].to_dict())

    if not any(partitions.values()) and inv_no in sales_opts:
        partitions, labels, client_name = _load_sales_invoice(conn, sql_df, inv_no)

    if not any(partitions.values()):
        st.info("أدخل بنود الطلب يدوياً أو اختر فاتورة / طلب معلّق")
        manual_item = st.text_input("صنف")
        manual_type = st.selectbox("نوع", ["أخضر", "محمص", "مطحون", "كوبي كاب"])
        manual_qty = st.number_input("كمية", 0.1, value=1.0)
        if st.button("إضافة بند") and manual_item:
            key, label = classify_line(manual_type)
            st.session_state.setdefault("_kds_manual", []).append(
                {"item": manual_item, "type": manual_type, "qty": manual_qty, "division": key}
            )
            st.rerun()
        for m in st.session_state.get("_kds_manual", []):
            key = m["division"]
            partitions[key].append(m)
            _, lbl = classify_line(m["type"])
            labels[key] = lbl

    if client_name:
        st.caption(f"العميل: **{client_name}**")

    timer_key = "_kds_timer_start"
    if timer_key not in st.session_state:
        st.session_state[timer_key] = None
    col_t1, col_t2 = st.columns(2)
    if col_t1.button("▶️ بدء التحضير (Unified Timer)"):
        st.session_state[timer_key] = datetime.now()
        conn.execute(
            "UPDATE kds_orders SET status='preparing', opened_at=NOW() WHERE inv_no=? AND status='pending'",
            (inv_no,),
        )
        conn.commit()
        st.rerun()
    elapsed = 0
    if st.session_state[timer_key]:
        elapsed = int((datetime.now() - st.session_state[timer_key]).total_seconds())
        col_t2.metric("⏱️ المدة", f"{elapsed // 60}:{elapsed % 60:02d}")

    checks = {}
    active_parts = []
    for key, css in [
        ("green", "kds-partition-green"),
        ("roast", "kds-partition-roast"),
        ("ground", "kds-partition-ground"),
    ]:
        lbl = labels.get(
            key,
            DIVISION_MAP.get(
                "أخضر" if key == "green" else "محمص" if key == "roast" else "مطحون"
            )[1],
        )
        items = partitions.get(key, [])
        if not items:
            continue
        active_parts.append(key)
        st.markdown(f'<div class="{css}"><b>{lbl}</b></div>', unsafe_allow_html=True)
        for it in items:
            st.markdown(f"- {it['item']} ({it['type']}) × {it['qty']:,.2f}")
        checks[key] = st.checkbox(f"✓ تأكيد قسم {lbl}", key=f"kds_chk_{key}")

    st.markdown("### بيانات التسليم")
    delivery = st.selectbox("طريقة التسليم", ["استلام من الفرع", "توصيل داخلي", "شحن خارجي"])
    driver_phone = st.text_input("هاتف السائق / التتبع")
    tracking = st.text_input("مرجع التتبع")

    all_checked = len(active_parts) > 0 and all(checks.get(k) for k in active_parts)
    delivery_ok = bool(driver_phone.strip()) and bool(delivery)
    can_complete = all_checked and delivery_ok and st.session_state.get(timer_key)

    if not can_complete:
        st.warning("أكمل كل الأقسام + بيانات التسليم + شغّل المؤقت قبل الإغلاق")

    if st.button("✅ إتمام الطلب", disabled=not can_complete):
        order_id = str(uuid.uuid4())
        line_items = []
        for k, arr in partitions.items():
            for it in arr:
                line_items.append({**it, "division": k})
        existing = conn.execute(
            "SELECT id FROM kds_orders WHERE inv_no=? AND status IN ('pending','preparing')",
            (inv_no,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE kds_orders SET status='completed', completed_at=NOW(), duration_seconds=?,
                    delivery_method=?, driver_phone=?, tracking_ref=?, checklist=?::jsonb,
                    line_items=?::jsonb, worker_username=?
                WHERE id=?::uuid
                """,
                (
                    elapsed,
                    delivery,
                    driver_phone,
                    tracking,
                    json.dumps(checks, ensure_ascii=False),
                    json.dumps(line_items, ensure_ascii=False),
                    username,
                    str(existing[0]),
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO kds_orders (id, inv_no, client, status, opened_at, completed_at, duration_seconds,
                    delivery_method, driver_phone, tracking_ref, checklist, line_items, worker_username)
                VALUES (?::uuid, ?, ?, 'completed', ?, NOW(), ?, ?, ?, ?, ?::jsonb, ?::jsonb, ?)
                """,
                (
                    order_id,
                    inv_no,
                    client_name,
                    st.session_state[timer_key].isoformat(),
                    elapsed,
                    delivery,
                    driver_phone,
                    tracking,
                    json.dumps(checks, ensure_ascii=False),
                    json.dumps(line_items, ensure_ascii=False),
                    username,
                ),
            )
        conn.execute(
            """
            INSERT INTO employee_metrics (username, week_start, commission, kds_orders_completed)
            VALUES (?, ?, 50, 1)
            """,
            (username, datetime.now().strftime("%Y-%W")),
        )
        conn.execute(
            "INSERT INTO audit_log (event_type, ref_id, username, payload) VALUES (?, ?, ?, ?::jsonb)",
            (
                "kds_complete",
                inv_no,
                username,
                json.dumps({"seconds": elapsed, "delivery": delivery}, ensure_ascii=False),
            ),
        )
        conn.commit()
        st.session_state[timer_key] = None
        st.session_state.pop("_kds_manual", None)
        st.success(f"تم إغلاق الطلب — {elapsed} ثانية — عمولة 50 ج.م")
        st.rerun()

    st.markdown("---")
    st.markdown("### سجل KDS الأخير")
    try:
        hist = sql_df(
            "SELECT inv_no, status, duration_seconds, delivery_method, completed_at FROM kds_orders ORDER BY created_at DESC LIMIT 10",
            conn,
        )
        if hist is not None and not hist.empty:
            st.dataframe(hist, use_container_width=True)
    except Exception:
        pass
