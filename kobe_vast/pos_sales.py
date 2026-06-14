# -*- coding: utf-8 -*-
"""POS sales: 3 platforms, editable cart, invoice history."""
from datetime import datetime

import pandas as pd
import streamlit as st

from kobe_vast.guards import GuardError
from kobe_vast.mobile_ui import add_item_button, delete_button, styled_dataframe
from kobe_vast.platforms import PLATFORMS, filter_items_by_platform, platform_badge, platform_for_type


def _recalc_cart(cart):
    for ln in cart:
        ln["t"] = round(float(ln.get("qty", 0)) * float(ln.get("p", 0)), 2)
        ln["platform"] = platform_for_type(ln.get("type", "أخضر"))
    return cart


def render_editable_cart(cart, cart_key="cart"):
    """Edit qty/price per line — delete single rows without clearing invoice."""
    if not cart:
        return []
    st.markdown('<div class="cart-panel">', unsafe_allow_html=True)
    st.markdown("#### 🧾 الفاتورة الحالية")
    st.caption("عدّل الكمية أو السعر لكل صنف — احذف صف واحد فقط إن احتجت")

    new_cart = []
    deleted = False
    for idx, ln in enumerate(cart):
        st.markdown('<div class="cart-line">', unsafe_allow_html=True)
        pk = ln.get("platform", platform_for_type(ln.get("type", "أخضر")))
        st.markdown(
            f'<div class="cart-line-header">{platform_badge(pk)}'
            f'<span style="font-weight:900;color:#ece6da;">{ln["item"]}</span></div>',
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns([2, 2, 1])
        qty = c1.number_input(
            "الكمية (كجم)", 0.001, value=float(ln["qty"]),
            key=f"{cart_key}_qty_{idx}", step=0.1,
        )
        price = c2.number_input(
            "السعر", 0.0, value=float(ln["p"]),
            key=f"{cart_key}_price_{idx}", step=1.0,
        )
        line_total = round(qty * price, 2)
        c3.markdown(f"**{line_total:,.2f}**")
        c3.caption("ج.م")
        if delete_button("حذف", key=f"{cart_key}_del_{idx}", css_class="btn-delete-row"):
            deleted = True
            st.markdown("</div>", unsafe_allow_html=True)
            continue
        new_cart.append({
            "item": ln["item"], "type": ln["type"],
            "qty": qty, "p": price, "t": line_total,
            "platform": pk,
        })
        st.markdown("</div>", unsafe_allow_html=True)

    if deleted:
        return _recalc_cart(new_cart)

    gross = sum(x["t"] for x in new_cart)
    st.markdown(
        f'<div class="cart-total-bar">إجمالي الفاتورة: {gross:,.2f} ج.م — {len(new_cart)} صنف</div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
    return _recalc_cart(new_cart)


def render_platform_item_picker(items_df, c_tier, platform_key):
    """Clear add-item UI per platform."""
    p = PLATFORMS[platform_key]
    sub = filter_items_by_platform(items_df, platform_key)
    st.markdown(f'<div class="add-item-box platform-card-{platform_key}">', unsafe_allow_html=True)
    st.markdown(f"#### ➕ إضافة صنف — {p['label']}")
    if sub is None or sub.empty:
        st.info(f"لا توجد أصناف في {p['label_short']} — أضف من المشتريات أولاً")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    options = [f"{r['name']} | {r['type']} ({r['qty']:,.1f} كجم متاح)" for _, r in sub.iterrows()]
    sel = st.selectbox("اختر الصنف", options, key=f"sel_{platform_key}")
    idx = options.index(sel)
    i_row = sub.iloc[idx]
    i_n, i_t = str(i_row["name"]), str(i_row["type"])
    def_p = float(i_row["sell_price"])
    if c_tier == "جملة" and float(i_row.get("wholesale_price", 0)) > 0:
        def_p = float(i_row["wholesale_price"])
    elif c_tier == "موزعين" and float(i_row.get("dist_price", 0)) > 0:
        def_p = float(i_row["dist_price"])

    c1, c2, c3 = st.columns(3)
    qty = c1.number_input("الكمية (كجم)", 0.001, value=1.0, key=f"qty_{platform_key}", step=0.1)
    up = c2.number_input("سعر الكيلو", 0.0, value=def_p, key=f"price_{platform_key}")
    c3.metric("إجمالي السطر", f"{qty * up:,.2f} ج.م")
    st.caption(f"📦 المتوفر: **{float(i_row['qty']):,.2f}** كجم")

    if add_item_button(f"➕ أضف {i_n} للفاتورة", key=f"add_{platform_key}"):
        st.session_state.cart.append({
            "item": i_n, "type": i_t, "qty": qty, "p": up,
            "t": round(qty * up, 2), "platform": platform_key,
        })
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_kc_cart_editor(cart, cart_key="kc"):
    """Kobe Cup retail cart — same per-line editing."""
    return render_editable_cart(cart, cart_key=cart_key)


def render_pos_sale_tab(
    conn, sql_df, items, c_df, banks_list,
    now_dt_fn, client_debt_fn, insert_treasury_fn,
    show_capture_fn, build_invoice_html_fn, get_settings_fn,
    pay_methods, load_inv_clear_fn, load_cust_clear_fn,
):
    cl, cr = st.columns([1, 1.2])
    with cl:
        st.markdown("### 🛒 إصدار فاتورة جديدة")
        client = st.selectbox("العميل", ["عميل نقدي"] + c_df["name"].tolist() + ["+ عميل جديد"], key="pos_client")
        c_tier, c_limit = "قطاعي", 10000.0
        if client == "+ عميل جديد":
            client = st.text_input("اسم العميل الجديد", key="pos_new_client")
        elif client != "عميل نقدي":
            c_info = c_df[c_df["name"] == client].iloc[0]
            c_tier, c_limit = c_info["pricing_tier"], float(c_info["credit_limit"])
            st.info(f"شريحة: **{c_tier}** | ديون: **{client_debt_fn(conn, client):,.2f}**")

        st.markdown("---")
        t_green, t_roast, t_cup = st.tabs([
            PLATFORMS["green"]["label"],
            PLATFORMS["roast"]["label"],
            PLATFORMS["kobecup"]["label"],
        ])
        with t_green:
            render_platform_item_picker(items, c_tier, "green")
        with t_roast:
            render_platform_item_picker(items, c_tier, "roast")
        with t_cup:
            render_platform_item_picker(items, c_tier, "kobecup")

        if st.session_state.cart:
            cart = render_editable_cart(st.session_state.cart, cart_key="pos")
            st.session_state.cart = cart
            if not cart:
                if cart_key == "kc":
                    st.session_state["kc_cart"] = []
                else:
                    st.session_state.cart = []
                st.rerun()

            gross = sum(x["t"] for x in cart)
            disc = st.number_input("خصم", 0.0, gross, 0.0, key="pos_disc")
            net = gross - disc

            pay_mode = st.radio(
                "طريقة الدفع",
                ["واحدة", "متعدد (كاش + بنكين)"],
                horizontal=True,
                key="pos_pay_mode",
            )

            pm, bank_ch, paid = "كاش", "---", float(net)
            split_cash, split_b1, split_b2 = float(net), 0.0, 0.0
            b1_label = banks_list[0] if banks_list else "بنك 1"
            b2_label = banks_list[1] if len(banks_list) > 1 else "بنك 2"

            if pay_mode == "واحدة":
                c_pay1, c_pay2 = st.columns(2)
                paid = c_pay2.number_input("المدفوع", 0.0, value=float(net), key="pos_paid")
                pm = st.selectbox("الدفع", pay_methods, key="pos_pm")
                bank_ch = (
                    st.selectbox("إلى حساب:", banks_list, key="pos_bank")
                    if pm in ["تحويل بنكي", "محفظة"]
                    else "---"
                )
                st.caption(f"**الصافي:** {net:,.2f} ج.م | **المتبقي:** {net - paid:,.2f} ج.م")
            else:
                st.caption(f"**الصافي:** {net:,.2f} ج.م — قسّم المبلغ على كاش وبنكين")
                c1, c2, c3 = st.columns(3)
                split_cash = c1.number_input("كاش", 0.0, value=float(net), key="pos_split_cash")
                split_b1 = c2.number_input(b1_label, 0.0, value=0.0, key="pos_split_b1")
                split_b2 = c3.number_input(b2_label, 0.0, value=0.0, key="pos_split_b2")
                total_paid = split_cash + split_b1 + split_b2
                if abs(total_paid - net) > 0.01:
                    st.warning(f"المجموع ({total_paid:,.2f}) ≠ الصافي ({net:,.2f})")
                else:
                    st.success(f"✅ المجموع يطابق الصافي: {total_paid:,.2f} ج.م")

            c_btn1, c_btn2 = st.columns(2)
            if c_btn1.button("✅ إصدار الفاتورة", type="primary", use_container_width=True, key="pos_issue"):
                d, tm = now_dt_fn()
                inv_no = f"INV-{datetime.now().strftime('%H%M%S')}"
                cf = client or "عميل نقدي"
                if cf != "عميل نقدي":
                    conn.execute("INSERT OR IGNORE INTO customers (name) VALUES (?)", (cf,))
                try:
                    if pay_mode == "متعدد (كاش + بنكين)":
                        from kobe_vast.finance_split import (
                            cart_to_bill_lines,
                            create_bill_with_split,
                            split_pay_label,
                        )

                        lines = cart_to_bill_lines(cart)
                        _, net_paid, sp = create_bill_with_split(
                            conn, inv_no, cf, lines, disc,
                            split_cash, split_b1, split_b2, banks_list,
                        )
                        pay_text = split_pay_label(sp, banks_list)
                        load_inv_clear_fn()
                        load_cust_clear_fn()
                        st.session_state.inv_res = {
                            "no": inv_no, "d": d, "c": cf, "cart": list(cart),
                            "gross": gross, "disc": disc, "net": net_paid,
                            "paid": net_paid, "rem": 0.0, "pay": pay_text,
                        }
                    else:
                        for i, ln in enumerate(cart):
                            ld, lp = (disc, paid) if i == 0 else (0, 0)
                            conn.execute(
                                "INSERT INTO sales (date,time,inv_no,client,item,type,qty,unit_p,total,paid,discount,pay_method,is_return) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)",
                                (d, tm, inv_no, cf, ln["item"], ln["type"], ln["qty"], ln["p"], ln["t"] - ld, lp, ld, pm),
                            )
                            conn.execute(
                                "UPDATE inv SET qty=qty-? WHERE name=? AND type=?",
                                (ln["qty"], ln["item"], ln["type"]),
                            )
                        insert_treasury_fn(conn, "إيداع", "مبيعات", f"فاتورة {inv_no}", paid, pm, bank_ch)
                        try:
                            from kobe_vast.kds_service import build_line_items_from_sales_rows, enqueue_kds_order
                            enqueue_kds_order(conn, inv_no, cf, build_line_items_from_sales_rows(cart), source="pos_sale")
                        except Exception:
                            pass
                        conn.commit()
                        load_inv_clear_fn()
                        load_cust_clear_fn()
                        st.session_state.inv_res = {
                            "no": inv_no, "d": d, "c": cf, "cart": list(cart),
                            "gross": gross, "disc": disc, "net": net, "paid": paid,
                            "rem": net - paid, "pay": pm,
                        }
                    st.session_state.cart = []
                    st.rerun()
                except GuardError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"خطأ إصدار الفاتورة: {e}")
            if c_btn2.button("🗑️ مسح الكل", use_container_width=True, key="pos_clear"):
                st.session_state.cart = []
                st.rerun()

    with cr:
        if "inv_res" in st.session_state:
            show_capture_fn(
                st.session_state.inv_res, get_settings_fn(),
                f"INV_{st.session_state.inv_res['no']}", brand="green",
            )
        elif st.session_state.cart:
            st.info("👈 أضف أصناف وعدّل الكميات — الفاتورة تظهر هنا بعد الإصدار")
        else:
            st.info("ابدأ بإضافة صنف من التبويبات أعلاه")
