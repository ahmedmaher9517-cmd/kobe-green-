# -*- coding: utf-8 -*-
"""Dynamic Blend Creator & Cost Calculator."""
import json

import streamlit as st

from kobe_vast.guards import (
    GuardError,
    assert_positive,
    assert_recipe_ratios,
    assert_sufficient_stock,
)

CARDAMOM_NAME = "حبهان"
CARDAMOM_TYPE = "توابل"


def _fetch_green_stocks(conn):
    cur = conn.execute(
        "SELECT name, qty, buy_price FROM inv WHERE type=? ORDER BY name",
        ("أخضر",),
    )
    return {r[0]: {"qty": float(r[1] or 0), "wac": float(r[2] or 0)} for r in cur.fetchall()}


def _fetch_cardamom(conn):
    cur = conn.execute(
        "SELECT name, qty, buy_price FROM inv WHERE name LIKE ? OR type=? ORDER BY name LIMIT 1",
        (f"%{CARDAMOM_NAME}%", CARDAMOM_TYPE),
    )
    row = cur.fetchone()
    if row:
        return {row[0]: {"qty": float(row[1] or 0), "wac": float(row[2] or 0)}}
    return {}


def _ensure_cardamom_in_inv(conn):
    existing = _fetch_cardamom(conn)
    if existing:
        return existing
    conn.execute(
        """
        INSERT INTO inv (name, type, qty, buy_price, sell_price)
        VALUES (?, ?, 1.0, 800.0, 1200.0)
        ON CONFLICT(name, type) DO NOTHING
        """,
        (CARDAMOM_NAME, CARDAMOM_TYPE),
    )
    conn.commit()
    return {CARDAMOM_NAME: {"qty": 1.0, "wac": 800.0}}


def calculate_blend_cost(recipe, stocks, cardamom_ratio=0.0, cardamom_stocks=None):
    assert_recipe_ratios(recipe)
    cost = 0.0
    breakdown = []
    for bean, ratio in recipe.items():
        r = float(ratio)
        wac = stocks.get(bean, {}).get("wac", 0)
        part = r * wac
        cost += part
        breakdown.append({"bean": bean, "ratio": r, "wac": wac, "cost_part": part})
    if cardamom_ratio > 0 and cardamom_stocks:
        c_stocks = cardamom_stocks or {}
        c_name = next(iter(c_stocks), CARDAMOM_NAME)
        cwac = c_stocks.get(c_name, {}).get("wac", 0)
        cpart = float(cardamom_ratio) * cwac
        cost += cpart
        breakdown.append({
            "bean": f"🌿 {c_name}", "ratio": float(cardamom_ratio),
            "wac": cwac, "cost_part": cpart,
        })
    return cost, breakdown


def deduct_blend_batch(conn, recipe, target_kg, bean_type="أخضر", cardamom_ratio=0.0):
    assert_positive(target_kg, "كمية الإنتاج")
    assert_recipe_ratios(recipe)
    stocks = _fetch_green_stocks(conn)
    deductions = []
    for bean, ratio in recipe.items():
        needed = float(target_kg) * float(ratio)
        avail = stocks.get(bean, {}).get("qty", 0)
        assert_sufficient_stock(avail, needed, bean)
        conn.execute(
            "UPDATE inv SET qty = qty - ? WHERE name=? AND type=?",
            (needed, bean, bean_type),
        )
        deductions.append({"bean": bean, "qty": needed})
    if cardamom_ratio > 0:
        c_stocks = _fetch_cardamom(conn) or _ensure_cardamom_in_inv(conn)
        c_name = next(iter(c_stocks), CARDAMOM_NAME)
        needed_c = float(target_kg) * float(cardamom_ratio)
        avail_c = c_stocks.get(c_name, {}).get("qty", 0)
        assert_sufficient_stock(avail_c, needed_c, c_name)
        conn.execute(
            "UPDATE inv SET qty = qty - ? WHERE name=? AND type=?",
            (needed_c, c_name, CARDAMOM_TYPE),
        )
        deductions.append({"bean": c_name, "qty": needed_c})
    return deductions


