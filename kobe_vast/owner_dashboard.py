# -*- coding: utf-8 -*-
"""Owner dashboard — valuation & true net profits (Phase 2)."""
import streamlit as st


OWNER_PIN_ENV = "KOBE_OWNER_PIN"


def _owner_authenticated():
    if st.session_state.get("_owner_ok"):
        return True
    pin = st.text_input("رمز المالك (Owner PIN)", type="password", key="owner_pin_in")
    expected = "kobe2026"
    import os
    expected = os.environ.get(OWNER_PIN_ENV, expected)
    if st.button("دخول لوحة المالك", key="owner_login"):
        if pin == expected:
            st.session_state["_owner_ok"] = True
            st.rerun()
        else:
            st.error("رمز غير صحيح")
    return False


def compute_valuation(conn, sql_df):
    inv_row = conn.execute(
        "SELECT COALESCE(SUM(qty * buy_price), 0), COALESCE(SUM(qty * sell_price), 0) FROM inv"
    ).fetchone()
    inv_cost = float(inv_row[0] or 0)
    inv_retail = float(inv_row[1] or 0)
    assets = conn.execute("SELECT COALESCE(SUM(asset_value), 0) FROM machine_assets").fetchone()[0]
    assets = float(assets or 0)
    pipeline = conn.execute(
        "SELECT COALESCE(SUM(net_total), 0) FROM bills WHERE is_return = FALSE"
    ).fetchone()[0]
    pipeline = float(pipeline or 0)
    return {
        "inventory_at_cost": inv_cost,
        "inventory_at_retail": inv_retail,
        "machine_assets": assets,
        "pipeline_bills": pipeline,
        "total_valuation": inv_cost + assets + pipeline * 0.3,
    }


def compute_net_profits(conn, sql_df):
    sales_gross = conn.execute(
        """
        SELECT COALESCE(SUM(net_total), 0) FROM bills WHERE is_return = FALSE
        """
    ).fetchone()[0]
    sales_gross = float(sales_gross or 0)
    returns = conn.execute(
        "SELECT COALESCE(SUM(ABS(net_total)), 0) FROM bills WHERE is_return = TRUE"
    ).fetchone()[0]
    returns = float(returns or 0)
    net_sales = sales_gross - returns
    fees = conn.execute(
        "SELECT COALESCE(SUM(fees), 0) FROM ecommerce_sales"
    ).fetchone()[0]
    fees = float(fees or 0)
    cogs = conn.execute(
        """
        SELECT COALESCE(SUM(bl.qty * i.buy_price), 0)
        FROM bill_lines bl
        JOIN bills b ON b.id = bl.bill_id
        LEFT JOIN inv i ON i.name = bl.item AND i.type = COALESCE(bl.item_type, 'أخضر')
        WHERE b.is_return = FALSE
        """
    ).fetchone()[0]
    cogs = float(cogs or 0)
    if cogs == 0:
        cogs = float(
            conn.execute(
                """
                SELECT COALESCE(SUM(s.qty * i.buy_price), 0)
                FROM sales s
                LEFT JOIN inv i ON s.item = i.name AND s.type = i.type
                WHERE s.is_return = 0 AND s.item != 'سداد دفعة نقدية'
                """
            ).fetchone()[0]
            or 0
        )
    weeks = 4
    payroll = weeks * 2200
    commissions = float(
        conn.execute("SELECT COALESCE(SUM(commission), 0) FROM employee_metrics").fetchone()[0]
        or 0
    )
    expenses = float(
        conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM treasury WHERE movement_type='سحب' AND category != 'مشتريات'"
        ).fetchone()[0]
        or 0
    )
    true_net = net_sales - fees - cogs - payroll - commissions - expenses
    return {
        "gross_sales": sales_gross,
        "returns": returns,
        "net_sales": net_sales,
        "processing_fees": fees,
        "cogs": cogs,
        "payroll": payroll,
        "commissions": commissions,
        "expenses": expenses,
        "true_net_profit": true_net,
    }


def render_owner_dashboard(conn, sql_df, lux_box_fn):
    st.markdown("## 👑 لوحة المالك — التقييم وصافي الربح الحقيقي")
    if not _owner_authenticated():
        st.info("منطقة محمية — للمالك فقط")
        return
    if st.button("خروج من لوحة المالك"):
        st.session_state.pop("_owner_ok", None)
        st.rerun()
    val = compute_valuation(conn, sql_df)
    prof = compute_net_profits(conn, sql_df)
    c1, c2, c3, c4 = st.columns(4)
    lux_box_fn(c1, "قيمة المخزون (تكلفة)", f"{val['inventory_at_cost']:,.0f} ج.م")
    lux_box_fn(c2, "أصول الآلات", f"{val['machine_assets']:,.0f} ج.م")
    lux_box_fn(c3, "تقييم الأعمال الخفي", f"{val['total_valuation']:,.0f} ج.م")
    lux_box_fn(c4, "صافي الربح الحقيقي", f"{prof['true_net_profit']:,.0f} ج.م", "profit")
    st.markdown("### تفاصيل الربحية")
    st.json(prof)
    st.markdown("### إضافة أصل / آلة")
    with st.form("add_asset"):
        an = st.text_input("اسم الأصل")
        av = st.number_input("القيمة", 0.0)
        if st.form_submit_button("حفظ"):
            conn.execute(
                "INSERT INTO machine_assets (asset_name, asset_value) VALUES (?, ?)",
                (an, av),
            )
            conn.commit()
            st.success("تم"); st.rerun()
