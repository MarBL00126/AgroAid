"""
Database helpers for AgroSafety.

The project uses psycopg2 directly. This module owns the connection pool and
small query helpers so routers do not create one-off connections or depend on
SQLAlchemy.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager

from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger("agrosafety.db")

_pool: ThreadedConnectionPool | None = None


def init_pool() -> None:
    global _pool

    if _pool is not None:
        return

    _pool = ThreadedConnectionPool(
        minconn=1,
        maxconn=int(os.environ.get("DB_POOL_MAX", "10")),
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ.get("DB_NAME", "agrosafety"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
    )
    logger.info("PostgreSQL pool inicializado")


def close_pool() -> None:
    global _pool

    if _pool is not None:
        _pool.closeall()
        _pool = None
        logger.info("PostgreSQL pool cerrado")


def is_pool_initialized() -> bool:
    return _pool is not None


@contextmanager
def get_conn():
    if _pool is None:
        raise RuntimeError("Pool de DB no inicializado")

    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)


def db_exec(sql: str, params: tuple = ()) -> None:
    with get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def db_fetch_one(sql: str, params: tuple = ()) -> dict | None:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None


def db_fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def db_fetch_val(sql: str, params: tuple = ()):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return row[0] if row else None


def ensure_schema() -> None:
    import pathlib

    schema_path = pathlib.Path(__file__).parent.parent / "schema.sql"
    if not schema_path.exists():
        raise RuntimeError(f"schema.sql no encontrado en {schema_path}")

    raw = schema_path.read_text(encoding="utf-8-sig")  # utf-8-sig strips BOM if present
    stmts = [s.strip() for s in raw.split(";") if s.strip()]

    with get_conn() as conn:
        try:
            with conn.cursor() as cur:
                for stmt in stmts:
                    cur.execute(stmt)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    logger.info("Schema verificado/creado")


def get_tenant_id(slug: str = "default") -> int:
    normalized = (slug or "default").strip().lower()
    name = "Default" if normalized == "default" else normalized

    with get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tenants (slug, name)
                    VALUES (%s, %s)
                    ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
                    RETURNING id
                    """,
                    (normalized, name),
                )
                tenant_id = cur.fetchone()[0]
            conn.commit()
            return tenant_id
        except Exception:
            conn.rollback()
            raise
