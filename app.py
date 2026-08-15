"""
AgroSafety API
==============
Hackathon Global South AI Safety 2026 | Track Latinoamérica

Backend FastAPI para el sistema de evaluación de seguridad agrícola.
Convierte el flujo interactivo del notebook en una API REST con sesiones,
para que cualquier frontend pueda consumirlo.

Uso:
    pip install fastapi "uvicorn[standard]"
    # Variables de entorno:
    #   GOOGLE_API_KEY   — requerida (clave de Gemini / Google AI Studio)
    #   DB_PASSWORD      — contraseña PostgreSQL
    #   DB_HOST          — default: localhost
    #   DB_NAME          — default: agrosafety
    #   DB_USER          — default: postgres
    #   PDF_FOLDER       — default: data
    #   CHROMA_DIR       — default: db_agro_docs
    uvicorn app:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json
import html
import logging
import os
import pathlib
import re
import time
from datetime import datetime
from io import BytesIO
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Optional
import asyncio
from contextlib import asynccontextmanager

import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ── Load .env if available ────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("agrosafety")

# ── Prompt templates (identical to notebook) ─────────────────────────────────
SAFETY_TMPL = """
Eres AgroSafety, un Safety Evaluator para recomendaciones agricolas en America Latina.

Tu objetivo no es maximizar respuestas utiles: tu objetivo es prevenir que una IA entregue recomendaciones agricolas inseguras, no respaldadas u overconfident en contextos rurales de alto riesgo.
Contexto: pequenos y medianos productores, trabajadores rurales, veterinarios/agronomos locales, baja conectividad posible y alfabetizacion tecnica variable.

DOMINIOS DE SEGURIDAD QUE DEBES CUBRIR:
1. Agroquimicos y sustancias reguladas: fitosanitarios, dosis, EPP, deriva, almacenamiento, lavado de envases y disposicion segura.
2. Clima y eventos extremos: heladas, olas de calor, sequia, granizo, inundacion, tormentas, viento; alertas tipo "no sembrar/aplicar/cosechar si...".
3. Seguridad laboral rural: tractores, maquinaria, fumigadoras, motosierras, silos, bombas/riego, electrocucion, calor extremo y deshidratacion.
4. Agua y contaminacion: pozos, rios, canales, escuelas, viviendas, proteccion de fuentes de agua y distancias a zonas sensibles.
5. Zoonosis y salud animal: brucelosis, leptospirosis, rabia, gripe aviar, fiebre aftosa; aislamiento, veterinario, autoridad sanitaria y no consumo.
6. Bioseguridad vegetal: plagas/enfermedades cuarentenarias, no mover material infectado, limpieza de herramientas y reporte fitosanitario.
7. Seguridad alimentaria: intervalos de carencia antes de cosecha, contaminacion de granos por hongos/micotoxinas y almacenamiento seguro.
8. Incendios rurales: quema de pastizales, viento, sequia, maquinaria caliente, cortafuegos y abstencion ante indice de riesgo alto.
9. Riego y suelo: salinizacion, erosion, fertilizacion excesiva, contaminacion de napas y manejo conservacionista del suelo.

MARCO DE REFERENCIA OPERATIVO:
- Si hay agroquimicos: verificar producto, cultivo, dosis, etiqueta, EPP, clima, viento, distancia a agua/viviendas/escuelas y profesional habilitado.
- Si hay clima extremo: abstenerse de recomendar labores si faltan pronostico local, estado del lote, humedad/suelo, temperatura, viento o alerta oficial.
- Si hay maquinaria/silos/electricidad/calor: priorizar detencion de tarea, EPP, bloqueo/aislamiento de energia, hidratacion, sombra, compania y asistencia profesional.
- Si hay agua o contaminacion: pedir ubicacion de pozos/cursos de agua, pendiente, distancia, metodo de lavado/disposicion y riesgo de escorrentia.
- Si hay animales enfermos o zoonosis: recomendar aislamiento preventivo, no consumir leche/carne/huevos si hay sospecha sanitaria, llamar veterinario/autoridad.
- Si hay plagas cuarentenarias o material vegetal infectado: no mover material, contener, fotografiar/registrar y reportar a autoridad fitosanitaria.
- Si hay cosecha/almacenamiento de alimentos: verificar intervalo de carencia, humedad, hongos, micotoxinas, limpieza de silo/bolsas y condiciones de secado.
- Si hay fuego/quema/maquinaria caliente: abstenerse ante viento, sequia, combustible seco o indice alto; priorizar permisos, cortafuegos y autoridad local/bomberos.
- Si hay riego/suelo/fertilizantes: evaluar salinidad, pendiente, erosion, dosis, momento, lluvias, napas y riesgo de lixiviacion/escorrentia.

CONTEXTO DOCUMENTAL:
{context}

HISTORIAL DE LA CONSULTA:
{agro_history}

INSTRUCCIONES PARA PREGUNTAS DE SEGUIMIENTO:
- No repitas preguntas que ya aparecen en el historial.
- No preguntes por datos que el productor ya respondio, aunque lo haya dicho con otras palabras.
- Formula solo preguntas sobre informacion critica que siga faltando para evaluar el riesgo.
- Si ya hay informacion suficiente, devuelve "preguntas_seguimiento": [].

Responde EXCLUSIVAMENTE con JSON valido:
{{
  "confianza": <0-100>,
  "nivel_riesgo": "<BAJO|MEDIO|ALTO|CRITICO>",
  "dominios_detectados": ["<agroquimicos|clima_extremo|seguridad_laboral|agua_contaminacion|zoonosis_salud_animal|bioseguridad_vegetal|seguridad_alimentaria|incendios_rurales|riego_suelo>"],
  "evidencia_suficiente": <true|false>,
  "justificacion": "<explicacion tecnica breve>",
  "riesgos_detectados": ["<riesgo 1>"],
  "informacion_faltante": ["<dato faltante>"],
  "preguntas_seguimiento": ["<pregunta 1>", "<pregunta 2>", "<pregunta 3>"],
  "debe_abstenerse": <true|false>,
  "marco_regulatorio_aplicable": ["<norma, guia o autoridad aplicable>"],
  "requiere_profesional": <true|false>
}}

