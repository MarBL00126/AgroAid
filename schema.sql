-- AgroSafety / AgroAid - PostgreSQL schema
-- Idempotente: se puede volver a correr sin riesgo.

CREATE TABLE IF NOT EXISTS tenants (
    id          SERIAL PRIMARY KEY,
    slug        VARCHAR(100) UNIQUE NOT NULL,
    name        VARCHAR(255) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO tenants (slug, name)
VALUES ('default', 'Default')
ON CONFLICT (slug) DO NOTHING;

CREATE TABLE IF NOT EXISTS consultas (
    id                SERIAL PRIMARY KEY,
    tenant_id         INTEGER REFERENCES tenants(id),
    consulta_inicial  TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    id             SERIAL PRIMARY KEY,
    tenant_id      INTEGER REFERENCES tenants(id),
    username       VARCHAR(100) UNIQUE NOT NULL,
    email          VARCHAR(255) UNIQUE NOT NULL,
    password_hash  TEXT NOT NULL,
    role           VARCHAR(30) NOT NULL DEFAULT 'user',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS respuestas (
    id                SERIAL PRIMARY KEY,
    tenant_id         INTEGER REFERENCES tenants(id),
    consulta_id       INTEGER NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
    iteracion         INTEGER NOT NULL,
    preguntas         JSONB,
    respuesta         TEXT,
    confianza_antes   INTEGER,
    riesgo_antes      TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS auditoria (
    id           SERIAL PRIMARY KEY,
    tenant_id    INTEGER REFERENCES tenants(id),
    consulta_id  INTEGER NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
    iteracion    INTEGER,
    accion       TEXT NOT NULL,
    detalle      JSONB,
    entry_hash   TEXT,
    prev_hash    TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evaluaciones_finales (
    id                      SERIAL PRIMARY KEY,
    tenant_id               INTEGER REFERENCES tenants(id),
    consulta_id             INTEGER NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
    evaluacion_final        TEXT,
    iteraciones_realizadas  INTEGER,
    abstuvo                 BOOLEAN NOT NULL DEFAULT FALSE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS metricas_seguridad (
    id                    SERIAL PRIMARY KEY,
    tenant_id             INTEGER REFERENCES tenants(id),
    consulta_id           INTEGER NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
    se_abstuvo            BOOLEAN,
    nivel_riesgo          TEXT,
    confianza_final       INTEGER,
    evidencia_suficiente  BOOLEAN,
    iteraciones           INTEGER,
    duracion_seg          DOUBLE PRECISION,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS api_keys (
    id          SERIAL PRIMARY KEY,
    tenant_id   INTEGER REFERENCES tenants(id),
    name        VARCHAR(100) NOT NULL,
    key_hash    VARCHAR(64) UNIQUE NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS whatsapp_contacts (
    id           SERIAL PRIMARY KEY,
    phone_number VARCHAR(30) NOT NULL,
    tenant_id    INTEGER NOT NULL,
    producer_id  INTEGER,
    active       BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS whatsapp_sessions (
    phone        VARCHAR(30) PRIMARY KEY,
    consulta_id  INTEGER REFERENCES consultas(id) ON DELETE SET NULL,
    state        VARCHAR(30) NOT NULL DEFAULT 'idle',
    tenant_id    INTEGER REFERENCES tenants(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT whatsapp_sessions_state_check
        CHECK (state IN ('idle', 'in_progress'))
);

CREATE TABLE IF NOT EXISTS webhooks (
    id         SERIAL PRIMARY KEY,
    tenant_id  INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    url        TEXT NOT NULL,
    secret     TEXT NOT NULL,
    events     TEXT[] NOT NULL DEFAULT '{}',
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tenant_branding (
    tenant_id     INTEGER PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    logo_url      TEXT NOT NULL DEFAULT '',
    primary_color TEXT NOT NULL DEFAULT '#16a34a',
    accent_color  TEXT NOT NULL DEFAULT '#15803d',
    app_name      TEXT NOT NULL DEFAULT 'AgroAid',
    footer_text   TEXT NOT NULL DEFAULT 'AgroSafety - Hackathon Global South AI Safety 2026'
);

INSERT INTO tenant_branding (tenant_id)
VALUES (1)
ON CONFLICT (tenant_id) DO NOTHING;

-- Columnas de migraciones (ADD COLUMN IF NOT EXISTS es idempotente)
ALTER TABLE consultas            ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id);
ALTER TABLE users                ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id);
ALTER TABLE users                ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user';
ALTER TABLE users                ADD COLUMN IF NOT EXISTS whatsapp TEXT UNIQUE;
ALTER TABLE respuestas           ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id);
ALTER TABLE auditoria            ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id);
ALTER TABLE auditoria            ADD COLUMN IF NOT EXISTS entry_hash TEXT;
ALTER TABLE auditoria            ADD COLUMN IF NOT EXISTS prev_hash TEXT;
ALTER TABLE evaluaciones_finales ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id);
ALTER TABLE evaluaciones_finales ADD COLUMN IF NOT EXISTS abstuvo BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE metricas_seguridad   ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id);
ALTER TABLE api_keys             ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id);

-- La view va DESPUES de los ALTER TABLE para que tenant_id ya exista en metricas_seguridad
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
   AND m.tenant_id = c.tenant_id;

CREATE INDEX IF NOT EXISTS idx_consultas_tenant_id              ON consultas(tenant_id);
CREATE INDEX IF NOT EXISTS idx_respuestas_consulta_id           ON respuestas(consulta_id);
CREATE INDEX IF NOT EXISTS idx_auditoria_consulta_id            ON auditoria(consulta_id);
CREATE INDEX IF NOT EXISTS idx_evaluaciones_finales_consulta_id ON evaluaciones_finales(consulta_id);
CREATE INDEX IF NOT EXISTS idx_metricas_seguridad_consulta_id   ON metricas_seguridad(consulta_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash                ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_whatsapp_sessions_consulta_id    ON whatsapp_sessions(consulta_id);
CREATE INDEX IF NOT EXISTS idx_whatsapp_sessions_tenant_id      ON whatsapp_sessions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_webhooks_tenant_active           ON webhooks(tenant_id, is_active);