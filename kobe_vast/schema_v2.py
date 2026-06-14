# -*- coding: utf-8 -*-
"""Phase 1+ schema migrations for VAST / Kobe production features."""

# gen_random_uuid() is built-in on Supabase PG 15+ — no pgcrypto extension needed
V2_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS bills (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        inv_no TEXT UNIQUE NOT NULL,
        client TEXT,
        bill_date TEXT NOT NULL,
        bill_time TEXT,
        gross_total NUMERIC(12,2) DEFAULT 0,
        discount NUMERIC(12,2) DEFAULT 0,
        net_total NUMERIC(12,2) DEFAULT 0,
        payment_split JSONB DEFAULT '{"cash": 0, "bank_1": 0, "bank_2": 0}',
        is_return BOOLEAN DEFAULT FALSE,
        original_bill_id UUID REFERENCES bills(id),
        notes TEXT DEFAULT '',
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bill_lines (
        id BIGSERIAL PRIMARY KEY,
        bill_id UUID NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
        item TEXT NOT NULL,
        item_type TEXT,
        qty NUMERIC(10,3) NOT NULL DEFAULT 0,
        unit_price NUMERIC(12,2) DEFAULT 0,
        line_total NUMERIC(12,2) DEFAULT 0,
        division TEXT DEFAULT 'green'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS coffee_blends (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        blend_name TEXT NOT NULL UNIQUE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        recipe JSONB NOT NULL,
        target_sell_price NUMERIC(12,2) DEFAULT 0,
        notes TEXT DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kds_orders (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        inv_no TEXT NOT NULL,
        client TEXT,
        status TEXT DEFAULT 'pending',
        opened_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        duration_seconds INTEGER,
        delivery_method TEXT,
        driver_phone TEXT,
        tracking_ref TEXT,
        checklist JSONB DEFAULT '{}',
        line_items JSONB DEFAULT '[]',
        worker_username TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id BIGSERIAL PRIMARY KEY,
        event_type TEXT NOT NULL,
        ref_id TEXT,
        username TEXT,
        payload JSONB,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS employee_metrics (
        id BIGSERIAL PRIMARY KEY,
        username TEXT NOT NULL,
        week_start TEXT,
        base_pay NUMERIC(12,2) DEFAULT 2200,
        commission NUMERIC(12,2) DEFAULT 0,
        kds_orders_completed INTEGER DEFAULT 0,
        notes TEXT DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS machine_assets (
        id BIGSERIAL PRIMARY KEY,
        asset_name TEXT NOT NULL,
        asset_value NUMERIC(14,2) DEFAULT 0,
        depreciation_pct NUMERIC(5,2) DEFAULT 0,
        notes TEXT DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_bills_inv_no ON bills(inv_no)",
    "CREATE INDEX IF NOT EXISTS idx_bills_return ON bills(is_return)",
    "CREATE INDEX IF NOT EXISTS idx_bill_lines_bill ON bill_lines(bill_id)",
    "CREATE INDEX IF NOT EXISTS idx_kds_status ON kds_orders(status)",
    """
    CREATE TABLE IF NOT EXISTS api_partners (
        id BIGSERIAL PRIMARY KEY,
        partner_name TEXT NOT NULL,
        partner_type TEXT DEFAULT 'متعاون',
        api_key_hash TEXT NOT NULL,
        api_key_prefix TEXT NOT NULL,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TEXT,
        revoked_at TEXT,
        last_used_at TEXT,
        notes TEXT DEFAULT '',
        webhook_url TEXT DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_api_partners_active ON api_partners(is_active)",
    "CREATE INDEX IF NOT EXISTS idx_api_partners_hash ON api_partners(api_key_hash)",
    """
    CREATE TABLE IF NOT EXISTS shipping_companies (
        id BIGSERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        brand TEXT NOT NULL DEFAULT 'green',
        phone TEXT DEFAULT '',
        contact_name TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        is_active BOOLEAN DEFAULT TRUE,
        UNIQUE(name, brand)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS shipping_cod (
        id BIGSERIAL PRIMARY KEY,
        company_id BIGINT NOT NULL REFERENCES shipping_companies(id),
        date TEXT NOT NULL,
        inv_no TEXT DEFAULT '',
        client TEXT DEFAULT '',
        cod_amount NUMERIC(12,2) DEFAULT 0,
        shipping_fee NUMERIC(12,2) DEFAULT 0,
        net_due NUMERIC(12,2) DEFAULT 0,
        status TEXT DEFAULT 'pending',
        settled_date TEXT,
        notes TEXT DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ship_cod_company ON shipping_cod(company_id)",
    "CREATE INDEX IF NOT EXISTS idx_ship_cod_status ON shipping_cod(status)",
    """
    CREATE OR REPLACE VIEW stock AS
    SELECT id, name AS item_name, type AS item_type, qty AS quantity,
           buy_price AS unit_cost, sell_price, wholesale_price, dist_price
    FROM inv
    """,
]

# Tables added after initial deploy — safe to re-run anytime
LATE_MIGRATION_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS api_partners (
        id BIGSERIAL PRIMARY KEY,
        partner_name TEXT NOT NULL,
        partner_type TEXT DEFAULT 'متعاون',
        api_key_hash TEXT NOT NULL,
        api_key_prefix TEXT NOT NULL,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TEXT,
        revoked_at TEXT,
        last_used_at TEXT,
        notes TEXT DEFAULT '',
        webhook_url TEXT DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_api_partners_active ON api_partners(is_active)",
    "CREATE INDEX IF NOT EXISTS idx_api_partners_hash ON api_partners(api_key_hash)",
    """
    CREATE TABLE IF NOT EXISTS shipping_companies (
        id BIGSERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        brand TEXT NOT NULL DEFAULT 'green',
        phone TEXT DEFAULT '',
        contact_name TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        is_active BOOLEAN DEFAULT TRUE,
        UNIQUE(name, brand)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS shipping_cod (
        id BIGSERIAL PRIMARY KEY,
        company_id BIGINT NOT NULL REFERENCES shipping_companies(id),
        date TEXT NOT NULL,
        inv_no TEXT DEFAULT '',
        client TEXT DEFAULT '',
        cod_amount NUMERIC(12,2) DEFAULT 0,
        shipping_fee NUMERIC(12,2) DEFAULT 0,
        net_due NUMERIC(12,2) DEFAULT 0,
        status TEXT DEFAULT 'pending',
        settled_date TEXT,
        notes TEXT DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ship_cod_company ON shipping_cod(company_id)",
    "CREATE INDEX IF NOT EXISTS idx_ship_cod_status ON shipping_cod(status)",
]


def migrate_schema_v2(cur):
    """Run each DDL separately — safe on Supabase."""
    for stmt in V2_STATEMENTS:
        cur.execute(stmt.strip())


def migrate_late_schema(cur):
    """Idempotent — api_partners, shipping (for DBs migrated before these tables)."""
    for stmt in LATE_MIGRATION_STATEMENTS:
        try:
            cur.execute(stmt.strip())
        except Exception:
            pass


def seed_core_menu(cur):
    from kobe_vast.product_menu import CORE_PRODUCT_MENU, seed_inv_type

    for p in CORE_PRODUCT_MENU:
        itype = seed_inv_type(p["category"])
        cur.execute(
            """
            INSERT INTO inv (name, type, qty, buy_price, sell_price, wholesale_price, dist_price)
            VALUES (%s, %s, 0, %s, %s, %s, %s)
            ON CONFLICT (name, type) DO UPDATE SET
                sell_price = EXCLUDED.sell_price,
                wholesale_price = EXCLUDED.wholesale_price,
                dist_price = EXCLUDED.dist_price
            """,
            (
                p["name_ar"],
                itype,
                p["price"] * 0.75,
                p["price"],
                p["price"] * 0.92,
                p["price"] * 0.85,
            ),
        )

    cur.execute("SELECT COUNT(*) FROM coffee_blends")
    if cur.fetchone()[0] == 0:
        blends = [
            ("حبشي بليند", '{"حبشي": 0.6, "فيتنامي روبستا": 0.4}'),
            ("كولومبي بليند", '{"كولومبي": 0.5, "برازيلي": 0.5}'),
            ("اسبريسو بليند", '{"برازيلي": 0.4, "كولومبي": 0.35, "هندي روبستا": 0.25}'),
        ]
        for name, recipe in blends:
            cur.execute(
                "INSERT INTO coffee_blends (blend_name, recipe) VALUES (%s, %s::jsonb) ON CONFLICT (blend_name) DO NOTHING",
                (name, recipe),
            )
