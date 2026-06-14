# db_wrapper.py
# Smart database connection for Al-Ghannam Fabrics ERP
# Automatically uses SQLite locally and Supabase PostgreSQL when deployed

import os
import sqlite3
from contextlib import contextmanager

# Detect environment
IS_DEPLOYED = False
SUPABASE_DB_URL = None

try:
    import streamlit as st
    if hasattr(st, 'secrets') and 'SUPABASE_DB_URL' in st.secrets:
        SUPABASE_DB_URL = st.secrets['SUPABASE_DB_URL']
        IS_DEPLOYED = True
except:
    SUPABASE_DB_URL = os.environ.get('SUPABASE_DB_URL', '')
    IS_DEPLOYED = bool(SUPABASE_DB_URL)

# Import PostgreSQL driver only if needed
if IS_DEPLOYED:
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        raise ImportError("psycopg2-binary required for deployed version. Add to requirements.")

# Database names
SQLITE_DB = os.environ.get("ALGHANNAM_DB_PATH", "Algannam_Trading.db")

@contextmanager
def get_connection():
    """
    Get database connection - SQLite for local, PostgreSQL for deployed
    Use as context manager: with get_connection() as conn:
    """
    if IS_DEPLOYED:
        # PostgreSQL/Supabase
        conn = psycopg2.connect(SUPABASE_DB_URL)
        conn.autocommit = False
        try:
            yield conn
        finally:
            conn.close()
    else:
        # SQLite
        conn = sqlite3.connect(SQLITE_DB, check_same_thread=False)
        try:
            yield conn
        finally:
            conn.close()

def get_conn():
    """
    Legacy function - returns connection (keep for backward compatibility)
    Warning: Remember to close connection when done!
    """
    if IS_DEPLOYED:
        return psycopg2.connect(SUPABASE_DB_URL)
    else:
        return sqlite3.connect(SQLITE_DB, check_same_thread=False)

def execute_query(query, params=None, fetch=True):
    """
    Execute a query with automatic parameter conversion
    Handles differences between SQLite (?) and PostgreSQL (%s)
    """
    if IS_DEPLOYED:
        # Convert ? to %s for PostgreSQL
        query = query.replace('?', '%s')
    
    with get_connection() as conn:
        cur = conn.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        
        if fetch:
            if IS_DEPLOYED:
                # Convert psycopg2 result to list of tuples (like SQLite)
                results = cur.fetchall()
            else:
                results = cur.fetchall()
            conn.commit()
            return results
        else:
            conn.commit()
            return None

def get_db_info():
    """Return current database type for debugging"""
    return {
        'type': 'PostgreSQL (Supabase)' if IS_DEPLOYED else 'SQLite',
        'deployed': IS_DEPLOYED,
        'db_name': SUPABASE_DB_URL[:30] + '...' if IS_DEPLOYED else SQLITE_DB
    }
