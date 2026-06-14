# -*- coding: utf-8 -*-
"""Ensure VAST tables exist — auto-create on PostgreSQL & SQLite."""


def _is_pg(conn):
    return type(conn).__name__ == "PgConnection"


def table_exists(conn, table_name):
    try:
        conn.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
        return True
    except Exception:
        try:
            conn.commit()
        except Exception:
            pass
        return False


def _run_ddl(conn, statements):
    for stmt in statements:
        s = stmt.strip()
        if not s:
            continue
        try:
            conn.execute(s)
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                conn.execute(s)
            except Exception:
                pass
    try:
        conn.commit()
    except Exception:
        pass


def _pg_late_statements():
    from kobe_vast.schema_v2 import LATE_MIGRATION_STATEMENTS
    return LATE_MIGRATION_STATEMENTS


def _sqlite_late_statements():
    return [
        """
        CREATE TABLE IF NOT EXISTS api_partners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_name TEXT NOT NULL,
            partner_type TEXT DEFAULT 'متعاون',
            api_key_hash TEXT NOT NULL,
            api_key_prefix TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            revoked_at TEXT,
            last_used_at TEXT,
            notes TEXT DEFAULT '',
            webhook_url TEXT DEFAULT ''
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS shipping_companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            brand TEXT NOT NULL DEFAULT 'green',
            phone TEXT DEFAULT '',
            contact_name TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            UNIQUE(name, brand)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS shipping_cod (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            inv_no TEXT DEFAULT '',
            client TEXT DEFAULT '',
            cod_amount REAL DEFAULT 0,
            shipping_fee REAL DEFAULT 0,
            net_due REAL DEFAULT 0,
            status TEXT DEFAULT 'pending',
            settled_date TEXT,
            notes TEXT DEFAULT ''
        )
        """,
    ]


def ensure_all_late_tables(conn):
    """Create api_partners + shipping tables if missing."""
    if _is_pg(conn):
        _run_ddl(conn, _pg_late_statements())
    else:
        _run_ddl(conn, _sqlite_late_statements())


def ensure_partners_table(conn):
    if not table_exists(conn, "api_partners"):
        ensure_all_late_tables(conn)
    if not table_exists(conn, "api_partners"):
        raise RuntimeError(
            "جدول api_partners غير موجود — شغّل FIX_MIGRATION.bat ثم أعد تحميل الصفحة"
        )


def ensure_shipping_tables(conn):
    if not table_exists(conn, "shipping_companies"):
        ensure_all_late_tables(conn)
    if not table_exists(conn, "shipping_companies"):
        raise RuntimeError(
            "جدول shipping_companies غير موجود — شغّل FIX_MIGRATION.bat"
        )


def require_table(conn, table_name, hint="شغّل FIX_MIGRATION.bat"):
    if table_name == "api_partners":
        ensure_partners_table(conn)
        return True
    if table_name in ("shipping_companies", "shipping_cod"):
        ensure_shipping_tables(conn)
        return True
    if not table_exists(conn, table_name):
        raise RuntimeError(f"جدول {table_name} غير موجود — {hint}")
    return True
