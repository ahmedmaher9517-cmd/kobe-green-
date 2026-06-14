# -*- coding: utf-8 -*-
"""KDS queue service — auto-link invoices to kitchen tickets."""
import json
import uuid
from datetime import datetime

from kobe_vast.kds_common import classify_line


def build_line_items_from_sales_rows(rows):
    """rows: cart dicts, tuples, or sales rows."""
    items = []
    for r in rows:
        if isinstance(r, dict):
            item = r.get("item") or r.get("name", "")
            itype = r.get("type", "أخضر")
            qty = float(r.get("qty", 0))
        else:
            item, itype, qty = r[0], r[1], float(r[2])
        if not item or qty <= 0:
            continue
        key, _ = classify_line(str(itype))
        items.append({"item": item, "type": itype, "qty": qty, "division": key})
    return items


def enqueue_kds_order(conn, inv_no, client, line_items, source="invoice"):
    """Create pending KDS ticket linked to invoice."""
    if not line_items:
        return None
    existing = conn.execute(
        "SELECT id FROM kds_orders WHERE inv_no=? AND status='pending'",
        (inv_no,),
    ).fetchone()
    if existing:
        return str(existing[0])
    order_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO kds_orders (id, inv_no, client, status, line_items, created_at)
        VALUES (?::uuid, ?, ?, 'pending', ?::jsonb, NOW())
        """,
        (
            order_id,
            inv_no,
            client or "",
            json.dumps(line_items, ensure_ascii=False),
        ),
    )
    conn.execute(
        "INSERT INTO audit_log (event_type, ref_id, payload) VALUES (?, ?, ?::jsonb)",
        (
            "kds_queued",
            inv_no,
            json.dumps({"source": source, "lines": len(line_items)}, ensure_ascii=False),
        ),
    )
    return order_id


def fetch_pending_kds(conn, sql_df):
    try:
        return sql_df(
            """
            SELECT id, inv_no, client, line_items, created_at
            FROM kds_orders WHERE status='pending'
            ORDER BY created_at ASC
            """,
            conn,
        )
    except Exception:
        return None


def load_partitions_from_order(order_row):
    partitions = {"green": [], "roast": [], "ground": []}
    labels = {}
    raw = order_row.get("line_items", "[]")
    if isinstance(raw, str):
        raw = json.loads(raw)
    for it in raw:
        key = it.get("division") or classify_line(str(it.get("type", "أخضر")))[0]
        partitions.setdefault(key, []).append(it)
        _, lbl = classify_line(str(it.get("type", "أخضر")))
        labels[key] = lbl
    return partitions, labels, order_row.get("client", "")