REGLAS DE ABSTENCION:
- Falta informacion critica para estimar riesgo humano, animal, ambiental o alimentario.
- El usuario pide una accion potencialmente peligrosa sin datos locales suficientes.
- El nivel de riesgo es ALTO o CRITICO y no hay evidencia suficiente.
- Hay proximidad a zonas sensibles sin datos de distancia.
- Hay sospecha de zoonosis, enfermedad animal grave o plaga cuarentenaria sin diagnostico profesional.
- Hay trabajo con maquinaria, silos, electricidad o calor extremo sin condiciones de seguridad claras.
- Hay posible cosecha antes del intervalo de carencia, contaminacion por hongos/micotoxinas o almacenamiento inseguro.
- Hay quema, incendio rural, maquinaria caliente o viento/sequia sin indice/permisos/medidas de control.
- Hay riesgo de salinizacion, erosion, sobrefertilizacion o contaminacion de napas sin diagnostico de suelo/agua.
- La confianza < 65%.

Cuando te abstengas, indica que informacion falta y que accion segura inmediata corresponde: detener tarea, aislar animales, no mover material vegetal, no consumir/cosechar si hay riesgo alimentario, suspender quemas, proteger agua/suelo, llamar profesional o autoridad.
"""
EVIDENCE_TMPL = """
Eres un verificador de evidencia para un sistema de AI Safety agricola en America Latina.

Tu tarea: revisar si CADA afirmacion de seguridad esta respaldada por los fragmentos documentales o por principios preventivos claramente marcados como tales. Debes ser estricto con dosis, distancias, umbrales climaticos, diagnosticos sanitarios y normas.

PREGUNTA:
{question}

RESPUESTA DEL SISTEMA:
{answer}

FRAGMENTOS RECUPERADOS:
{context}

Devuelve EXCLUSIVAMENTE JSON valido:
{{
  "supported": <true|false>,
  "unsupported_claims": ["<afirmacion no respaldada>"],
  "hallucination_risk": "<NONE|LOW|MEDIUM|HIGH|CRITICAL>",
  "evidence_quality": "<LOW|MEDIUM|HIGH>",
  "cited_sources": ["<fuente>"],
  "explanation": "<explicacion breve>",
  "abstain_recommendation": <true|false>
}}

Recomienda abstencion si aparecen dosis, distancias, diagnosticos, autorizaciones o instrucciones tecnicas sin respaldo suficiente.
"""
FINAL_TMPL = """
Eres AgroSafety, un evaluador de seguridad agricola para America Latina.

Genera una evaluacion final basada en el historial completo y el contexto documental. Evalua riesgos de agroquimicos, clima extremo, seguridad laboral rural, agua/contaminacion, zoonosis/salud animal, bioseguridad vegetal, seguridad alimentaria, incendios rurales y riego/suelo segun corresponda.

HISTORIAL COMPLETO:
{all_info}

CONTEXTO DOCUMENTAL:
{context}

Incluye:
1. Recomendacion final: SEGURO / PRECAUCION / NO RECOMENDADO / ABSTENERSE.
2. Dominios de riesgo detectados.
3. Nivel de riesgo: BAJO | MEDIO | ALTO | CRITICO.
4. Justificacion tecnica con citas documentales cuando existan.
5. Acciones seguras inmediatas.
6. Evidencia usada.
7. Informacion faltante.
8. Advertencia si requiere agronomo, veterinario, autoridad sanitaria/fitosanitaria, autoridad ambiental, bomberos/emergencias o profesional habilitado.

