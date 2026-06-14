# -*- coding: utf-8 -*-
"""User list + role-based permissions management."""
import streamlit as st

from kobe_vast.auth_security import hash_password, password_strength_hint, validate_password
from kobe_vast.mobile_ui import delete_button, styled_dataframe
from kobe_vast.permissions import role_pages_summary

ROLES = [
    ("مدير", "صلاحيات كاملة — إعدادات، مستخدمين، حذف سجلات"),
    ("محاسب", "مبيعات، خزينة، تقارير، لوحة المالك"),
    ("كاشير", "مبيعات، كوبي كاب، KDS، دفع متعدد"),
    ("مخزن", "مخزون، تحميص، خلطات، KDS"),
    ("مشاهدة", "عرض تقارير ومخزون فقط — بدون تعديل"),
]


def _role_labels():
    return [r[0] for r in ROLES]


def render_permissions_matrix():
    st.markdown("#### 🔐 الصلاحيات")
    rows = []
    for role_key, desc in ROLES:
        pages = role_pages_summary(role_key)
        rows.append({
            "الدور": role_key,
            "الوصف": desc,
            "الصفحات": "، ".join(pages),
        })
    styled_dataframe(__import__("pandas").DataFrame(rows))


def render_user_admin(conn, sql_df, current_username):
    st.markdown("## 👥 المستخدمين والصلاحيات")

    users_df = sql_df("SELECT id, username, role FROM users ORDER BY id", conn)
    if users_df is not None and not users_df.empty:
        show = users_df.rename(columns={"id": "#", "username": "المستخدم", "role": "الصلاحية"})
        styled_dataframe(show)
        st.caption(f"إجمالي: **{len(users_df)}** مستخدم")
    else:
        st.info("لا يوجد مستخدمون بعد")

    render_permissions_matrix()

    st.markdown("---")
    st.markdown("### ➕ إضافة مستخدم جديد")
    st.caption(password_strength_hint())

    with st.form("add_user_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        nu = c1.text_input("اسم المستخدم *")
        nr = c2.selectbox("الصلاحية *", _role_labels())
        for rk, desc in ROLES:
            if rk == nr:
                st.caption(desc)
                break
        p1 = st.text_input("كلمة المرور *", type="password")
        p2 = st.text_input("تأكيد كلمة المرور *", type="password")
        submitted = st.form_submit_button("✅ إضافة للقائمة", use_container_width=True)
        if submitted:
            if not nu.strip():
                st.error("أدخل اسم المستخدم")
            elif p1 != p2:
                st.error("كلمتا المرور غير متطابقتين")
            else:
                ok, err = validate_password(p1)
                if not ok:
                    st.error(err)
                else:
                    try:
                        conn.execute(
                            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                            (nu.strip(), hash_password(p1), nr),
                        )
                        conn.commit()
                        st.success(f"تم إضافة {nu} بصلاحية {nr}")
                        st.rerun()
                    except Exception:
                        st.error("اسم المستخدم مسجل مسبقاً")

    st.markdown("---")
    st.markdown("### ✏️ تعديل صلاحية أو كلمة مرور")
    if users_df is not None and not users_df.empty:
        user_opts = {
            f"{r['username']} ({r['role']})": int(r["id"])
            for _, r in users_df.iterrows()
        }
        sel = st.selectbox("اختر مستخدم", list(user_opts.keys()))
        uid = user_opts[sel]
        sel_user = sel.split(" (")[0]

        c1, c2 = st.columns(2)
        new_role = c1.selectbox("صلاحية جديدة", _role_labels(), key="edit_role")
        if c2.button("💾 حفظ الصلاحية", use_container_width=True, key="user_save_role"):
            conn.execute("UPDATE users SET role=? WHERE id=?", (new_role, uid))
            conn.commit()
            st.success("تم تحديث الصلاحية")
            st.rerun()

        st.caption(password_strength_hint())
        np1 = st.text_input("كلمة مرور جديدة", type="password", key="np1")
        np2 = st.text_input("تأكيد كلمة المرور الجديدة", type="password", key="np2")
        if st.button("🔑 تغيير كلمة المرور", use_container_width=True, key="user_change_pw") and np1:
            if np1 != np2:
                st.error("كلمتا المرور غير متطابقتين")
            else:
                ok, err = validate_password(np1)
                if not ok:
                    st.error(err)
                else:
                    conn.execute(
                        "UPDATE users SET password=? WHERE id=?",
                        (hash_password(np1), uid),
                    )
                    conn.commit()
                    st.success("تم تغيير كلمة المرور")
                    st.rerun()

        if sel_user != current_username:
            if delete_button(f"حذف المستخدم {sel_user}", key=f"del_user_{uid}"):
                conn.execute("DELETE FROM users WHERE id=?", (uid,))
                conn.commit()
                st.success("تم الحذف")
                st.rerun()
        else:
            st.warning("لا يمكنك حذف حسابك أثناء تسجيل الدخول")
