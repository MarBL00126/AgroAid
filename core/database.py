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
    statements = [
        """
        CREATE TABLE IF NOT EXISTS tenants (
            id SERIAL PRIMARY KEY,
            slug VARCHAR(100) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        INSERT INTO tenants (slug, name)
        VALUES ('default', 'Default')
        ON CONFLICT (slug) DO NOTHING
        """,
        """
        CREATE TABLE IF NOT EXISTS consultas (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER REFERENCES tenants(id),
            consulta_inicial TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER REFERENCES tenants(id),
            username VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role VARCHAR(30) NOT NULL DEFAULT 'user',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS respuestas (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER REFERENCES tenants(id),
            consulta_id INTEGER NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
            iteracion INTEGER NOT NULL,
            preguntas JSONB,
            respuesta TEXT,
            confianza_antes INTEGER,
            riesgo_antes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS auditoria (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER REFERENCES tenants(id),
            consulta_id INTEGER NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
            iteracion INTEGER,
            accion TEXT NOT NULL,
            detalle JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS evaluaciones_finales (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER REFERENCES tenants(id),
            consulta_id INTEGER NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
            evaluacion_final TEXT,
            iteraciones_realizadas INTEGER,
            abstuvo BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS metricas_seguridad (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER REFERENCES tenants(id),
            consulta_id INTEGER NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
            se_abstuvo BOOLEAN,
            nivel_riesgo TEXT,
            confianza_final INTEGER,
            evidencia_suficiente BOOLEAN,
            iteraciones INTEGER,
            duracion_seg DOUBLE PRECISION,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        
"""
CREATE OR REPLACE VIEW historial_consultas AS
SELECT
    c.id AS consulta_id,
    c.tenant_id,
    c.consulta_inicial,
    c.created_at AS fecha_consulta,
    m.se_abstuvo,
    m.nivel_riesgo,
    m.confianza_final,
    m.evidencia_suficiente,
    m.iteraciones,
    m.duracion_seg
FROM consultas c
LEFT JOIN metricas_seguridad m
    ON m.consulta_id = c.id
   AND m.tenant_id = c.tenant_id
"""


        ,
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER REFERENCES tenants(id),
            name VARCHAR(100) NOT NULL,
            key_hash VARCHAR(64) UNIQUE NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ
        )
        """,
        "ALTER TABLE consultas ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(30) NOT NULL DEFAULT 'user'",
        "ALTER TABLE respuestas ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id)",
        "ALTER TABLE auditoria ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id)",
        "ALTER TABLE evaluaciones_finales ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id)",
        "ALTER TABLE evaluaciones_finales ADD COLUMN IF NOT EXISTS abstuvo BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE metricas_seguridad ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id)",
        "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id)",
        "CREATE INDEX IF NOT EXISTS idx_consultas_tenant_id ON consultas(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_respuestas_consulta_id ON respuestas(consulta_id)",
        "CREATE INDEX IF NOT EXISTS idx_auditoria_consulta_id ON auditoria(consulta_id)",
        "CREATE INDEX IF NOT EXISTS idx_evaluaciones_finales_consulta_id ON evaluaciones_finales(consulta_id)",
        "CREATE INDEX IF NOT EXISTS idx_metricas_seguridad_consulta_id ON metricas_seguridad(consulta_id)",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash)",
    ]

    with get_conn() as conn:
        try:
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
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
