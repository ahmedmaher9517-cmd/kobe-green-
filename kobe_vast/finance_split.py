# -*- coding: utf-8 -*-
"""Split-wallet checkout matrix & returns processing (Phase 2)."""
import json
import uuid
from datetime import datetime

import streamlit as st

from kobe_vast.guards import GuardError, assert_non_negative, assert_split_payment


def _now():
    n = datetime.now()
    return n.strftime("%Y-%m-%d"), n.strftime("%I:%M %p")


def create_bill_with_split(conn, inv_no, client, lines, discount, cash, bank_1, bank_2, banks_list):
    gross = sum(float(ln["line_total"]) for ln in lines)
    net = gross - float(discount)
    split = assert_split_payment(cash, bank_1, bank_2, net)
    bill_id = str(uuid.uuid4())
    d, t = _now()
    conn.execute(
        """
        INSERT INTO bills (id, inv_no, client, bill_date, bill_time, gross_total, discount, net_total, payment_split, is_return)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb, FALSE)
        """,
        (
            bill_id,
            inv_no,
            client,
            d,
            t,
            gross,
            discount,
            net,
            json.dumps(split, ensure_ascii=False),
        ),
    )
    for ln in lines:
        conn.execute(
            """
            INSERT INTO bill_lines (bill_id, item, item_type, qty, unit_price, line_total, division)
            VALUES (?::uuid, ?, ?, ?, ?, ?, ?)
            """,
            (
                bill_id,
                ln["item"],
                ln.get("type", ""),
                ln["qty"],
                ln["unit_price"],
                ln["line_total"],
                ln.get("division", "green"),
            ),
        )
        conn.execute(
            "UPDATE inv SET qty = qty - ? WHERE name=? AND type=?",
            (ln["qty"], ln["item"], ln.get("type", "أخضر")),
        )
    if split["cash"] > 0:
        conn.execute(
            "INSERT INTO treasury (date,time,movement_type,category,description,amount,pay_method,method_details) VALUES (?,?,?,?,?,?,?,?)",
            (d, t, "إيداع", "مبيعات", f"فاتورة {inv_no}", split["cash"], "كاش", "---"),
        )
    if split["bank_1"] > 0:
        b1 = banks_list[0] if banks_list else "بنك 1"
        conn.execute(
            "INSERT INTO treasury (date,time,movement_type,category,description,amount,pay_method,method_details) VALUES (?,?,?,?,?,?,?,?)",
            (d, t, "إيداع", "مبيعات", f"فاتورة {inv_no}", split["bank_1"], "تحويل بنكي", b1),
        )
    if split["bank_2"] > 0:
        b2 = banks_list[1] if len(banks_list) > 1 else "بنك 2"
        conn.execute(
            "INSERT INTO treasury (date,time,movement_type,category,description,amount,pay_method,method_details) VALUES (?,?,?,?,?,?,?,?)",
            (d, t, "إيداع", "مبيعات", f"فاتورة {inv_no}", split["bank_2"], "تحويل بنكي", b2),
        )
    for ln in lines:
        conn.execute(
            "INSERT INTO sales (date,time,inv_no,client,item,type,qty,unit_p,total,paid,discount,pay_method,is_return) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)",
            (
                d,
                t,
                inv_no,
                client,
                ln["item"],
                ln.get("type", ""),
                ln["qty"],
                ln["unit_price"],
                ln["line_total"],
                net,
                discount,
                "تقسيم",
            ),
        )
    from kobe_vast.kds_service import build_line_items_from_sales_rows, enqueue_kds_order

    kds_lines = build_line_items_from_sales_rows(lines)
    enqueue_kds_order(conn, inv_no, client, kds_lines, source="split_payment")
    conn.commit()
    return bill_id, net, split