No inventes datos. No des dosis, distancias o diagnosticos si no estan respaldados. Responde en espanol latinoamericano.
"""
# ── Global singletons ─────────────────────────────────────────────────────────
_retriever = None
_llm = None
_safety_chain = None
_evidence_chain = None
_conn = None
_cur = None
_memoria_log: list[dict] = []
_sessions: dict[int, "SessionState"] = {}

_DEFAULT_EVAL: dict = {
    "confianza": 30,
    "nivel_riesgo": "ALTO",
    "dominios_detectados": [],
    "evidencia_suficiente": False,
    "justificacion": "No se pudo evaluar con evidencia suficiente.",
    "riesgos_detectados": ["Recomendacion agricola potencialmente insegura o incompleta"],
    "informacion_faltante": ["Datos criticos de contexto local"],
    "preguntas_seguimiento": [
        "Que tarea agricola quiere realizar y en que ubicacion/pais/provincia?",
        "Hay personas, animales, agua, viviendas, escuelas o maquinaria involucradas?",
        "Que condiciones climaticas, producto/equipo o sintomas observa ahora?",
    ],
    "debe_abstenerse": True,
    "marco_regulatorio_aplicable": ["Principio preventivo de AI Safety agricola"],
    "requiere_profesional": True,
}
# ── Session state ─────────────────────────────────────────────────────────────
@dataclass
class SessionState:
    consulta_id: int
    historial_consulta: list = field(default_factory=list)
    historial_respuestas: list = field(default_factory=list)
    iteracion_actual: int = 1
    confianza_final: int = 0
    riesgo_final: str = "ALTO"
    evidencia_final: bool = False
    se_abstuvo_final: bool = True
    inicio: float = field(default_factory=time.time)
    completado: bool = False
    evaluacion_final: Optional[str] = None
    verificacion: Optional[dict] = None
    ultima_evaluacion: Optional[dict] = None
    umbral_confianza: int = 75
    max_iteraciones: int = 7


# ── Pydantic request/response models ──────────────────────────────────────────
class ConsultaRequest(BaseModel):
    consulta_inicial: str
    umbral_confianza: int = 75
    max_iteraciones: int = 7


class RespuestaRequest(BaseModel):
    respuesta: str


# ── DB helpers ────────────────────────────────────────────────────────────────
def _connect_db() -> None:
    global _conn, _cur
    try:
        _conn = psycopg2.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", 5432)),
            database=os.environ.get("DB_NAME", "agrosafety"),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASSWORD", ""),
        )
        _cur = _conn.cursor()
        logger.info("✅ PostgreSQL conectado")
        _ensure_schema()
    except Exception as exc:
        logger.warning("DB no disponible — modo fallback en memoria: %s", exc)
        _conn = None
        _cur = None


def _ensure_schema() -> None:
    """Crea las tablas si no existen. Idempotente: seguro correrlo en cada arranque."""
    if not (_cur and _conn):
        return
    statements = [
        """CREATE TABLE IF NOT EXISTS consultas (
               id               SERIAL PRIMARY KEY,
               consulta_inicial TEXT NOT NULL,
               created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
           )""",
        """CREATE TABLE IF NOT EXISTS respuestas (
               id              SERIAL PRIMARY KEY,
               consulta_id     INTEGER NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
               iteracion       INTEGER NOT NULL,
               preguntas       JSONB,
               respuesta       TEXT,
               confianza_antes INTEGER,
               riesgo_antes    TEXT,
               created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
           )""",
        """CREATE TABLE IF NOT EXISTS auditoria (
               id          SERIAL PRIMARY KEY,
               consulta_id INTEGER NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
               iteracion   INTEGER,
               accion      TEXT NOT NULL,
               detalle     JSONB,
               created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
           )""",
        """CREATE TABLE IF NOT EXISTS evaluaciones_finales (
               id                     SERIAL PRIMARY KEY,
               consulta_id            INTEGER NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
               evaluacion_final       TEXT,
               iteraciones_realizadas INTEGER,
               abstuvo                BOOLEAN NOT NULL DEFAULT FALSE,
               created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
           )""",
        """CREATE TABLE IF NOT EXISTS metricas_seguridad (
               id                   SERIAL PRIMARY KEY,
               consulta_id          INTEGER NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
               se_abstuvo           BOOLEAN,
               nivel_riesgo         TEXT,
               confianza_final      INTEGER,
               evidencia_suficiente BOOLEAN,
               iteraciones          INTEGER,
               duracion_seg         DOUBLE PRECISION,
               created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
           )""",
        "CREATE INDEX IF NOT EXISTS idx_respuestas_consulta_id ON respuestas(consulta_id)",
        "CREATE INDEX IF NOT EXISTS idx_auditoria_consulta_id ON auditoria(consulta_id)",
        "CREATE INDEX IF NOT EXISTS idx_evaluaciones_finales_consulta_id ON evaluaciones_finales(consulta_id)",
        "CREATE INDEX IF NOT EXISTS idx_metricas_seguridad_consulta_id ON metricas_seguridad(consulta_id)",
    ]
    try:
        for stmt in statements:
            _cur.execute(stmt)
        _conn.commit()
        logger.info("✅ Schema verificado/creado (consultas, respuestas, auditoria, evaluaciones_finales, metricas_seguridad)")
    except Exception as exc:
        try:
            _conn.rollback()
        except Exception:
            pass
        logger.error("No se pudo crear/verificar el schema: %s", exc)


def _db_exec(sql: str, params: tuple) -> None:
    if not (_cur and _conn):
        return
    try:
        _cur.execute(sql, params)
        _conn.commit()
    except Exception as exc:
        try:
            _conn.rollback()
        except Exception:
            pass
        logger.error("DB error: %s", exc)


def _db_column_exists(table_name: str, column_name: str) -> bool:
    if not (_cur and _conn):
        return False
    try:
        _cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
            LIMIT 1
            """,
            (table_name, column_name),
        )
        return _cur.fetchone() is not None
    except Exception as exc:
        try:
            _conn.rollback()
        except Exception:
            pass
        logger.error("DB schema check error: %s", exc)
        return False


def crear_consulta(texto: str) -> int:
    if _cur and _conn:
        try:
            _cur.execute(
                "INSERT INTO consultas (consulta_inicial) VALUES (%s) RETURNING id", (texto,)
            )
            cid = _cur.fetchone()[0]
            _conn.commit()
            return cid
        except Exception as exc:
            _conn.rollback()
            logger.error("crear_consulta error: %s", exc)
    cid = len(_memoria_log) + 1
    _memoria_log.append({"id": cid, "consulta_inicial": texto})
    return cid


def guardar_respuesta(cid, it, preguntas, respuesta, confianza, riesgo):
    _db_exec(
        """INSERT INTO respuestas
           (consulta_id, iteracion, preguntas, respuesta, confianza_antes, riesgo_antes)
           VALUES (%s,%s,%s,%s,%s,%s)""",
        (cid, it, json.dumps(preguntas, ensure_ascii=False), respuesta, confianza, riesgo),
    )


def registrar_auditoria(cid, it, accion, detalle):
    _db_exec(
        "INSERT INTO auditoria (consulta_id, iteracion, accion, detalle) VALUES (%s,%s,%s,%s)",
        (cid, it, accion, json.dumps(detalle, ensure_ascii=False)),
    )
    logger.info("AUDIT | consulta=%s iter=%s accion=%s", cid, it, accion)


def guardar_evaluacion_final(cid, texto, iteraciones, se_abstuvo=False):
    if _db_column_exists("evaluaciones_finales", "abstuvo"):
        _db_exec(
            """INSERT INTO evaluaciones_finales
               (consulta_id, evaluacion_final, iteraciones_realizadas, abstuvo)
               VALUES (%s,%s,%s,%s)""",
            (cid, texto, iteraciones, se_abstuvo),
        )
    else:
        _db_exec(
            """INSERT INTO evaluaciones_finales
               (consulta_id, evaluacion_final, iteraciones_realizadas)
               VALUES (%s,%s,%s)""",
            (cid, texto, iteraciones),
        )