def save_blend(conn, blend_name, recipe, sell_price=0, cardamom_pct=0):
    assert_recipe_ratios(recipe)
    payload = {"beans": recipe, "cardamom_pct": float(cardamom_pct)}
    conn.execute(
        """
        INSERT INTO coffee_blends (blend_name, recipe, target_sell_price)
        VALUES (?, ?::jsonb, ?)
        ON CONFLICT (blend_name) DO UPDATE SET
            recipe = EXCLUDED.recipe, target_sell_price = EXCLUDED.target_sell_price
        """,
        (blend_name, json.dumps(payload, ensure_ascii=False), float(sell_price)),
    )
    conn.commit()


def update_blend_by_id(conn, blend_id, blend_name, recipe, sell_price=0, cardamom_pct=0):
    assert_recipe_ratios(recipe)
    payload = {"beans": recipe, "cardamom_pct": float(cardamom_pct)}
    conn.execute(
        """
        UPDATE coffee_blends
        SET blend_name=?, recipe=?::jsonb, target_sell_price=?
        WHERE id=?::uuid
        """,
        (blend_name, json.dumps(payload, ensure_ascii=False), float(sell_price), blend_id),
    )
    conn.commit()


def delete_blend(conn, blend_id):
    conn.execute("DELETE FROM coffee_blends WHERE id=?::uuid", (blend_id,))
    conn.commit()


def load_saved_blends(conn):
    cur = conn.execute(
        "SELECT id, blend_name, recipe, target_sell_price FROM coffee_blends ORDER BY blend_name"
    )
    rows = []
    for r in cur.fetchall():
        recipe = r[2]
        if isinstance(recipe, str):
            recipe = json.loads(recipe)
        if isinstance(recipe, dict) and "beans" in recipe:
            cardamom_pct = recipe.get("cardamom_pct", 0)
            recipe = recipe["beans"]
        else:
            cardamom_pct = 0
        rows.append({
            "id": str(r[0]), "blend_name": r[1], "recipe": recipe,
            "cardamom_pct": cardamom_pct, "target_sell_price": float(r[3] or 0),
        })
    return rows