def process_return(conn, original_inv_no, username, banks_list):
    cur = conn.execute(
        "SELECT id, client, net_total, payment_split, is_return FROM bills WHERE inv_no=?",
        (original_inv_no,),
    )
    row = cur.fetchone()
    if not row:
        raise GuardError("الفاتورة غير موجودة في سجل bills")
    if row[4]:
        raise GuardError("هذه الفاتورة مرتجع مسبقاً")
    bill_id, client, net_total, payment_split, _ = row
    net = float(net_total or 0)
    split = payment_split
    if isinstance(split, str):
        split = json.loads(split)
    d, t = _now()
    ret_no = f"RET-{original_inv_no}"
    ret_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO bills (id, inv_no, client, bill_date, bill_time, gross_total, net_total, payment_split, is_return, original_bill_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?::jsonb, TRUE, ?::uuid)
        """,
        (
            ret_id,
            ret_no,
            client,
            d,
            t,
            -net,
            -net,
            json.dumps({k: -float(v) for k, v in split.items()}, ensure_ascii=False),
            bill_id,
        ),
    )
    conn.execute("UPDATE bills SET is_return = TRUE WHERE id = ?::uuid", (bill_id,))
    lines = conn.execute(
        "SELECT item, item_type, qty, unit_price, line_total FROM bill_lines WHERE bill_id = ?::uuid",
        (bill_id,),
    ).fetchall()
    for ln in lines:
        item, itype, qty, up, lt = ln
        conn.execute(
            "UPDATE inv SET qty = qty + ? WHERE name=? AND type=?",
            (float(qty), item, itype or "أخضر"),
        )
        conn.execute(
            "INSERT INTO sales (date,time,inv_no,client,item,type,qty,unit_p,total,paid,discount,pay_method,is_return) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)",
            (d, t, ret_no, client, item, itype, qty, up, -float(lt), 0, 0, "مرتجع"),
        )
    cash = abs(float(split.get("cash", 0)))
    if cash > 0:
        conn.execute(
            "INSERT INTO treasury (date,time,movement_type,category,description,amount,pay_method) VALUES (?,?,?,?,?,?,?)",
            (d, t, "سحب", "مرتجعات", f"مرتجع {original_inv_no}", cash, "كاش"),
        )
    conn.execute(
        "INSERT INTO audit_log (event_type, ref_id, username, payload) VALUES (?, ?, ?, ?::jsonb)",
        ("return", ret_no, username, json.dumps({"original": original_inv_no}, ensure_ascii=False)),
    )
    conn.commit()
    return ret_no


def cart_to_bill_lines(cart):
    """Convert POS cart rows to split-payment bill lines."""
    from kobe_vast.platforms import platform_for_type

    lines = []
    for ln in cart:
        pk = platform_for_type(ln.get("type", "أخضر"))
        division = "green" if pk == "green" else ("roast" if pk == "roast" else "ground")
        lines.append({
            "item": ln["item"],
            "type": ln["type"],
            "qty": float(ln["qty"]),
            "unit_price": float(ln["p"]),
            "line_total": float(ln["t"]),
            "division": division,
        })
    return lines


def split_pay_label(split, banks_list):
    parts = []
    if split.get("cash", 0) > 0:
        parts.append(f"كاش {split['cash']:,.0f}")
    b1 = banks_list[0] if banks_list else "بنك 1"
    b2 = banks_list[1] if len(banks_list) > 1 else "بنك 2"
    if split.get("bank_1", 0) > 0:
        parts.append(f"{b1} {split['bank_1']:,.0f}")
    if split.get("bank_2", 0) > 0:
        parts.append(f"{b2} {split['bank_2']:,.0f}")
    return " + ".join(parts) or "تقسيم"


def render_split_returns_ui(conn, banks_list):
    """مرتجع فواتير الدفع المقسّم (من جدول bills)."""
    st.markdown("#### 🔙 مرتجع فاتورة دفع مقسّم")
    st.caption("للفواتير اللي اتسجلت بتقسيم كاش + بنكين")
    ret_inv = st.text_input("رقم الفاتورة الأصلية", key="split_ret_inv")
    if st.button("تسجيل مرتجع كامل", key="split_ret_btn") and ret_inv:
        try:
            username = st.session_state.get("username", "system")
            rno = process_return(conn, ret_inv.strip(), username, banks_list)
            st.success(f"تم المرتجع: {rno}")
            st.rerun()
        except GuardError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"خطأ: {e}")


def render_split_checkout_ui(conn, banks_list):
    st.markdown("## 💳 دفع متعدد المحافظ (Split Payment)")
    st.caption("كاش + بنك 1 + بنك 2 = إجمالي الفاتورة")
    client = st.text_input("العميل", value="عميل نقدي")
    inv_no = st.text_input("رقم الفاتورة", value=f"INV-{datetime.now().strftime('%H%M%S')}")
    item = st.text_input("الصنف")
    itype = st.selectbox("النوع", ["أخضر", "مطحون", "محمص", "كوبي كاب"])
    qty = st.number_input("الكمية (كجم)", 0.001, value=1.0)
    unit_p = st.number_input("سعر الوحدة", 0.0, value=0.0)
    discount = st.number_input("خصم", 0.0, value=0.0)
    gross = qty * unit_p
    net = gross - discount
    st.info(f"صافي الفاتورة: **{net:,.2f} ج.م**")
    c1, c2, c3 = st.columns(3)
    cash = c1.number_input("كاش", 0.0, value=float(net))
    bank_1 = c2.number_input("بنك 1", 0.0, value=0.0)
    bank_2 = c3.number_input("بنك 2", 0.0, value=0.0)
    total_paid = cash + bank_1 + bank_2
    if abs(total_paid - net) > 0.01:
        st.warning(f"المجموع ({total_paid:,.2f}) ≠ الصافي ({net:,.2f})")
    if st.button("✅ تأكيد الفاتورة والدفع المقسّم") and item:
        try:
            division = "green" if itype == "أخضر" else ("roast" if itype == "محمص" else "ground")
            lines = [
                {
                    "item": item,
                    "type": itype,
                    "qty": qty,
                    "unit_price": unit_p,
                    "line_total": gross,
                    "division": division,
                }
            ]
            bid, n, sp = create_bill_with_split(
                conn, inv_no, client, lines, discount, cash, bank_1, bank_2, banks_list
            )
            st.success(f"تم حفظ الفاتورة {inv_no} — صافي {n:,.2f} ج.م — تم إرسالها لـ KDS")
            st.json(sp)
        except GuardError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"خطأ: {e}")

    st.markdown("---")
    st.markdown("### 🔙 معالجة المرتجعات")
    ret_inv = st.text_input("رقم الفاتورة الأصلية للمرتجع")
    if st.button("تسجيل مرتجع كامل") and ret_inv:
        try:
            username = st.session_state.get("username", "system")
            rno = process_return(conn, ret_inv, username, banks_list)
            st.success(f"تم المرتجع: {rno}")
            st.rerun()
        except GuardError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"خطأ: {e}")
