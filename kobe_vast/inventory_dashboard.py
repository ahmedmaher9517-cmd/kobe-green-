# -*- coding: utf-8 -*-
"""Inventory dashboard: per-platform dashboards + styled tables."""
from datetime import datetime, timedelta

import streamlit as st

from kobe_vast.mobile_ui import delete_button, styled_dataframe
from kobe_vast.platforms import PLATFORMS, filter_items_by_platform, platform_badge


def _f(v):
    """Normalize Decimal/numeric DB values to float."""
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _platform_stats(df):
    if df is None or df.empty:
        return {"qty": 0, "cost_val": 0, "sell_val": 0, "margin_pct": 0, "skus": 0, "low": 0}
    qty = df["qty"].apply(_f)
    buy = df["buy_price"].apply(_f)
    sell = df["sell_price"].apply(_f)
    cost_val = (qty * buy).sum()
    sell_val = (qty * sell).sum()
    margin = ((sell_val - cost_val) / sell_val * 100) if sell_val > 0 else 0
    low = len(df[qty <= 10])
    return {
        "qty": float(qty.sum()),
        "cost_val": float(cost_val),
        "sell_val": float(sell_val),
        "margin_pct": float(margin),
        "skus": len(df),
        "low": low,
    }


def _platform_sales(conn, sql_df, platform_types, since):
    if not platform_types:
        return None
    placeholders = ",".join(["?"] * len(platform_types))
    return sql_df(
        f"""
        SELECT s.item, s.type, SUM(s.qty) AS qty_sold, SUM(s.total) AS revenue
        FROM sales s
        WHERE s.is_return = 0 AND s.item != 'سداد دفعة نقدية'
          AND s.type IN ({placeholders}) AND s.date >= ?
        GROUP BY s.item, s.type ORDER BY SUM(s.total) DESC LIMIT 5
        """,
        conn,
        params=tuple(platform_types) + (since,),
    )


