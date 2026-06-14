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
_RE_AS_AR_ALIAS = re.compile(r"\bAS\s+([\u0600-\u06FF][\w\u0600-\u06FF]*)", re.I)
_RE_COL_AR_ALIAS = re.compile(
    r"(?<!\.)(?P<col>(?<!AS )(?<!\bAS )\b(?!AS\b)[\w]+)\s+(?P<alias>[\u0600-\u06FF][\w\u0600-\u06FF]*)(?=\s*[,)]|\s+FROM|\s+WHERE|\s+ORDER|\s+LIMIT|\s+GROUP)",
    re.I,
)


def _apply_col_ar_alias(match):
    col = match.group("col")
    if col.upper() == "AS":
        return match.group(0)
    return f'{col} AS "{match.group("alias")}"'


def _translate_sql(query):
    q = query.strip()

    if _RE_INSERT_IGNORE.search(q):
        q = _RE_INSERT_IGNORE.sub("INSERT INTO", q)
        if "ON CONFLICT" not in q.upper():
            q = q.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

    q = _RE_AS_QUOTED.sub(r'AS "\1"', q)
    q = _RE_AS_AR_ALIAS.sub(r'AS "\1"', q)
    q = _RE_COL_QUOTED_ALIAS.sub(r'\1 AS "\2"', q)
    q = _RE_LITERAL_AR_ALIAS.sub(r'\1 AS "\2"', q)
    q = _RE_COL_AR_ALIAS.sub(_apply_col_ar_alias, q)

    q = _RE_QTY_UPSERT.sub("qty=inv.qty+", q)
    return q.replace("?", "%s")


class PgCursor:
    def __init__(self, cursor, conn):
        self._cur = cursor
        self._conn = conn
        self.description = None

    def execute(self, query, params=()):
        try:
            self._cur.execute(_translate_sql(query), params or ())
        except Exception:
            self._conn.rollback()
            raise
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
        return PgCursor(self._conn.cursor(), self._conn)

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
        _pools[dsn] = pool.ThreadedConnectionPool(2, 12, dsn, **kwargs)
    raw = _pools[dsn].getconn()
    return PgConnection(raw, _pools[dsn])


def read_sql_query(query, conn, params=None):
    cur = conn.cursor()
    try:
        cur.execute(query, params or ())
    except Exception:
        try:
            conn._conn.rollback()
        except Exception:
            pass
        raise
    columns = [desc[0] for desc in cur._cur.description] if cur._cur.description else []
    rows = cur.fetchall()
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns)