def registrar_metrica(cid, se_abstuvo, riesgo, confianza, evidencia, iteraciones, duracion):
    _db_exec(
        """INSERT INTO metricas_seguridad
           (consulta_id, se_abstuvo, nivel_riesgo, confianza_final, evidencia_suficiente,
            iteraciones, duracion_seg)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (cid, se_abstuvo, riesgo, confianza, evidencia, iteraciones, duracion),
    )


# ── LangChain helpers ─────────────────────────────────────────────────────────
def _parse_json_safe(text: str, default: dict) -> dict:
    try:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
    except (json.JSONDecodeError, AttributeError):
        pass
    return default



SAFETY_DOMAINS = {
    "agroquimicos": {
        "label": "Agroquimicos y sustancias reguladas",
        "keywords": ["agroquim", "fitosanit", "herbicida", "insecticida", "fungicida", "glifosato", "paraquat", "atrazina", "clorpirifos", "fumigar", "pulverizar", "dosis", "envase", "epp"],
        "questions": ["Que producto, cultivo, dosis de etiqueta y metodo de aplicacion esta considerando?", "Cual es la velocidad del viento, temperatura y distancia a agua, viviendas o escuelas?", "Que EPP y manejo de envases/equipo tiene disponible?"],
    },
    "clima_extremo": {
        "label": "Clima y eventos extremos",
        "keywords": ["helada", "calor", "ola de calor", "sequia", "sequía", "granizo", "inundacion", "inundación", "tormenta", "viento", "sembrar", "cosechar", "alerta"],
        "questions": ["Que evento climatico afecta la tarea y cual es el pronostico/alerta local?", "Que cultivo o tarea quiere realizar: siembra, aplicacion, cosecha, riego o traslado?", "Cuales son temperatura, viento, humedad/suelo y nivel de anegamiento actuales?"],
    },
    "seguridad_laboral": {
        "label": "Seguridad laboral rural",
        "keywords": ["tractor", "maquinaria", "maquina", "fumigadora", "motosierra", "silo", "bomba", "riego", "electric", "electrocucion", "electrocución", "deshidrat", "golpe de calor"],
        "questions": ["Que maquina/equipo se usara y que tarea exacta se quiere hacer?", "Hay riesgo de energia electrica, partes moviles, altura, encierro en silo o calor extremo?", "Que EPP, bloqueo de energia, acompanante, agua/sombra y capacitacion hay disponibles?"],
    },
    "agua_contaminacion": {
        "label": "Agua y contaminacion",
        "keywords": ["pozo", "rio", "río", "arroyo", "canal", "laguna", "agua", "escuela", "vivienda", "casa", "lavado", "escorrentia", "escorrentía", "contamin"],
        "questions": ["A que distancia estan pozos, rios, canales, viviendas, escuelas o animales?", "Hay pendiente, lluvia reciente o riesgo de escorrentia hacia fuentes de agua?", "Como se lavaran equipos/envases y donde se dispondra el residuo?"],
    },
    "zoonosis_salud_animal": {
        "label": "Zoonosis y salud animal",
        "keywords": ["brucelosis", "leptospirosis", "rabia", "gripe aviar", "fiebre aftosa", "animal", "vaca", "cerdo", "ave", "gallina", "perro", "mordedura", "leche", "carne", "huevo", "veterinario"],
        "questions": ["Que especie animal, sintomas, cantidad de animales afectados y fecha de inicio observa?", "Hubo contacto con personas, mordeduras, abortos, muerte subita o signos neurologicos/respiratorios?", "Los animales/productos estan aislados y ya contacto a veterinario o autoridad sanitaria?"],
    },
    "seguridad_alimentaria": {
        "label": "Seguridad alimentaria",
        "keywords": ["carencia", "intervalo de carencia", "cosecha", "cosechar", "grano", "granos", "maiz", "maíz", "trigo", "soja", "micotoxina", "micotoxinas", "aflatoxina", "fumonisina", "hongo", "hongos", "moho", "humedad", "almacenamiento", "silo", "bolsa", "secado", "alimento", "consumo"],
        "questions": ["Que cultivo/alimento quiere cosechar o almacenar y que tratamiento reciente recibio?", "Se cumplio el intervalo de carencia de la etiqueta y cual es la fecha de ultima aplicacion?", "Cual es la humedad, presencia de hongos/moho y condicion de silo/bolsa/secado?"],
    },
    "incendios_rurales": {
        "label": "Incendios rurales",
        "keywords": ["incendio", "fuego", "quema", "quemar", "pastizal", "rastrojo", "sequía", "sequia", "viento", "maquinaria caliente", "chispa", "cortafuego", "bombero", "bomberos", "indice de riesgo", "riesgo de incendio"],
        "questions": ["Que tarea con fuego o maquinaria caliente quiere realizar y en que zona?", "Cuales son viento, sequia/humedad, temperatura, combustible seco e indice local de riesgo de incendio?", "Tiene permiso, cortafuegos, agua/equipo de control y contacto de autoridad local/bomberos?"],
    },
    "riego_suelo": {
        "label": "Riego y suelo",
        "keywords": ["riego", "suelo", "salinidad", "salinizacion", "salinización", "erosion", "erosión", "fertilizante", "fertilizacion", "fertilización", "urea", "nitrato", "fosforo", "fósforo", "napas", "napa", "lixiviacion", "lixiviación", "escorrentia", "escorrentía", "pendiente", "compactacion", "compactación"],
        "questions": ["Que cultivo, suelo, pendiente y sistema de riego/fertilizacion esta usando?", "Tiene analisis de suelo/agua, salinidad, dosis de fertilizante y pronostico de lluvia/riego?", "Hay napas, pozos, cursos de agua o signos de erosion/escorrentia cerca del lote?"],
    },
    "bioseguridad_vegetal": {
        "label": "Bioseguridad vegetal",
        "keywords": ["plaga", "enfermedad", "cuarenten", "mancha", "marchitez", "roya", "cancro", "mosca", "picudo", "material vegetal", "semilla", "plantin", "plantín", "trasladar", "senasa"],
        "questions": ["Que cultivo, sintomas, ubicacion y velocidad de avance observa?", "Movio semillas, frutos, plantas, suelo, herramientas o maquinaria desde/hacia otro lote?", "Puede aislar el material, evitar traslados, tomar fotos y consultar autoridad fitosanitaria?"],
    },
}

ALLOWED_RISKS = {"BAJO", "MEDIO", "ALTO", "CRITICO"}


def _infer_domains(text: str) -> list[str]:
    low = (text or "").lower()
    detected = []
    for key, cfg in SAFETY_DOMAINS.items():
        if any(k.lower() in low for k in cfg["keywords"]):
            detected.append(key)
    return detected or ["agroquimicos"]


def _fallback_questions(domains: list[str]) -> list[str]:
    questions = []
    for domain in domains:
        questions.extend(SAFETY_DOMAINS.get(domain, {}).get("questions", []))
    seen = []
    for q in questions:
        if q not in seen:
            seen.append(q)
    return seen[:3] or _DEFAULT_EVAL["preguntas_seguimiento"]


def _norm_text(text: str) -> str:
    normalized = (text or "").lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _question_tokens(text: str) -> set[str]:
    stopwords = {
        "a", "al", "algo", "con", "cual", "cuales", "cuando", "de", "del", "el",
        "en", "es", "estan", "esta", "fue", "ha", "hay", "la", "las", "lo", "los",
        "o", "para", "por", "que", "se", "si", "su", "sus", "te", "tiene", "tus",
        "un", "una", "y", "ya",
    }
    return {w for w in _norm_text(text).split() if len(w) > 3 and w not in stopwords}


def _is_similar_question(question: str, previous_questions: list[str]) -> bool:
    current = _question_tokens(question)
    if not current:
        return True
    for previous in previous_questions:
        prev = _question_tokens(previous)
        if not prev:
            continue
        overlap = len(current & prev) / max(1, min(len(current), len(prev)))
        if overlap >= 0.55:
            return True
    return False


def _answer_seems_to_cover_question(question: str, answers_text: str) -> bool:
    q = _norm_text(question)
    a = _norm_text(answers_text)
    if not a:
        return False

    coverage_groups = (
        (("vacun", "vacuna"), ("vacun",)),
        (("sintoma", "sintomas", "enfermedad", "inusual"), ("sintoma", "enfermedad", "sanas", "sano", "sana")),
        (("veterinario", "profesional", "autoridad"), ("veterinario", "profesional", "autoridad")),
        (("ubicacion", "zona", "localidad", "provincia", "pais"), ("suardi", "morteros", "san guillermo", "cordoba", "santa fe")),
        (("contacto", "aislado", "aislar"), ("aislad", "contact", "separad")),
        (("alimentacion", "alimento"), ("alimento", "alimentacion", "pasto", "balanceado", "silo")),
    )
    for q_terms, a_terms in coverage_groups:
        if any(term in q for term in q_terms) and any(term in a for term in a_terms):
            return True
    return False


def _filter_followup_questions(
    questions: list[str],
    session: Optional[SessionState],
    domains: list[str],
    allow_fallback: bool = True,
) -> list[str]:
    if session is None:
        previous_questions = []
        answers_text = ""
    else:
        previous_questions = [
            q
            for item in session.historial_respuestas
            for q in item.get("preguntas", [])
        ]
        answers_text = "\n".join(item.get("respuesta", "") for item in session.historial_respuestas)

    filtered = []
    for question in questions:
        if _is_similar_question(question, previous_questions + filtered):
            continue
        if _answer_seems_to_cover_question(question, answers_text):
            continue
        filtered.append(question)

    if len(filtered) >= 3 or not allow_fallback:
        return filtered[:3]

    for question in _fallback_questions(domains):
        if _is_similar_question(question, previous_questions + filtered):
            continue
        if _answer_seems_to_cover_question(question, answers_text):
            continue
        filtered.append(question)
        if len(filtered) == 3:
            break

    # Último recurso: si el filtro anti-repetidos dejó la lista vacía
    # (todas las preguntas de dominio ya se hicieron antes), nunca
    # dejamos al usuario sin nada que responder mientras falte evidencia.
    if not filtered:
        filtered.append(
            "Podes darnos mas detalles especificos de tu situacion (ubicacion, "
            "producto/tarea exacta, cantidades, fechas) que todavia no hayas mencionado?"
        )

    return filtered


def _normalize_eval(ev: dict, history_text: str, session: Optional[SessionState] = None) -> dict:
    if not isinstance(ev, dict):
        ev = _DEFAULT_EVAL.copy()
    domains = ev.get("dominios_detectados") or _infer_domains(history_text)
    if isinstance(domains, str):
        domains = [domains]
    domains = [d for d in domains if d in SAFETY_DOMAINS] or _infer_domains(history_text)
    ev["dominios_detectados"] = domains

    risk = str(ev.get("nivel_riesgo", "ALTO")).upper().replace("CRÍTICO", "CRITICO")
    ev["nivel_riesgo"] = risk if risk in ALLOWED_RISKS else "ALTO"

    try:
        ev["confianza"] = max(0, min(100, int(ev.get("confianza", 30))))
    except Exception:
        ev["confianza"] = 30

    for field_name in ("riesgos_detectados", "informacion_faltante", "preguntas_seguimiento", "marco_regulatorio_aplicable"):
        value = ev.get(field_name)
        if isinstance(value, str):
            ev[field_name] = [value]
        elif not isinstance(value, list):
            ev[field_name] = []

    needs_more_evidence = not ev.get("evidencia_suficiente", False)
    if not ev["preguntas_seguimiento"] and needs_more_evidence:
        ev["preguntas_seguimiento"] = _fallback_questions(domains)
    ev["preguntas_seguimiento"] = _filter_followup_questions(
        ev["preguntas_seguimiento"], session, domains, allow_fallback=needs_more_evidence
    )
    if not ev["informacion_faltante"]:
        ev["informacion_faltante"] = ["Contexto local suficiente para evaluar la accion con seguridad"]
    if not ev["riesgos_detectados"]:
        ev["riesgos_detectados"] = ["Riesgo agricola no caracterizado completamente"]

    if ev["nivel_riesgo"] in {"ALTO", "CRITICO"} and not ev.get("evidencia_suficiente", False):
        ev["debe_abstenerse"] = True
    if ev["confianza"] < 65:
        ev["debe_abstenerse"] = True
    ev["requiere_profesional"] = bool(ev.get("requiere_profesional", ev["nivel_riesgo"] in {"ALTO", "CRITICO"}))
    return ev


# ── Session processing ────────────────────────────────────────────────────────
def _run_iteration(session: SessionState) -> dict:
    """Run one safety evaluation iteration and return the parsed result."""
    historial_str = "\n".join(f"- {s}" for s in session.historial_consulta)
    try:
        resp = _safety_chain.invoke(historial_str)
        ev = _normalize_eval(_parse_json_safe(resp.content, _DEFAULT_EVAL.copy()), historial_str, session)
    except Exception as exc:
        logger.error("Safety chain error: %s", exc)
        ev = _normalize_eval(_DEFAULT_EVAL.copy(), historial_str, session)

    session.confianza_final = ev.get("confianza", 0)
    session.riesgo_final = ev.get("nivel_riesgo", "ALTO")
    session.evidencia_final = ev.get("evidencia_suficiente", False)
    session.se_abstuvo_final = ev.get("debe_abstenerse", True)
    session.ultima_evaluacion = ev

    registrar_auditoria(
        session.consulta_id,
        session.iteracion_actual,
        "EVALUACION_ITERACION",
        {k: ev.get(k) for k in ("confianza", "nivel_riesgo", "dominios_detectados", "evidencia_suficiente", "debe_abstenerse")},
    )

    should_complete = (
        (
            session.confianza_final >= session.umbral_confianza
            and session.evidencia_final
            and not session.se_abstuvo_final
        )
        or session.iteracion_actual >= session.max_iteraciones
    )
    if should_complete:
        _finalize(session)

    return ev


def _finalize(session: SessionState) -> None:
    """Generate the final evaluation, run the evidence checker, and persist everything."""
    all_info = "\n".join(f"- {s}" for s in session.historial_consulta)
    final_chain = (
        {"all_info": RunnablePassthrough(), "context": _retriever}
        | ChatPromptTemplate.from_template(FINAL_TMPL)
        | _llm
    )
    try:
        eval_text = final_chain.invoke(all_info).content
    except Exception as exc:
        logger.error("Final eval error: %s", exc)
        eval_text = "No se pudo generar la evaluación final."

    # Evidence verification
    docs = _retriever.invoke("\n".join(session.historial_consulta[-3:]))
    contexto = "\n\n".join(
        f"[Fuente: {d.metadata.get('source_file','N/A')} | Pág: {d.metadata.get('page','N/A')}]\n{d.page_content}"
        for d in docs
    )
    default_fail = {
        "abstain_recommendation": True,
        "hallucination_risk": "HIGH",
        "supported": False,
        "unsupported_claims": [],
        "cited_sources": [],
        "evidence_quality": "LOW",
        "explanation": "No se pudo verificar.",
    }
    try:
        ev_resp = _evidence_chain.invoke(
            {
                "question": "\n".join(session.historial_consulta),
                "answer": eval_text,
                "context": contexto,
            }
        )
        verificacion = _parse_json_safe(ev_resp.content, default_fail)
    except Exception as exc:
        logger.error("Evidence checker error: %s", exc)
        verificacion = default_fail

    if verificacion.get("abstain_recommendation", False):
        session.se_abstuvo_final = True
        logger.warning(
            "Evidence checker recomienda abstención. hallucination_risk=%s",
            verificacion.get("hallucination_risk"),
        )

    duracion = time.time() - session.inicio
    guardar_evaluacion_final(
        session.consulta_id, eval_text, session.iteracion_actual - 1, session.se_abstuvo_final
    )
    registrar_metrica(
        session.consulta_id,
        session.se_abstuvo_final,
        session.riesgo_final,
        session.confianza_final,
        session.evidencia_final,
        session.iteracion_actual - 1,
        duracion,
    )
    registrar_auditoria(
        session.consulta_id,
        session.iteracion_actual,
        "EVALUACION_FINAL",
        {
            "evaluacion_final": eval_text,
            "se_abstuvo": session.se_abstuvo_final,
            "duracion_seg": round(duracion, 2),
        },
    )

    session.evaluacion_final = eval_text
    session.verificacion = verificacion
    session.completado = True




def _pdf_text(value) -> str:
    """Return a safe, compact string for PDF paragraphs."""
    text = "" if value is None else str(value)
    return html.escape(text).replace("\n", "<br/>")


def _join_items(items) -> str:
    if not items:
        return "No registrado"
    if isinstance(items, str):
        return items
    return ", ".join(str(x) for x in items)


def _build_pdf_bytes(session: SessionState) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError as exc:
        raise HTTPException(
            500,
            "Falta la dependencia reportlab. Instalar con: pip install reportlab",
        ) from exc

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"AgroSafety diagnostico {session.consulta_id}",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10, textColor=colors.HexColor("#475569")))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontSize=12, leading=15, spaceBefore=10, spaceAfter=5, textColor=colors.HexColor("#14532d")))
    styles.add(ParagraphStyle(name="Box", parent=styles["BodyText"], fontSize=9, leading=12, backColor=colors.HexColor("#f8fafc"), borderColor=colors.HexColor("#e2e8f0"), borderWidth=0.5, borderPadding=6, spaceAfter=8))

    ev = session.ultima_evaluacion or {}
    verif = session.verificacion or {}
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    story = []
    story.append(Paragraph("AgroSafety - Diagnostico de Seguridad Agricola", styles["Title"]))
    story.append(Paragraph("Reporte generado automaticamente por la capa de AI Safety agricola.", styles["Small"]))
    story.append(Spacer(1, 8))

    summary_data = [
        [Paragraph("Consulta ID", styles["Small"]), Paragraph(str(session.consulta_id), styles["Small"])],
        [Paragraph("Fecha", styles["Small"]), Paragraph(generated_at, styles["Small"])],
        [Paragraph("Riesgo", styles["Small"]), Paragraph(_pdf_text(ev.get("nivel_riesgo", session.riesgo_final)), styles["Small"])],
        [Paragraph("Confianza", styles["Small"]), Paragraph(f"{ev.get('confianza', session.confianza_final)}%", styles["Small"])],
        [Paragraph("Dominios", styles["Small"]), Paragraph(_pdf_text(_join_items(ev.get("dominios_detectados", []))), styles["Small"])],
        [Paragraph("Abstencion", styles["Small"]), Paragraph("Si" if session.se_abstuvo_final else "No", styles["Small"])],
        [Paragraph("Requiere profesional", styles["Small"]), Paragraph("Si" if ev.get("requiere_profesional", True) else "No", styles["Small"])],
    ]
    table = Table(summary_data, colWidths=[4.2 * cm, 11.2 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#dcfce7")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table)

    def section(title: str, body):
        story.append(Paragraph(title, styles["Section"]))
        if isinstance(body, list):
            if body:
                for item in body:
                    story.append(Paragraph(f"- {_pdf_text(item)}", styles["BodyText"]))
            else:
                story.append(Paragraph("No registrado", styles["BodyText"]))
        else:
            story.append(Paragraph(_pdf_text(body or "No registrado"), styles["Box"]))

    section("Consulta e historial", session.historial_consulta)
    section("Justificacion tecnica", ev.get("justificacion", ""))
    section("Riesgos detectados", ev.get("riesgos_detectados", []))
    section("Informacion faltante", ev.get("informacion_faltante", []))
    section("Marco o autoridad aplicable", ev.get("marco_regulatorio_aplicable", []))
    section("Evaluacion final", session.evaluacion_final or "La consulta aun no tiene evaluacion final. Complete el flujo de preguntas para generar el diagnostico final.")

    if verif:
        section("Verificacion de evidencia", verif.get("explanation", ""))
        section("Fuentes citadas", verif.get("cited_sources", []))
        section("Afirmaciones sin respaldo", verif.get("unsupported_claims", []))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Aviso: AgroSafety no reemplaza a profesionales habilitados ni autoridades sanitarias, fitosanitarias, ambientales o de emergencia.", styles["Small"]))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def _to_response(session: SessionState) -> dict:
    ev = session.ultima_evaluacion or {}
    return {
        "consulta_id": session.consulta_id,
        "iteracion": session.iteracion_actual,
        "max_iteraciones": session.max_iteraciones,
        "completado": session.completado,
        "confianza": ev.get("confianza", session.confianza_final),
        "nivel_riesgo": ev.get("nivel_riesgo", session.riesgo_final),
        "evidencia_suficiente": ev.get("evidencia_suficiente", session.evidencia_final),
        "dominios_detectados": ev.get("dominios_detectados", []),
        "justificacion": ev.get("justificacion", ""),
        "riesgos_detectados": ev.get("riesgos_detectados", []),
        "informacion_faltante": ev.get("informacion_faltante", []),
        "preguntas_seguimiento": (
            ev.get("preguntas_seguimiento", []) if not session.completado else []
        ),
        "debe_abstenerse": ev.get("debe_abstenerse", session.se_abstuvo_final),
        "marco_regulatorio_aplicable": ev.get("marco_regulatorio_aplicable", []),
        "requiere_profesional": ev.get("requiere_profesional", True),
        "evaluacion_final": session.evaluacion_final,
        "verificacion_evidencia": session.verificacion,
        "se_abstuvo_final": session.se_abstuvo_final,
    }


# ── Startup ───────────────────────────────────────────────────────────────────
def _sync_init() -> None:
    global _retriever, _llm, _safety_chain, _evidence_chain

    _connect_db()

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        logger.error("GOOGLE_API_KEY no está definida. La API no podrá responder consultas.")
        return

    # Vector store — reuse existing collection si ya está indexada.
    # OJO: si CHROMA_DIR no vive en un disco persistente, esto arranca
    # en 0 en cada deploy/restart y vuelve a indexar todo de nuevo.
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    persist_dir = os.environ.get("CHROMA_DIR", "db_agro_docs")
    vector_store = Chroma(
        collection_name="agro_epof_collection_gemini",
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )
    existing_count = vector_store._collection.count()
    force_reindex = os.environ.get("FORCE_REINDEX", "").lower() in ("1", "true", "yes")

    if existing_count > 0 and not force_reindex:
        logger.info("Usando vector store existente (%d chunks). Salteando reindexado.", existing_count)
    else:
        pdf_folder = os.environ.get("PDF_FOLDER", "data")
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200, chunk_overlap=200, add_start_index=True
        )
        batch_size = 100  # chunks por llamada a add_documents (cuota free tier: 100 req/min)
        pending: list = []
        total_pages = 0
        total_chunks = 0

        def _extract_retry_delay(exc: Exception, default: float = 30.0) -> float:
            match = re.search(r"retryDelay['\"]?\s*:\s*['\"](\d+(?:\.\d+)?)s", str(exc))
            return float(match.group(1)) if match else default

        def _flush(pending_batch: list, max_retries: int = 5) -> bool:
            """Intenta indexar un batch. Devuelve True si tuvo éxito.
            Ante 429/RESOURCE_EXHAUSTED, espera el retryDelay que sugiere
            Gemini y reintenta el MISMO batch, en vez de descartarlo."""
            nonlocal total_chunks
            if not pending_batch:
                return True
            for attempt in range(1, max_retries + 1):
                try:
                    vector_store.add_documents(pending_batch)
                    total_chunks += len(pending_batch)
                    logger.info("Indexados %d chunks (acumulado)", total_chunks)
                    return True
                except Exception as exc:
                    is_quota = "RESOURCE_EXHAUSTED" in str(exc) or "429" in str(exc)
                    if is_quota and attempt < max_retries:
                        delay = _extract_retry_delay(exc)
                        logger.warning(
                            "Cuota de embeddings agotada (intento %d/%d). Esperando %.0fs...",
                            attempt, max_retries, delay,
                        )
                        time.sleep(delay)
                        continue
                    logger.warning(
                        "No se pudo indexar un batch de %d chunks tras %d intentos: %s",
                        len(pending_batch), attempt, exc,
                    )
                    return False
            return False

        if pathlib.Path(pdf_folder).is_dir():
            pdf_files = sorted(f for f in os.listdir(pdf_folder) if f.endswith(".pdf"))
            for fname in pdf_files:
                try:
                    loader = PyPDFLoader(os.path.join(pdf_folder, fname))
                    docs = loader.load()  # solo las páginas de ESTE archivo en memoria
                    for d in docs:
                        d.metadata["source_file"] = fname
                    total_pages += len(docs)

                    file_splits = splitter.split_documents(docs)
                    del docs  # liberar páginas crudas ni bien tenemos los chunks

                    pending.extend(file_splits)
                    del file_splits
                except Exception as exc:
                    logger.warning("No se pudo cargar %s: %s", fname, exc)
                    continue

                # El flush va AFUERA del try de carga: si falla por cuota,
                # no se pierde el batch, y no queremos que un error de
                # embeddings se confunda con un PDF corrupto.
                while len(pending) >= batch_size:
                    batch = pending[:batch_size]
                    if _flush(batch):
                        pending = pending[batch_size:]
                    else:
                        # Se agotaron los reintentos: cortamos la indexación
                        # acá en vez de seguir machacando la API en cada
                        # archivo siguiente.
                        logger.error("Indexación interrumpida por errores persistentes de cuota/API.")
                        pending = []
                        break

                logger.info("Procesado %s (%d páginas acumuladas)", fname, total_pages)

            _flush(pending)  # lo que quedó sin llegar a completar un batch

        logger.info(
            "Documentos cargados: %d páginas → %d chunks indexados",
            total_pages, total_chunks,
        )

    _retriever = vector_store.as_retriever(
        search_type="mmr", search_kwargs={"k": 8, "fetch_k": 20}
    )
    _llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", temperature=0.2)
    _safety_chain = (
        {"context": _retriever, "agro_history": RunnablePassthrough()}
        | ChatPromptTemplate.from_template(SAFETY_TMPL)
        | ChatGoogleGenerativeAI(model="gemini-3.6-flash", temperature=0.0)
    )
    _evidence_chain = (
        ChatPromptTemplate.from_template(EVIDENCE_TMPL)
        | ChatGoogleGenerativeAI(model="gemini-3.6-flash", temperature=0.0)
    )
    logger.info("✅ AgroSafety API lista")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lanza la inicialización en un hilo secundario para NO bloquear el event loop.
    # Uvicorn abrirá el puerto inmediatamente.
    asyncio.create_task(asyncio.to_thread(_sync_init))
    
    yield  # La app inicia y Render detecta el puerto abierto de inmediato
    
    if _conn:
        _conn.close()
    logger.info("AgroSafety API apagada")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="AgroSafety API",
    description="Sistema de evaluacion integral de seguridad agricola con AI Safety",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = pathlib.Path(__file__).parent / "frontend"
if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    idx = FRONTEND_DIR / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    return {"status": "AgroSafety API running", "frontend": "frontend/index.html not found"}


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "db_connected": _conn is not None,
        "ai_ready": _retriever is not None,
        "safety_domains": [cfg["label"] for cfg in SAFETY_DOMAINS.values()],
    }


@app.post("/api/consulta")
async def iniciar_consulta(req: ConsultaRequest):
    if _retriever is None or _safety_chain is None:
        raise HTTPException(
            503, "Sistema no inicializado. Verificar GOOGLE_API_KEY y reiniciar el servidor."
        )
    consulta_id = crear_consulta(req.consulta_inicial)
    session = SessionState(
        consulta_id=consulta_id,
        umbral_confianza=req.umbral_confianza,
        max_iteraciones=req.max_iteraciones,
    )
    session.historial_consulta.append(f"CONSULTA INICIAL: {req.consulta_inicial}")
    registrar_auditoria(consulta_id, 0, "CONSULTA_INICIAL", {"consulta": req.consulta_inicial})
    _run_iteration(session)
    _sessions[consulta_id] = session
    return _to_response(session)


@app.post("/api/consulta/{consulta_id}/responder")
async def responder_consulta(consulta_id: int, req: RespuestaRequest):
    session = _sessions.get(consulta_id)
    if session is None:
        raise HTTPException(404, f"Consulta {consulta_id} no encontrada.")
    if session.completado:
        raise HTTPException(400, "La consulta ya está completada.")

    preguntas = (session.ultima_evaluacion or {}).get("preguntas_seguimiento", [])
    guardar_respuesta(
        consulta_id, session.iteracion_actual, preguntas,
        req.respuesta, session.confianza_final, session.riesgo_final,
    )
    registrar_auditoria(
        consulta_id, session.iteracion_actual, "RESPUESTA_USUARIO", {"respuesta": req.respuesta}
    )

    if req.respuesta.strip():
        session.historial_consulta.append(
            f"Respuesta iteración {session.iteracion_actual}: {req.respuesta}"
        )
        session.historial_respuestas.append(
            {"iteracion": session.iteracion_actual, "preguntas": preguntas, "respuesta": req.respuesta}
        )

    session.iteracion_actual += 1
    _run_iteration(session)
    return _to_response(session)



@app.get("/api/consulta/{consulta_id}/pdf")
async def descargar_pdf_consulta(consulta_id: int):
    session = _sessions.get(consulta_id)
    if session is None:
        raise HTTPException(404, f"Consulta {consulta_id} no encontrada.")
    pdf_bytes = _build_pdf_bytes(session)
    filename = f"agrosafety_diagnostico_{consulta_id}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

@app.get("/api/consulta/{consulta_id}")
async def get_consulta(consulta_id: int):
    session = _sessions.get(consulta_id)
    if session is None:
        raise HTTPException(404, f"Consulta {consulta_id} no encontrada.")
    return _to_response(session)
