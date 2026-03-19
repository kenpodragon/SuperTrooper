"""Database connection pool using psycopg2."""

import json
import datetime
import decimal
from contextlib import contextmanager

import psycopg2
import psycopg2.pool
import psycopg2.extras

import config

# Register JSON adapter for psycopg2
psycopg2.extras.register_default_jsonb(loads=json.loads)

_pool = None


def get_pool():
    """Return the global connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            host=config.DB_HOST,
            port=config.DB_PORT,
            dbname=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
        )
    return _pool


def close_pool():
    """Close all connections in the pool."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


@contextmanager
def get_conn():
    """Context manager that checks out a connection and returns it when done."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


@contextmanager
def get_cursor(cursor_factory=None):
    """Context manager that yields a cursor with auto-commit/rollback."""
    factory = cursor_factory or psycopg2.extras.RealDictCursor
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=factory)
        try:
            yield cur
        finally:
            cur.close()


def query(sql, params=None):
    """Execute a SELECT and return all rows as list of dicts."""
    with get_cursor() as cur:
        cur.execute(sql, params or ())
        return [dict(row) for row in cur.fetchall()]


def query_one(sql, params=None):
    """Execute a SELECT and return a single row dict or None."""
    with get_cursor() as cur:
        cur.execute(sql, params or ())
        row = cur.fetchone()
        return dict(row) if row else None


def execute(sql, params=None):
    """Execute an INSERT/UPDATE/DELETE. Returns rowcount."""
    with get_cursor() as cur:
        cur.execute(sql, params or ())
        return cur.rowcount


def execute_returning(sql, params=None):
    """Execute an INSERT/UPDATE with RETURNING clause. Returns the row dict."""
    with get_cursor() as cur:
        cur.execute(sql, params or ())
        row = cur.fetchone()
        return dict(row) if row else None


def serialize(obj):
    """JSON-safe serializer for dates, decimals, etc."""
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