def _render_platform_tab(conn, sql_df, lux_box_fn, inv, pk, p, since):
    sub = filter_items_by_platform(inv, pk)
    stats = _platform_stats(sub)

    st.markdown(
        f'<div class="platform-card-{pk}" style="margin-bottom:16px;">'
        f'<h3 style="margin:0;color:{p["color"]};">{p["label"]} — لوحة الأصناف</h3></div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4, c5 = st.columns(5)
    lux_box_fn(c1, "الكمية (كجم)", f"{stats['qty']:,.1f}")
    lux_box_fn(c2, "تكلفة المخزون", f"{stats['cost_val']:,.0f}")
    lux_box_fn(c3, "قيمة البيع", f"{stats['sell_val']:,.0f}")
    lux_box_fn(c4, "هامش %", f"{stats['margin_pct']:.1f}%")
    lux_box_fn(c5, "نواقص", str(stats["low"]))

    if sub is None or sub.empty:
        st.info(f"لا أصناف في {p['label_short']}")
        return

    sub = sub.copy()
    sub["qty"] = sub["qty"].apply(_f)
    sub["buy_price"] = sub["buy_price"].apply(_f)
    sub["sell_price"] = sub["sell_price"].apply(_f)
    sub["قيمة_تكلفة"] = (sub["qty"] * sub["buy_price"]).round(2)
    sub["قيمة_بيع"] = (sub["qty"] * sub["sell_price"]).round(2)
    sell_safe = sub["sell_price"].replace(0, 1.0)
    sub["هامش_%"] = ((sub["sell_price"] - sub["buy_price"]) / sell_safe * 100).round(1)
    sub["حالة"] = sub["qty"].apply(
        lambda q: "🔴 ناقص" if q <= 5 else ("🟡 منخفض" if q <= 10 else "🟢 متوفر")
    )
    show = sub.rename(columns={
        "name": "الصنف", "type": "النوع", "qty": "الكمية",
        "buy_price": "تكلفة/كجم", "sell_price": "بيع/كجم",
        "wholesale_price": "جملة", "dist_price": "موزعين",
    })
    styled_dataframe(
        show[["الصنف", "النوع", "الكمية", "تكلفة/كجم", "بيع/كجم", "قيمة_تكلفة", "قيمة_بيع", "هامش_%", "حالة"]]
    )

    sales_plat = _platform_sales(conn, sql_df, p["types"], since)
    if sales_plat is not None and not sales_plat.empty:
        st.markdown(f"##### 📈 أفضل مبيعات {p['label_short']} (90 يوم)")
        sp = sales_plat.rename(columns={"item": "الصنف", "type": "النوع", "qty_sold": "المباع", "revenue": "الإيراد"})
        styled_dataframe(sp)


def render_platform_dashboard(conn, sql_df, lux_box_fn):
    st.markdown("## 📦 لوحة المخزون")
    inv = sql_df(
        "SELECT name, type, qty, buy_price, sell_price, wholesale_price, dist_price FROM inv ORDER BY type, name",
        conn,
    )
    if inv.empty:
        st.warning("المخزون فارغ — أضف مشتريات أولاً")
        return

    since = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    tabs = st.tabs([p["label"] for p in PLATFORMS.values()])
    for tab, (pk, p) in zip(tabs, PLATFORMS.items()):
        with tab:
            _render_platform_tab(conn, sql_df, lux_box_fn, inv, pk, p, since)

    st.markdown("---")
    st.markdown("### 🏆 الأفضل أداءً (كل المنصات — 90 يوم)")
    top = sql_df(
        """
        SELECT s.item, s.type,
               SUM(s.qty) AS qty_sold, SUM(s.total) AS total_sales,
               SUM(s.qty * COALESCE(i.buy_price, 0)) AS cogs,
               SUM(s.total) - SUM(s.qty * COALESCE(i.buy_price, 0)) AS profit
        FROM sales s
        LEFT JOIN inv i ON s.item = i.name AND s.type = i.type
        WHERE s.is_return = 0 AND s.item != 'سداد دفعة نقدية' AND s.date >= ?
        GROUP BY s.item, s.type HAVING SUM(s.qty) > 0
        ORDER BY SUM(s.total) DESC LIMIT 15
        """,
        conn,
        params=(since,),
    )
    if top is None or top.empty:
        top = sql_df(
            """
            SELECT s.item, s.type, SUM(s.qty) AS qty_sold, SUM(s.total) AS total_sales,
                   SUM(s.qty * COALESCE(i.buy_price, 0)) AS cogs,
                   SUM(s.total) - SUM(s.qty * COALESCE(i.buy_price, 0)) AS profit
            FROM sales s LEFT JOIN inv i ON s.item = i.name AND s.type = i.type
            WHERE s.is_return = 0 AND s.item != 'سداد دفعة نقدية'
            GROUP BY s.item, s.type HAVING SUM(s.qty) > 0
            ORDER BY SUM(s.total) DESC LIMIT 15
            """,
            conn,
        )
    if top is not None and not top.empty:
        top = top.rename(columns={
            "item": "الصنف", "type": "النوع", "qty_sold": "الكمية_المباعة",
            "total_sales": "إجمالي_المبيعات", "cogs": "تكلفة_البضاعة", "profit": "الربح",
        })
        total_sales = _f(top["إجمالي_المبيعات"].sum()) or 1.0
        top = top.copy()
        top["نسبة_%"] = (top["إجمالي_المبيعات"].apply(_f) / total_sales * 100).round(1)
        t1, t2, t3 = st.tabs(["💰 مبيعات", "📈 ربح", "📊 كمية"])
        with t1:
            styled_dataframe(top.sort_values("إجمالي_المبيعات", ascending=False).head(8))
        with t2:
            styled_dataframe(top.sort_values("الربح", ascending=False).head(8))
        with t3:
            styled_dataframe(top.sort_values("الكمية_المباعة", ascending=False).head(8))
    else:
        st.info("لا بيانات مبيعات كافية بعد")


def render_inventory_page(conn, sql_df, lux_box_fn):
    render_platform_dashboard(conn, sql_df, lux_box_fn)
    st.markdown("---")
    t_sales, t_purch = st.tabs(["📤 حركة المبيعات", "📥 حركة المشتريات"])
    with t_sales:
        df_s = sql_df(
            "SELECT date, time, inv_no, client, item, type, qty, total FROM sales WHERE is_return=0 AND item!='سداد دفعة نقدية' ORDER BY id DESC LIMIT 100",
            conn,
        )
        if df_s is not None and not df_s.empty:
            show = df_s.rename(columns={
                "date": "التاريخ", "time": "الوقت", "inv_no": "الفاتورة",
                "client": "العميل", "item": "الصنف", "type": "النوع",
                "qty": "الكمية", "total": "الإجمالي",
            })
            styled_dataframe(show)
            for i, row in df_s.iterrows():
                if delete_button(f"حذف #{i+1}", key=f"del_sale_{i}"):
                    conn.execute(
                        "DELETE FROM sales WHERE inv_no=? AND item=? AND date=?",
                        (row["inv_no"], row["item"], row["date"]),
                    )
                    conn.commit()
                    st.rerun()
    with t_purch:
        df_p = sql_df(
            "SELECT date, time, supplier, item, type, qty, total FROM purchases WHERE item!='سداد دفعة نقدية' ORDER BY id DESC LIMIT 100",
            conn,
        )
        if df_p is not None and not df_p.empty:
            show = df_p.rename(columns={
                "date": "التاريخ", "time": "الوقت", "supplier": "المورد",
                "item": "الصنف", "type": "النوع", "qty": "الكمية", "total": "الإجمالي",
            })
            styled_dataframe(show)
            for i, row in df_p.iterrows():
                if delete_button(f"حذف #{i+1}", key=f"del_purch_{i}"):
                    conn.execute(
                        "DELETE FROM purchases WHERE supplier=? AND item=? AND date=?",
                        (row["supplier"], row["item"], row["date"]),
                    )
                    conn.commit()
                    st.rerun()