def render_blend_creator_ui(conn, sql_df):
    st.markdown("## ☕ منشئ التوليفات وحاسبة التكلفة")
    stocks = _fetch_green_stocks(conn)
    if not stocks:
        st.warning("لا يوجد بن أخضر — أضف أصنافاً أولاً")
        return

    cardamom_stocks = _fetch_cardamom(conn)
    if not cardamom_stocks:
        if st.button("🌿 إضافة حبهان للمخزون تلقائياً", key="blend_add_cardamom"):
            cardamom_stocks = _ensure_cardamom_in_inv(conn)
            st.success("تم إضافة حبهان (1 كجم — تكلفة 800 ج.م/كجم)")
            st.rerun()
    else:
        c_name = next(iter(cardamom_stocks))
        st.caption(f"🌿 **{c_name}** متاح: {cardamom_stocks[c_name]['qty']:,.3f} كجم — WAC: {cardamom_stocks[c_name]['wac']:,.2f}")

    beans = list(stocks.keys())
    st.markdown("### 📊 حساب التكلفة (بدون خصم مخزون)")
    with st.form("blend_eval"):
        blend_name = st.text_input("اسم التوليفة", placeholder="مثال: خلطة كافيه خاصة")
        n = st.number_input("عدد أنواع البن", 2, 6, 2)
        ratios = {}
        cols = st.columns(min(int(n), 3))
        for i in range(int(n)):
            with cols[i % len(cols)]:
                b = st.selectbox(f"بن #{i+1}", beans, key=f"bean_{i}")
                pct = st.number_input("نسبة %", 0.0, 100.0, 100.0 / n, key=f"pct_{i}")
                ratios[b] = pct / 100.0

        st.markdown("---")
        st.markdown("##### 🌿 الحبهان (اختياري)")
        add_cardamom = st.checkbox("إضافة حبهان للتوليفة", value=False)
        cardamom_g = st.number_input(
            "جرام حبهان لكل كيلو توليفة", 0.0, 200.0, 5.0,
            disabled=not add_cardamom,
            help="مثال: 5 جرام = 0.5% من الكيلو",
        )
        cardamom_ratio = (cardamom_g / 1000.0) if add_cardamom else 0.0

        eval_btn = st.form_submit_button("احسب تكلفة الكيلو (WAC)", use_container_width=True)
        if eval_btn:
            try:
                bean_total = sum(ratios.values())
                recipe = {k: v / bean_total for k, v in ratios.items()}
                cost, breakdown = calculate_blend_cost(
                    recipe, stocks, cardamom_ratio, cardamom_stocks or _fetch_cardamom(conn)
                )
                st.success(f"تكلفة الكيلو: **{cost:,.2f} ج.م**")
                if add_cardamom:
                    st.info(f"🌿 حبهان: {cardamom_g} جرام/كجم ({cardamom_ratio*100:.2f}%)")
                for line in breakdown:
                    st.caption(
                        f"{line['bean']}: {line['ratio']*100:.1f}% × {line['wac']:,.2f} = {line['cost_part']:,.2f}"
                    )
                st.session_state["_last_blend_recipe"] = recipe
                st.session_state["_last_blend_cost"] = cost
                st.session_state["_last_cardamom_ratio"] = cardamom_ratio
                st.session_state["_last_cardamom_g"] = cardamom_g
            except GuardError as e:
                st.error(str(e))

    st.markdown("---")
    st.markdown("### 🏭 تنفيذ الإنتاج")
    recipe = st.session_state.get("_last_blend_recipe")
    if recipe:
        prod_kg = st.number_input("كمية الإنتاج (كجم)", 0.1, value=10.0, key="prod_kg")
        out_name = st.text_input("اسم المنتج الناتج", value="خلطة مخصصة")
        out_type = st.selectbox("نوع المنتج", ["أخضر", "مطحون", "محمص"])
        card_ratio = st.session_state.get("_last_cardamom_ratio", 0)
        if card_ratio > 0:
            st.caption(f"🌿 سيُخصم حبهان: {prod_kg * card_ratio * 1000:.1f} جرام")
        if st.button("✅ تنفيذ الخصم وإضافة للمخزن", type="primary", key="blend_run_prod"):
            try:
                cost_kg = st.session_state.get("_last_blend_cost", 0)
                deduct_blend_batch(conn, recipe, prod_kg, cardamom_ratio=card_ratio)
                conn.execute(
                    """
                    INSERT INTO inv (name, type, qty, buy_price, sell_price)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(name, type) DO UPDATE SET qty = inv.qty + ?, buy_price = ?
                    """,
                    (out_name, out_type, prod_kg, cost_kg, cost_kg * 1.35, prod_kg, cost_kg),
                )
                conn.execute(
                    "INSERT INTO audit_log (event_type, ref_id, payload) VALUES (?, ?, ?::jsonb)",
                    ("blend_production", out_name, json.dumps({
                        "recipe": recipe, "kg": prod_kg,
                        "cardamom_g": st.session_state.get("_last_cardamom_g", 0),
                    }, ensure_ascii=False)),
                )
                conn.commit()
                st.success(f"تم إنتاج {prod_kg} كجم — {out_name}")
                st.rerun()
            except GuardError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"خطأ: {e}")

    st.markdown("---")
    st.markdown("### 📚 التوليفات المحفوظة")
    blends = load_saved_blends(conn)
    if blends:
        for b in blends:
            card_ratio = float(b.get("cardamom_pct", 0) or 0) / 1000.0
            cost, _ = calculate_blend_cost(
                b["recipe"], stocks, card_ratio, _fetch_cardamom(conn),
            )
            card_note = f" + حبهان {b.get('cardamom_pct', 0)}g/كجم" if b.get("cardamom_pct") else ""
            st.markdown(f"**{b['blend_name']}** — WAC: {cost:,.2f} ج.م/كجم{card_note}")
            beans_txt = " | ".join(f"{k} {v*100:.0f}%" for k, v in b["recipe"].items())
            st.caption(f"{beans_txt} — سعر بيع: {b['target_sell_price']:,.0f} ج.م")

        st.markdown("---")
        st.markdown("### ✏️ تعديل توليفة")
        blend_map = {b["blend_name"]: b for b in blends}
        sel_name = st.selectbox("اختر توليفة للتعديل", list(blend_map.keys()), key="blend_edit_sel")
        if sel_name:
            cur = blend_map[sel_name]
            with st.form("blend_edit_form"):
                new_name = st.text_input("اسم التوليفة", value=cur["blend_name"])
                sell_p = st.number_input(
                    "سعر البيع المستهدف (ج.م/كجم)",
                    0.0, value=float(cur["target_sell_price"]),
                )
                card_g = st.number_input(
                    "جرام حبهان لكل كيلو",
                    0.0, 200.0,
                    float(cur.get("cardamom_pct", 0) or 0),
                )
                st.markdown("**نسب البن (%):**")
                recipe_pcts = {}
                bean_names = list(cur["recipe"].keys())
                cols = st.columns(min(len(bean_names), 3) or 1)
                for i, bean in enumerate(bean_names):
                    with cols[i % len(cols)]:
                        recipe_pcts[bean] = st.number_input(
                            bean,
                            0.0, 100.0,
                            float(cur["recipe"][bean]) * 100.0,
                            key=f"edit_pct_{cur['id']}_{bean}",
                        )
                n_extra = st.number_input("إضافة نوع بن جديد", 0, 3, 0, key=f"edit_extra_{cur['id']}")
                extra_beans = {}
                if n_extra > 0:
                    available = [x for x in beans if x not in bean_names]
                    if not available:
                        st.warning("لا توجد أنواع بن إضافية")
                    else:
                        ex_cols = st.columns(int(n_extra))
                        for j in range(int(n_extra)):
                            with ex_cols[j]:
                                eb = st.selectbox(
                                    f"بن جديد #{j+1}",
                                    available,
                                    key=f"edit_new_bean_{cur['id']}_{j}",
                                )
                                ep = st.number_input(
                                    "نسبة %",
                                    0.0, 100.0, 0.0,
                                    key=f"edit_new_pct_{cur['id']}_{j}",
                                )
                                extra_beans[eb] = ep

                c_save, c_del = st.columns(2)
                save_edit = c_save.form_submit_button("💾 حفظ التعديلات", use_container_width=True)
                del_edit = c_del.form_submit_button("🗑️ حذف التوليفة", use_container_width=True)

            if save_edit:
                try:
                    all_pcts = {**recipe_pcts, **extra_beans}
                    total = sum(all_pcts.values())
                    if total <= 0:
                        raise GuardError("أدخل نسب البن")
                    recipe = {k: v / total for k, v in all_pcts.items() if v > 0}
                    assert_recipe_ratios(recipe)
                    update_blend_by_id(
                        conn, cur["id"], new_name.strip(), recipe, sell_p, card_g,
                    )
                    st.success(f"تم تحديث {new_name}")
                    st.rerun()
                except GuardError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"خطأ: {e}")

            if del_edit:
                try:
                    delete_blend(conn, cur["id"])
                    st.success("تم حذف التوليفة")
                    st.rerun()
                except Exception as e:
                    st.error(f"خطأ: {e}")

        st.markdown("---")
        st.markdown("### 💾 حفظ التوليفة الحالية")
        recipe = st.session_state.get("_last_blend_recipe")
        if recipe:
            save_name = st.text_input("اسم للحفظ", key="blend_save_name")
            save_price = st.number_input(
                "سعر بيع مستهدف",
                0.0,
                value=float(st.session_state.get("_last_blend_cost", 0)) * 1.35,
                key="blend_save_price",
            )
            if st.button("💾 حفظ في القائمة", key="blend_save_btn") and save_name.strip():
                try:
                    card_g = st.session_state.get("_last_cardamom_g", 0)
                    save_blend(conn, save_name.strip(), recipe, save_price, card_g)
                    st.success(f"تم حفظ {save_name}")
                    st.rerun()
                except GuardError as e:
                    st.error(str(e))
    else:
        st.info("لا توجد توليفات محفوظة بعد — احسب توليفة ثم احفظها")
