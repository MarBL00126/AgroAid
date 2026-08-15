-- AgroSafety / AgroAid — Schema de PostgreSQL
-- Corré esto UNA VEZ contra la base de Railway.
-- Es seguro volver a correrlo: usa IF NOT EXISTS en todo.

CREATE TABLE IF NOT EXISTS consultas (
    id                SERIAL PRIMARY KEY,
    consulta_inicial  TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS respuestas (
    id                SERIAL PRIMARY KEY,
    consulta_id       INTEGER NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
    iteracion         INTEGER NOT NULL,
    preguntas         JSONB,
    respuesta         TEXT,
    confianza_antes   INTEGER,
    riesgo_antes      TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS auditoria (
    id                SERIAL PRIMARY KEY,
    consulta_id       INTEGER NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
    iteracion         INTEGER,
    accion            TEXT NOT NULL,
    detalle           JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evaluaciones_finales (
    id                      SERIAL PRIMARY KEY,
    consulta_id             INTEGER NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
    evaluacion_final        TEXT,
    iteraciones_realizadas  INTEGER,
    abstuvo                 BOOLEAN NOT NULL DEFAULT FALSE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS metricas_seguridad (
    id                      SERIAL PRIMARY KEY,
    consulta_id             INTEGER NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
    se_abstuvo              BOOLEAN,
    nivel_riesgo            TEXT,
    confianza_final         INTEGER,
    evidencia_suficiente    BOOLEAN,
    iteraciones             INTEGER,
    duracion_seg            DOUBLE PRECISION,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índices útiles para consultar por consulta_id (los joins/lookups más comunes)
CREATE INDEX IF NOT EXISTS idx_respuestas_consulta_id ON respuestas(consulta_id);
CREATE INDEX IF NOT EXISTS idx_auditoria_consulta_id ON auditoria(consulta_id);
CREATE INDEX IF NOT EXISTS idx_evaluaciones_finales_consulta_id ON evaluaciones_finales(consulta_id);
CREATE INDEX IF NOT EXISTS idx_metricas_seguridad_consulta_id ON metricas_seguridad(consulta_id);
