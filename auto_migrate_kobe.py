# auto_migrate_kobe.py
# Automatic Supabase migration for KOBE GREEN ERP
# Runs once on first deployment, creates all tables safely

def migrate_supabase_kobe(connection_url):
    """
    Create all Kobe ERP tables on Supabase (safe - uses IF NOT EXISTS)
    Called automatically on first cloud deployment
    """
    try:
        import psycopg2
    except ImportError:
        raise ImportError("psycopg2-binary required for Supabase")
    
    conn = psycopg2.connect(connection_url)
    conn.autocommit = False
    
    try:
        cur = conn.cursor()
        
        # Create all Kobe tables (translated from SQLite to PostgreSQL)
        SCHEMA = """
        -- Settings
        CREATE TABLE IF NOT EXISTS settings (
            id BIGSERIAL PRIMARY KEY,
            company_name TEXT,
            phone TEXT,
            address TEXT,
            gemini_key TEXT DEFAULT ''
        );
        
        -- Inventory
        CREATE TABLE IF NOT EXISTS inv (
            id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            qty NUMERIC(12,3) DEFAULT 0,
            buy_price NUMERIC(12,2) DEFAULT 0,
            sell_price NUMERIC(12,2) DEFAULT 0,
            wholesale_price NUMERIC(12,2) DEFAULT 0,
            dist_price NUMERIC(12,2) DEFAULT 0,
            UNIQUE(name, type)
        );
        
        -- Customers
        CREATE TABLE IF NOT EXISTS customers (
            id BIGSERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            phone TEXT,
            address TEXT,
            opening_balance NUMERIC(12,2) DEFAULT 0,
            pricing_tier TEXT DEFAULT 'قطاعي',
            credit_limit NUMERIC(12,2) DEFAULT 10000.0
        );
        
        -- Suppliers
        CREATE TABLE IF NOT EXISTS suppliers (
            id BIGSERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            phone TEXT
        );
        
        -- Sales
        CREATE TABLE IF NOT EXISTS sales (
            id BIGSERIAL PRIMARY KEY,
            date TEXT NOT NULL,
            time TEXT,
            inv_no TEXT,
            client TEXT,
            item TEXT,
            type TEXT,
            qty NUMERIC(12,3),
            unit_p NUMERIC(12,2),
            total NUMERIC(12,2),
            paid NUMERIC(12,2),
            discount NUMERIC(12,2),
            pay_method TEXT,
            shipping_method TEXT,
            is_return INTEGER DEFAULT 0
        );
        
        -- Purchases
        CREATE TABLE IF NOT EXISTS purchases (
            id BIGSERIAL PRIMARY KEY,
            date TEXT NOT NULL,
            time TEXT,
            supplier TEXT,
            item TEXT,
            type TEXT,
            qty NUMERIC(12,3),
            total NUMERIC(12,2),
            paid NUMERIC(12,2),
            pay_method TEXT
        );
        
        -- Treasury
        CREATE TABLE IF NOT EXISTS treasury (
            id BIGSERIAL PRIMARY KEY,
            date TEXT NOT NULL,
            time TEXT,
            movement_type TEXT,
            category TEXT,
            description TEXT,
            amount NUMERIC(12,2),
            pay_method TEXT,
            method_details TEXT DEFAULT '---'
        );
        
        -- Banks
        CREATE TABLE IF NOT EXISTS banks (
            id BIGSERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        );
        
        -- Users
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT,
            role TEXT
        );
        
        -- Roasting Log
        CREATE TABLE IF NOT EXISTS roasting_log (
            id BIGSERIAL PRIMARY KEY,
            date TEXT,
            green_bean TEXT,
            roasted_bean TEXT,
            in_qty NUMERIC(12,3),
            loss_pct NUMERIC(5,2),
            net_qty NUMERIC(12,3),
            cost NUMERIC(12,2),
            sell_price NUMERIC(12,2)
        );
        
        -- Shipping
        CREATE TABLE IF NOT EXISTS shipping (
            id BIGSERIAL PRIMARY KEY,
            date TEXT,
            order_ref TEXT,
            client TEXT,
            awb TEXT,
            is_delivered INTEGER DEFAULT 0
        );
        
        -- Leads
        CREATE TABLE IF NOT EXISTS leads (
            id BIGSERIAL PRIMARY KEY,
            date TEXT,
            name TEXT,
            phone TEXT,
            requests TEXT,
            status TEXT,
            source TEXT,
            notes TEXT DEFAULT ''
        );
        
        -- KC Customers
        CREATE TABLE IF NOT EXISTS kc_customers (
            id BIGSERIAL PRIMARY KEY,
            name TEXT UNIQUE,
            phone TEXT
        );
        
        -- Platforms
        CREATE TABLE IF NOT EXISTS platforms (
            id BIGSERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        );
        
        -- Ecommerce Inventory
        CREATE TABLE IF NOT EXISTS ecommerce_inv (
            id BIGSERIAL PRIMARY KEY,
            platform TEXT NOT NULL,
            item TEXT NOT NULL,
            type TEXT NOT NULL,
            qty NUMERIC(12,3) DEFAULT 0,
            UNIQUE(platform, item, type)
        );
        
        -- Ecommerce Sales
        CREATE TABLE IF NOT EXISTS ecommerce_sales (
            id BIGSERIAL PRIMARY KEY,
            date TEXT,
            platform TEXT,
            item TEXT,
            qty NUMERIC(12,3),
            gross_price NUMERIC(12,2),
            fees NUMERIC(12,2),
            net_profit NUMERIC(12,2)
        );
        
        -- TODOs
        CREATE TABLE IF NOT EXISTS todos (
            id BIGSERIAL PRIMARY KEY,
            task TEXT,
            is_done INTEGER DEFAULT 0,
            created_at TEXT
        );
        
        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date);
        CREATE INDEX IF NOT EXISTS idx_sales_client ON sales(client);
        CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(date);
        CREATE INDEX IF NOT EXISTS idx_treasury_date ON treasury(date);
        CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
        """
        
        cur.execute(SCHEMA)
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS company_id BIGINT")

        # VAST v2 in savepoint — failure won't abort base schema transaction
        cur.execute("SAVEPOINT vast_v2")
        try:
            from kobe_vast.schema_v2 import migrate_schema_v2, seed_core_menu
            migrate_schema_v2(cur)
            seed_core_menu(cur)
            cur.execute("RELEASE SAVEPOINT vast_v2")
        except Exception as vast_err:
            cur.execute("ROLLBACK TO SAVEPOINT vast_v2")
            import warnings
            warnings.warn(f"VAST schema v2 skipped: {vast_err}")

        # Always ensure late tables (api_partners, shipping) even if v2 savepoint failed
        try:
            from kobe_vast.schema_v2 import migrate_late_schema
            migrate_late_schema(cur)
        except Exception as late_err:
            import warnings
            warnings.warn(f"Late schema skipped: {late_err}")

        cur.execute("SELECT COUNT(*) FROM settings")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO settings (company_name, phone, address) VALUES (%s, %s, %s)",
                ("كوبي جرين | KOBE GREEN", "01027766055", "25 شارع محمد علي وسط البلد")
            )
        else:
            cur.execute(
                "UPDATE settings SET address=%s WHERE address IS NULL OR address='' OR address=%s",
                ("25 شارع محمد علي وسط البلد", "مصر — القاهرة"),
            )
        
        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                ("admin", "123", "مدير")
            )
        
        cur.execute("SELECT COUNT(*) FROM platforms")
        if cur.fetchone()[0] == 0:
            platforms = ["أمازون (FBA)", "نون (FBN)", "المتجر الإلكتروني"]
            for plat in platforms:
                cur.execute("INSERT INTO platforms (name) VALUES (%s)", (plat,))
        
        cur.execute("SELECT COUNT(*) FROM banks")
        if cur.fetchone()[0] == 0:
            banks = ["البنك الأهلي المصري", "بنك مصر", "CIB", "InstaPay"]
            for bank in banks:
                cur.execute("INSERT INTO banks (name) VALUES (%s)", (bank,))
        
        conn.commit()
        return True
        
    except Exception as e:
        conn.rollback()
        raise Exception(f"Migration failed: {e}")
    finally:
        conn.close()
