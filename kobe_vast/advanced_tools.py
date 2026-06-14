# -*- coding: utf-8 -*-
"""Secondary pages — not in main nav."""
import urllib.parse
from datetime import datetime, timedelta

import streamlit as st


def render_tools_page(
    role,
    conn_factory,
    sql_df_fn,
    lux_box_fn,
    banks_list,
    get_settings_fn,
    show_capture_fn,
    build_quote_html_fn,
    build_menu_html_fn,
    wa_phone_fn,
    now_dt_fn,
    pricing_tiers,
):
    """متقدم — للمدير والمخزن فقط."""
    is_admin = role == "مدير"
    is_stock = role in ("مدير", "مخزن")

    if not is_admin and not is_stock:
        st.warning("لا توجد أدوات متاحة لصلاحيتك")
        return

    sections = []
    if is_stock:
        sections += ["خلطات", "تحميص"]
    if is_admin:
        sections += ["عروض", "CRM", "واتساب", "لوحة المالك", "سجلات", "مستخدمين"]

    tabs = st.tabs(sections)
    ti = 0

    if is_stock:
        with tabs[ti]:
            try:
                from kobe_vast.blend_engine import render_blend_creator_ui
                with conn_factory() as conn:
                    render_blend_creator_ui(conn, sql_df_fn)
            except Exception as e:
                st.error(str(e))
        ti += 1
        with tabs[ti]:
            st.markdown("## 🔥 التحميص")
            with conn_factory() as conn:
                greens = sql_df_fn(
                    "SELECT name, qty, buy_price, sell_price FROM inv WHERE type='أخضر'", conn
                )
                if greens.empty:
                    st.warning("لا يوجد بن أخضر")
                else:
                    c1, c2 = st.columns(2)
                    gn = c1.selectbox("البن الأخضر", greens["name"].tolist())
                    iw = c1.number_input("الوزن (كجم)", 0.1, value=10.0)
                    loss = c1.number_input("الهدر %", 0.0, 50.0, 15.0)
                    rn = c2.text_input("اسم المحمص", value=f"{gn} محمص")
                    g = greens[greens["name"] == gn].iloc[0]
                    nq = iw * (1 - loss / 100)
                    rc = (iw * float(g["buy_price"])) / nq if nq > 0 else 0
                    c2.info(f"صافي: **{nq:,.2f}** كجم | تكلفة/كجم: **{rc:,.2f}**")
                    if st.button("تأكيد التحميص", key="tools_roast_confirm") and rn:
                        conn.execute(
                            "UPDATE inv SET qty=qty-? WHERE name=? AND type='أخضر'", (iw, gn)
                        )
                        conn.execute(
                            "INSERT INTO inv (name,type,qty,buy_price,sell_price) VALUES (?,'محمص',?,?,?) "
                            "ON CONFLICT(name,type) DO UPDATE SET qty=qty+?,buy_price=?",
                            (rn, nq, rc, rc * 1.3, nq, rc),
                        )
                        conn.commit()
                        st.success("تم"); st.rerun()
        ti += 1

    if is_admin:
        with tabs[ti]:
            st.markdown("## عروض الأسعار")
            try:
                from kobe_vast.quotation_skins import render_triple_quotation_ui
                with conn_factory() as conn:
                    render_triple_quotation_ui(get_settings_fn(), show_capture_fn, conn=conn)
            except Exception as e:
                st.warning(str(e))
            with conn_factory() as conn:
                with st.expander("كتالوج كلاسيكي + CRM"):
                    inv_df = sql_df_fn(
                        "SELECT name, type, sell_price, wholesale_price, dist_price FROM inv WHERE sell_price>0",
                        conn,
                    )
                    tier = st.selectbox("الشريحة", pricing_tiers, key="classic_tier")
                    qcname = st.text_input("العميل", "عزيزي العميل", key="classic_client")
                    qc_phone = st.text_input("هاتف العميل", key="classic_phone")
                    qc_company = st.text_input("الشركة (اختياري)", key="classic_company")
                    opts = [f"{r['name']} | {r['type']}" for _, r in inv_df.iterrows()]
                    picked = st.multiselect("أصناف", opts, key="classic_pick")
                    if picked and st.button("توليد عرض + CRM", key="tools_quote_gen"):
                        qrows = ""
                        prod_list = []
                        for p in picked:
                            n, t = p.split(" | ")
                            row = inv_df[(inv_df["name"] == n) & (inv_df["type"] == t)].iloc[0]
                            pr = row["sell_price"]
                            if tier == "جملة" and row["wholesale_price"] > 0:
                                pr = row["wholesale_price"]
                            elif tier == "موزعين" and row["dist_price"] > 0:
                                pr = row["dist_price"]
                            qrows += f"<tr><td>{n}</td><td>{pr:,.0f}</td></tr>"
                            prod_list.append(n)
                        exp = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
                        show_capture_fn(
                            build_quote_html_fn(qcname, qrows, exp, now_dt_fn()[0], get_settings_fn()),
                            f"Q_{qcname}",
                        )
                        from kobe_vast.crm_sync import push_b2b_lead
                        ok, msg = push_b2b_lead(
                            conn, qcname, qc_phone, qc_company, tier=tier,
                            products=", ".join(prod_list[:10]), source="عرض سعر كلاسيكي",
                        )
                        if ok:
                            st.success(f"CRM: {msg}")
        ti += 1

        with tabs[ti]:
            st.markdown("## CRM")
            with conn_factory() as conn:
                new_task = st.text_input("مهمة جديدة")
                if st.button("إضافة مهمة", key="tools_crm_add_task") and new_task:
                    conn.execute("INSERT INTO todos (task, created_at) VALUES (?,?)", (new_task, now_dt_fn()[0]))
                    conn.commit(); st.rerun()
                todos = sql_df_fn("SELECT * FROM todos WHERE is_done=0 ORDER BY id DESC LIMIT 20", conn)
                for _, row in todos.iterrows():
                    if st.checkbox(row["task"], key=f"t_{row['id']}"):
                        conn.execute("UPDATE todos SET is_done=1 WHERE id=?", (row["id"],))
                        conn.commit(); st.rerun()
                with st.expander("عميل محتمل"):
                    n_name = st.text_input("الاسم")
                    n_phone = st.text_input("الهاتف")
                    if st.button("حفظ", key="tools_crm_save_lead") and n_name:
                        conn.execute(
                            "INSERT INTO leads (date,name,phone,status,source) VALUES (?,?,?,'جديد','يدوي')",
                            (now_dt_fn()[0], n_name, n_phone),
                        )
                        conn.commit(); st.rerun()
                leads = sql_df_fn(
                    "SELECT name, phone, status, source, requests FROM leads ORDER BY id DESC LIMIT 30",
                    conn,
                )
                if not leads.empty:
                    styled_dataframe(leads.rename(columns={
                        "name": "العميل", "phone": "الهاتف", "status": "الحالة",
                        "source": "المصدر", "requests": "الطلب",
                    }))
        ti += 1

        with tabs[ti]:
            st.markdown("## واتساب")
            with conn_factory() as conn:
                q = (
                    "SELECT name, phone FROM customers WHERE phone != '' "
                    "UNION SELECT name, phone FROM kc_customers WHERE phone != '' "
                    "UNION SELECT name, phone FROM leads WHERE phone != ''"
                )
                tg = sql_df_fn(q, conn).to_dict("records")
            st.caption(f"{len(tg)} رقم")
            msg = st.text_area("الرسالة", "عروض من كوبي جرين ☕", height=100)
            if st.button("تجهيز روابط", key="tools_wa_prepare") and tg:
                enc = urllib.parse.quote(msg)
                for t in tg[:20]:
                    phone = wa_phone_fn(t["phone"])
                    st.markdown(
                        f'[💬 {t["name"]}](https://wa.me/{phone}?text={enc})'
                    )
        ti += 1

        with tabs[ti]:
            with conn_factory() as conn:
                try:
                    from kobe_vast.owner_dashboard import render_owner_dashboard
                    render_owner_dashboard(conn, sql_df_fn, lux_box_fn)
                except Exception as e:
                    st.error(str(e))
        ti += 1

        with tabs[ti]:
            st.markdown("## تعديل السجلات")
            tables = {"مخزون": "inv", "عملاء": "customers", "مبيعات": "sales", "خزينة": "treasury"}
            tbl = st.selectbox("الجدول", list(tables.keys()))
            with conn_factory() as conn:
                df = sql_df_fn(f"SELECT * FROM {tables[tbl]} ORDER BY id DESC LIMIT 200", conn)
                edited = st.data_editor(df, num_rows="dynamic", use_container_width=True, key=f"ed_{tbl}")
                if st.button("حفظ", key="tools_records_save"):
                    st.warning("استخدم الإعدادات لتعديل الأسعار — هنا للحذف السريع فقط")
        ti += 1

        with tabs[ti]:
            with conn_factory() as conn:
                from kobe_vast.user_admin import render_user_admin
                render_user_admin(conn, sql_df_fn, st.session_state.get("username", ""))
