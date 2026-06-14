# -*- coding: utf-8 -*-
"""Push B2B / campaign client data into CRM leads."""


def push_b2b_lead(conn, name, phone="", company="", email="", tier="", products="", source="B2B Campaign", notes_extra=""):
    """Insert or update a lead from B2B campaign / quotation."""
    name = (name or "").strip()
    if not name:
        return False, "اسم العميل مطلوب"

    phone = (phone or "").strip()
    company = (company or "").strip()
    email = (email or "").strip()
    tier = (tier or "").strip()
    products = (products or "").strip()

    requests_parts = []
    if tier:
        requests_parts.append(f"شريحة: {tier}")
    if products:
        requests_parts.append(f"أصناف: {products}")
    requests = " | ".join(requests_parts)

    notes_parts = []
    if company:
        notes_parts.append(f"شركة: {company}")
    if email:
        notes_parts.append(f"بريد: {email}")
    if notes_extra:
        notes_parts.append(notes_extra)
    notes = " | ".join(notes_parts)

    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")

    if phone:
        row = conn.execute(
            "SELECT id FROM leads WHERE phone = ? AND phone != '' ORDER BY id DESC LIMIT 1",
            (phone,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE leads SET name=?, requests=?, status='تفاوض', source=?, notes=? WHERE id=?",
                (name, requests, source, notes, row[0]),
            )
            conn.commit()
            return True, f"تم تحديث العميل في CRM (#{row[0]})"

    conn.execute(
        "INSERT INTO leads (date, name, phone, requests, status, source, notes) VALUES (?,?,?,?,?,?,?)",
        (today, name, phone, requests, "جديد", source, notes),
    )
    conn.commit()
    return True, "تم إضافة العميل إلى CRM"
