# -*- coding: utf-8 -*-
"""SQLite-compatible PostgreSQL wrapper for Kobe Green ERP."""
import re

import pandas as pd
import psycopg2
from psycopg2 import pool

_RE_INSERT_IGNORE = re.compile(r"INSERT\s+OR\s+IGNORE\s+INTO", re.I)
_RE_QTY_UPSERT = re.compile(r"\bqty=qty\+")
_RE_AS_QUOTED = re.compile(r"\bas\s+'([^']+)'", re.I)
_RE_COL_QUOTED_ALIAS = re.compile(r"(\w+)\s+'([^']+)'(?=\s*[,)]|\s+FROM)", re.I)
_RE_LITERAL_AR_ALIAS = re.compile(r"('(?:[^']*\|\|[^']*|[^']*)')\s+([\u0600-\u06FF][\w\u0600-\u06FF]*)")
_RE_COL_AR_ALIAS = re.compile(
    r"(\w+)\s+([\u0600-\u06FF][\w\u0600-\u06FF]*)(?=\s*[,)]|\s+FROM|\s+WHERE|\s+ORDER|\s+LIMIT)",
    re.I,
)


def _translate_sql(query):
    q = query.strip()

    if _RE_INSERT_IGNORE.search(q):
        q = _RE_INSERT_IGNORE.sub("INSERT INTO", q)
        if "ON CONFLICT" not in q.upper():
            q = q.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

    # SQLite:  col as 'alias'  ->  col AS "alias"
    q = _RE_AS_QUOTED.sub(r'AS "\1"', q)
    # SQLite:  col 'alias'  (in SELECT list)
    q = _RE_COL_QUOTED_ALIAS.sub(r'\1 AS "\2"', q)
    # SQLite:  'literal' alias  or  'expr'||x alias
    q = _RE_LITERAL_AR_ALIAS.sub(r'\1 AS "\2"', q)
    # SQLite:  col ArabicAlias  (no AS keyword)
    q = _RE_COL_AR_ALIAS.sub(r'\1 AS "\2"', q)

    q = _RE_QTY_UPSERT.sub("qty=inv.qty+", q)
    return q.replace("?", "%s")


class PgCursor:
    def __init__(self, cursor):
        self._cur = cursor
        self.description = None

    def execute(self, query, params=()):
        self._cur.execute(_translate_sql(query), params or ())
        self.description = self._cur.description
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()


class PgConnection:
    def __init__(self, conn, connection_pool=None):
        self._conn = conn
        self._pool = connection_pool

    def execute(self, query, params=()):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def cursor(self):
        return PgCursor(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def close(self):
        if self._pool is not None:
            self._pool.putconn(self._conn)
        else:
            self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self.close()
        return False


_pools = {}


def connect(dsn, **kwargs):
    if dsn not in _pools:
        _pools[dsn] = pool.ThreadedConnectionPool(1, 6, dsn, **kwargs)
    raw = _pools[dsn].getconn()
    return PgConnection(raw, _pools[dsn])


def read_sql_query(query, conn, params=None):
    cur = conn.cursor()
    cur.execute(query, params or ())
    columns = [desc[0] for desc in cur._cur.description] if cur._cur.description else []
    rows = cur.fetchall()
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns)
