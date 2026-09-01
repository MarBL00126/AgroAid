"""
AgroSafety API
==============

Hackathon Global South AI Safety 2026 | Track Latinoamérica

Backend FastAPI para el sistema de evaluación de seguridad agrícola.

Convierte el flujo interactivo del notebook en una API REST con sesiones,
para que cualquier frontend pueda consumirlo.

Uso:

    pip install fastapi "uvicorn[standard]" slowapi

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

import hashlib
import json
import html
import logging
import os
import pathlib
import re
import time
import asyncio

from datetime import datetime
from io import BytesIO
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi

from pydantic import BaseModel

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from routers.auth import router as auth_router
from routers.admin import router as admin_router
from routers.keys import router as keys_router
from routers.whatsapp import router as whatsapp_router
from routers.voz import router as voz_router
from routers.imagen import router as imagen_router
from routers.dashboard import router as dashboard_router

from routers.senasa import router as senasa_router
from core.clima import get_clima as _fetch_clima
from core.senasa import buscar_fitosanitario
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.chroma import get_retriever, get_vector_store
from core.database import (
    close_pool,
    db_exec,
    db_fetch_one,
    db_fetch_val,
    ensure_schema,
    get_conn,
    get_tenant_id,
    init_pool,
    is_pool_initialized,
)
from core.deps import require_any


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


# ── Prompt templates ──────────────────────────────────────────────────────────

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

8. Incendios rurales: quema de pastizales, viento, sequia, combustible seco, maquinaria caliente, cortafuegos y abstencion ante indice de riesgo alto.

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

_llm = None
_evidence_chain = None

_db_ready = False
_sessions: dict[int, "SessionState"] = {}


_DEFAULT_EVAL: dict = {
    "confianza": 30,
    "nivel_riesgo": "ALTO",
    "dominios_detectados": [],
    "evidencia_suficiente": False,
    "justificacion": "No se pudo evaluar con evidencia suficiente.",
    "riesgos_detectados": [
        "Recomendacion agricola potencialmente insegura o incompleta"
    ],
    "informacion_faltante": [
        "Datos criticos de contexto local"
    ],
    "preguntas_seguimiento": [
        "Que tarea agricola quiere realizar y en que ubicacion/pais/provincia?",
        "Hay personas, animales, agua, viviendas, escuelas o maquinaria involucradas?",
        "Que condiciones climaticas, producto/equipo o sintomas observa ahora?",
    ],
    "debe_abstenerse": True,
    "marco_regulatorio_aplicable": [
        "Principio preventivo de AI Safety agricola"
    ],
    "requiere_profesional": True,
}


# ── Session state ─────────────────────────────────────────────────────────────

@dataclass
class SessionState:

    consulta_id: int
    tenant_slug: str

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

    umbral_confianza: int = 80
    max_iteraciones: int = 5


# ── Pydantic request/response models ──────────────────────────────────────────

class ConsultaRequest(BaseModel):

    consulta_inicial: str

    umbral_confianza: int = 80

    max_iteraciones: int = 5

    tenant_slug: str = "default"
    lat: float | None = None
    lon: float | None = None


class RespuestaRequest(BaseModel):

    respuesta: str


# ── DB helpers ────────────────────────────────────────────────────────────────

def _connect_db() -> None:

    global _db_ready

    try:

        init_pool()

        _ensure_schema()

        _db_ready = True

        logger.info("PostgreSQL conectado")

    except Exception as exc:

        _db_ready = False

        logger.error(
            "DB no disponible: %s",
            exc,
        )


def _ensure_schema() -> None:

    try:

        ensure_schema()

        logger.info(
            "Schema verificado/creado"
        )

    except Exception as exc:

        logger.error(
            "No se pudo crear/verificar el schema: %s",
            exc,
        )
        raise


def _db_exec(sql: str, params: tuple) -> None:

    try:

        db_exec(sql, params)

    except Exception as exc:

        logger.error(
            "DB error: %s",
            exc,
        )
        raise


def _db_column_exists(table_name: str, column_name: str) -> bool:

    try:

        return bool(
            db_fetch_val(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = %s
              AND column_name = %s
            LIMIT 1
            """,
                (table_name, column_name),
            )
        )

    except Exception as exc:

        logger.error(
            "DB schema check error: %s",
            exc,
        )

        return False


def crear_consulta(
    texto: str,
    tenant_slug: str = "default",
) -> int:

    try:

        tenant_id = get_tenant_id(
            tenant_slug
        )

        with get_conn() as conn:

            try:

                with conn.cursor() as cur:

                    cur.execute(
                """
                INSERT INTO consultas (tenant_id, consulta_inicial)
                VALUES (%s, %s)
                RETURNING id
                """,
                        (
                            tenant_id,
                            texto,
                        ),
                    )

                    cid = cur.fetchone()[0]

                conn.commit()

                return cid

            except Exception:

                conn.rollback()
                raise

    except Exception as exc:

        logger.error(
            "crear_consulta error: %s",
            exc,
        )

        raise HTTPException(
            status_code=503,
            detail="Base de datos no disponible.",
        ) from exc


def guardar_respuesta(
    cid,
    it,
    preguntas,
    respuesta,
    confianza,
    riesgo,
):

    _db_exec(
        """
        INSERT INTO respuestas
        (
            tenant_id,
            consulta_id,
            iteracion,
            preguntas,
            respuesta,
            confianza_antes,
            riesgo_antes
        )
        VALUES (
            (SELECT tenant_id FROM consultas WHERE id = %s),
            %s,%s,%s,%s,%s,%s
        )
        """,
        (
            cid,
            cid,
            it,
            json.dumps(
                preguntas,
                ensure_ascii=False,
            ),
            respuesta,
            confianza,
            riesgo,
        ),
    )


def registrar_auditoria(
    cid,
    it,
    accion,
    detalle,
):
    ultima = db_fetch_one(
        """
        SELECT entry_hash FROM auditoria
        WHERE consulta_id = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (cid,),
    )
    prev_hash=ultima["entry_hash"] if ultima else None
    detalle_json = json.dumps( detalle, ensure_ascii=False, sort_keys=True, )
    hash_data = json.dumps( { "consulta_id": cid, "iteracion": it, "accion": accion, "detalle": detalle_json, "prev_hash": prev_hash, }, ensure_ascii=False, sort_keys=True, )
    entry_hash = hashlib.sha256( hash_data.encode("utf-8") ).hexdigest()
    _db_exec(
        """
        INSERT INTO auditoria
        (
            tenant_id,
            consulta_id,
            iteracion,
            accion,
            detalle,
            entry_hash, 
            prev_hash
        )
        VALUES (
            (SELECT tenant_id FROM consultas WHERE id = %s),
            %s,%s,%s,%s,%s,%s
        )
        """,
        (
            cid,
            cid,
            it,
            accion,
            detalle_json,
            entry_hash,
            prev_hash,
        ),
    )

    logger.info(
        "AUDIT | consulta=%s iter=%s accion=%s",
        cid,
        it,
        accion,
        prev_hash
    )


def guardar_evaluacion_final(
    cid,
    texto,
    iteraciones,
    se_abstuvo=False,
):

    if _db_column_exists(
        "evaluaciones_finales",
        "abstuvo",
    ):

        _db_exec(
            """
            INSERT INTO evaluaciones_finales
            (
                tenant_id,
                consulta_id,
                evaluacion_final,
                iteraciones_realizadas,
                abstuvo
            )
            VALUES (
                (SELECT tenant_id FROM consultas WHERE id = %s),
                %s,%s,%s,%s
            )
            """,
            (
                cid,
                cid,
                texto,
                iteraciones,
                se_abstuvo,
            ),
        )

    else:

        _db_exec(
            """
            INSERT INTO evaluaciones_finales
            (
                tenant_id,
                consulta_id,
                evaluacion_final,
                iteraciones_realizadas
            )
            VALUES (
                (SELECT tenant_id FROM consultas WHERE id = %s),
                %s,%s,%s
            )
            """,
            (
                cid,
                cid,
                texto,
                iteraciones,
            ),
        )


def registrar_metrica(
    cid,
    se_abstuvo,
    riesgo,
    confianza,
    evidencia,
    iteraciones,
    duracion,
):

    _db_exec(
        """
        INSERT INTO metricas_seguridad
        (
            tenant_id,
            consulta_id,
            se_abstuvo,
            nivel_riesgo,
            confianza_final,
            evidencia_suficiente,
            iteraciones,
            duracion_seg
        )
        VALUES (
            (SELECT tenant_id FROM consultas WHERE id = %s),
            %s,%s,%s,%s,%s,%s,%s
        )
        """,
        (
            cid,
            cid,
            se_abstuvo,
            riesgo,
            confianza,
            evidencia,
            iteraciones,
            duracion,
        ),
    )


# ── LangChain helpers ─────────────────────────────────────────────────────────

def _extract_text(content) -> str:

    if isinstance(content, str):
        return content

    if isinstance(content, list):

        parts = []

        for item in content:

            if isinstance(item, str):

                parts.append(item)

            elif isinstance(item, dict):

                text = item.get("text")

                if text:
                    parts.append(str(text))

        return "\n".join(parts)

    return "" if content is None else str(content)


def _parse_json_safe(
    text: str,
    default: dict,
) -> dict:

    try:

        match = re.search(
            r"\{.*\}",
            text,
            re.DOTALL,
        )

        if match:

            return json.loads(
                match.group(0)
            )

    except (
        json.JSONDecodeError,
        AttributeError,
    ):
        pass

    return default


# ── Safety domains ────────────────────────────────────────────────────────────

SAFETY_DOMAINS = {

    "agroquimicos": {
        "label": "Agroquimicos y sustancias reguladas",

        "keywords": [
            "agroquim",
            "fitosanit",
            "herbicida",
            "insecticida",
            "fungicida",
            "glifosato",
            "paraquat",
            "atrazina",
            "clorpirifos",
            "fumigar",
            "pulverizar",
            "dosis",
            "envase",
            "epp",
        ],

        "questions": [
            "Que producto, cultivo, dosis de etiqueta y metodo de aplicacion esta considerando?",
            "Cual es la velocidad del viento, temperatura y distancia a agua, viviendas o escuelas?",
            "Que EPP y manejo de envases/equipo tiene disponible?",
        ],
    },

    "clima_extremo": {

        "label": "Clima y eventos extremos",

        "keywords": [
            "helada",
            "calor",
            "ola de calor",
            "sequia",
            "sequía",
            "granizo",
            "inundacion",
            "inundación",
            "tormenta",
            "viento",
            "sembrar",
            "cosechar",
            "alerta",
        ],

        "questions": [
            "Que evento climatico afecta la tarea y cual es el pronostico/alerta local?",
            "Que cultivo o tarea quiere realizar: siembra, aplicacion, cosecha, riego o traslado?",
            "Cuales son temperatura, viento, humedad/suelo y nivel de anegamiento actuales?",
        ],
    },

    "seguridad_laboral": {

        "label": "Seguridad laboral rural",

        "keywords": [
            "tractor",
            "maquinaria",
            "maquina",
            "fumigadora",
            "motosierra",
            "silo",
            "bomba",
            "riego",
            "electric",
            "electrocucion",
            "electrocución",
            "deshidrat",
            "golpe de calor",
        ],

        "questions": [
            "Que maquina/equipo se usara y que tarea exacta se quiere hacer?",
            "Hay riesgo de energia electrica, partes moviles, altura, encierro en silo o calor extremo?",
            "Que EPP, bloqueo de energia, acompanante, agua/sombra y capacitacion hay disponibles?",
        ],
    },

    "agua_contaminacion": {

        "label": "Agua y contaminacion",

        "keywords": [
            "pozo",
            "rio",
            "río",
            "arroyo",
            "canal",
            "laguna",
            "agua",
            "escuela",
            "vivienda",
            "casa",
            "lavado",
            "escorrentia",
            "escorrentía",
            "contamin",
        ],

        "questions": [
            "A que distancia estan pozos, rios, canales, viviendas, escuelas o animales?",
            "Hay pendiente, lluvia reciente o riesgo de escorrentia hacia fuentes de agua?",
            "Como se lavaran equipos/envases y donde se dispondra el residuo?",
        ],
    },

    "zoonosis_salud_animal": {

        "label": "Zoonosis y salud animal",

        "keywords": [
            "brucelosis",
            "leptospirosis",
            "rabia",
            "gripe aviar",
            "fiebre aftosa",
            "animal",
            "vaca",
            "cerdo",
            "ave",
            "gallina",
            "perro",
            "mordedura",
            "leche",
            "carne",
            "huevo",
            "veterinario",
        ],

        "questions": [
            "Que especie animal, sintomas, cantidad de animales afectados y fecha de inicio observa?",
            "Hubo contacto con personas, mordeduras, abortos, muerte subita o signos neurologicos/respiratorios?",
            "Los animales/productos estan aislados y ya contacto a veterinario o autoridad sanitaria?",
        ],
    },

    "seguridad_alimentaria": {

        "label": "Seguridad alimentaria",

        "keywords": [
            "carencia",
            "intervalo de carencia",
            "cosecha",
            "cosechar",
            "grano",
            "granos",
            "maiz",
            "maíz",
            "trigo",
            "soja",
            "micotoxina",
            "micotoxinas",
            "aflatoxina",
            "fumonisina",
            "hongo",
            "hongos",
            "moho",
            "humedad",
            "almacenamiento",
            "silo",
            "bolsa",
            "secado",
            "alimento",
            "consumo",
        ],

        "questions": [
            "Que cultivo/alimento quiere cosechar o almacenar y que tratamiento reciente recibio?",
            "Se cumplio el intervalo de carencia de la etiqueta y cual es la fecha de ultima aplicacion?",
            "Cual es la humedad, presencia de hongos/moho y condicion de silo/bolsa/secado?",
        ],
    },

    "incendios_rurales": {

        "label": "Incendios rurales",

        "keywords": [
            "incendio",
            "fuego",
            "quema",
            "quemar",
            "pastizal",
            "rastrojo",
            "sequía",
            "sequia",
            "viento",
            "maquinaria caliente",
            "chispa",
            "cortafuego",
            "bombero",
            "bomberos",
            "indice de riesgo",
            "riesgo de incendio",
        ],

        "questions": [
            "Que tarea con fuego o maquinaria caliente quiere realizar y en que zona?",
            "Cuales son viento, sequia/humedad, temperatura, combustible seco e indice local de riesgo de incendio?",
            "Tiene permiso, cortafuegos, agua/equipo de control y contacto de autoridad local/bomberos?",
        ],
    },

    "riego_suelo": {

        "label": "Riego y suelo",

        "keywords": [
            "riego",
            "suelo",
            "salinidad",
            "salinizacion",
            "salinización",
            "erosion",
            "erosión",
            "fertilizante",
            "fertilizacion",
            "fertilización",
            "urea",
            "nitrato",
            "fosforo",
            "fósforo",
            "napas",
            "napa",
            "lixiviacion",
            "lixiviación",
            "escorrentia",
            "escorrentía",
            "pendiente",
            "compactacion",
            "compactación",
        ],

        "questions": [
            "Que cultivo, suelo, pendiente y sistema de riego/fertilizacion esta usando?",
            "Tiene analisis de suelo/agua, salinidad, dosis de fertilizante y pronostico de lluvia/riego?",
            "Hay napas, pozos, cursos de agua o signos de erosion/escorrentia cerca del lote?",
        ],
    },

    "bioseguridad_vegetal": {

        "label": "Bioseguridad vegetal",

        "keywords": [
            "plaga",
            "enfermedad",
            "cuarenten",
            "mancha",
            "marchitez",
            "roya",
            "cancro",
            "mosca",
            "picudo",
            "material vegetal",
            "semilla",
            "plantin",
            "plantín",
            "trasladar",
            "senasa",
        ],

        "questions": [
            "Que cultivo, sintomas, ubicacion y velocidad de avance observa?",
            "Movio semillas, frutos, plantas, suelo, herramientas o maquinaria desde/hacia otro lote?",
            "Puede aislar el material, evitar traslados, tomar fotos y consultar autoridad fitosanitaria?",
        ],
    },
}


ALLOWED_RISKS = {
    "BAJO",
    "MEDIO",
    "ALTO",
    "CRITICO",
}


def _infer_domains(text: str) -> list[str]:

    low = (text or "").lower()

    detected = []

    for key, cfg in SAFETY_DOMAINS.items():

        if any(
            keyword.lower() in low
            for keyword in cfg["keywords"]
        ):

            detected.append(key)

    return detected or ["agroquimicos"]


def _fallback_questions(
    domains: list[str],
) -> list[str]:

    questions = []

    for domain in domains:

        questions.extend(
            SAFETY_DOMAINS
            .get(domain, {})
            .get("questions", [])
        )

    seen = []

    for question in questions:

        if question not in seen:
            seen.append(question)

    return (
        seen[:3]
        or _DEFAULT_EVAL["preguntas_seguimiento"]
    )


def _norm_text(text: str) -> str:

    normalized = (text or "").lower()

    normalized = re.sub(
        r"[^\w\s]",
        " ",
        normalized,
        flags=re.UNICODE,
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()

    return normalized


def _question_tokens(
    text: str,
) -> set[str]:

    stopwords = {
        "a",
        "al",
        "algo",
        "con",
        "cual",
        "cuales",
        "cuando",
        "de",
        "del",
        "el",
        "en",
        "es",
        "estan",
        "esta",
        "fue",
        "ha",
        "hay",
        "la",
        "las",
        "lo",
        "los",
        "o",
        "para",
        "por",
        "que",
        "se",
        "si",
        "su",
        "sus",
        "te",
        "tiene",
        "tus",
        "un",
        "una",
        "y",
        "ya",
    }

    return {
        word
        for word in _norm_text(text).split()
        if len(word) > 3
        and word not in stopwords
    }


def _is_similar_question(
    question: str,
    previous_questions: list[str],
) -> bool:

    current = _question_tokens(question)

    if not current:
        return True

    for previous in previous_questions:

        prev = _question_tokens(previous)

        if not prev:
            continue

        overlap = (
            len(current & prev)
            / max(
                1,
                min(
                    len(current),
                    len(prev),
                ),
            )
        )

        if overlap >= 0.55:
            return True

    return False


def _answer_seems_to_cover_question(
    question: str,
    answers_text: str,
) -> bool:

    q = _norm_text(question)
    a = _norm_text(answers_text)

    if not a:
        return False

    coverage_groups = (

        (
            ("vacun", "vacuna"),
            ("vacun",),
        ),

        (
            (
                "sintoma",
                "sintomas",
                "enfermedad",
                "inusual",
            ),
            (
                "sintoma",
                "enfermedad",
                "sanas",
                "sano",
                "sana",
            ),
        ),

        (
            (
                "veterinario",
                "profesional",
                "autoridad",
            ),
            (
                "veterinario",
                "profesional",
                "autoridad",
            ),
        ),

        (
            (
                "ubicacion",
                "zona",
                "localidad",
                "provincia",
                "pais",
            ),
            (
                "suardi",
                "morteros",
                "san guillermo",
                "cordoba",
                "santa fe",
            ),
        ),

        (
            (
                "contacto",
                "aislado",
                "aislar",
            ),
            (
                "aislad",
                "contact",
                "separad",
            ),
        ),

        (
            (
                "alimentacion",
                "alimento",
            ),
            (
                "alimento",
                "alimentacion",
                "pasto",
                "balanceado",
                "silo",
            ),
        ),
    )

    for q_terms, a_terms in coverage_groups:

        if (
            any(term in q for term in q_terms)
            and any(term in a for term in a_terms)
        ):
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
            question
            for item in session.historial_respuestas
            for question in item.get(
                "preguntas",
                [],
            )
        ]

        answers_text = "\n".join(
            item.get("respuesta", "")
            for item in session.historial_respuestas
        )

    filtered = []

    for question in questions:

        if _is_similar_question(
            question,
            previous_questions + filtered,
        ):
            continue

        if _answer_seems_to_cover_question(
            question,
            answers_text,
        ):
            continue

        filtered.append(question)

    if len(filtered) >= 3 or not allow_fallback:
        return filtered[:3]

    for question in _fallback_questions(domains):

        if _is_similar_question(
            question,
            previous_questions + filtered,
        ):
            continue

        if _answer_seems_to_cover_question(
            question,
            answers_text,
        ):
            continue

        filtered.append(question)

        if len(filtered) == 3:
            break

    if not filtered:

        filtered.append(
            "Podes darnos mas detalles especificos de tu situacion "
            "(ubicacion, producto/tarea exacta, cantidades, fechas) "
            "que todavia no hayas mencionado?"
        )

    return filtered


def _normalize_eval(
    ev: dict,
    history_text: str,
    session: Optional[SessionState] = None,
) -> dict:

    if not isinstance(ev, dict):
        ev = _DEFAULT_EVAL.copy()

    domains = (
        ev.get("dominios_detectados")
        or _infer_domains(history_text)
    )

    if isinstance(domains, str):
        domains = [domains]

    domains = [
        domain
        for domain in domains
        if domain in SAFETY_DOMAINS
    ] or _infer_domains(history_text)

    ev["dominios_detectados"] = domains

    risk = str(
        ev.get(
            "nivel_riesgo",
            "ALTO",
        )
    ).upper().replace(
        "CRÍTICO",
        "CRITICO",
    )

    ev["nivel_riesgo"] = (
        risk
        if risk in ALLOWED_RISKS
        else "ALTO"
    )

    try:

        ev["confianza"] = max(
            0,
            min(
                100,
                int(
                    ev.get(
                        "confianza",
                        30,
                    )
                ),
            ),
        )

    except Exception:

        ev["confianza"] = 30

    for field_name in (
        "riesgos_detectados",
        "informacion_faltante",
        "preguntas_seguimiento",
        "marco_regulatorio_aplicable",
    ):

        value = ev.get(field_name)

        if isinstance(value, str):

            ev[field_name] = [value]

        elif not isinstance(value, list):

            ev[field_name] = []

    needs_more_evidence = not ev.get(
        "evidencia_suficiente",
        False,
    )

    if (
        not ev["preguntas_seguimiento"]
        and needs_more_evidence
    ):

        ev["preguntas_seguimiento"] = (
            _fallback_questions(domains)
        )

    ev["preguntas_seguimiento"] = (
        _filter_followup_questions(
            ev["preguntas_seguimiento"],
            session,
            domains,
            allow_fallback=needs_more_evidence,
        )
    )

    if not ev["informacion_faltante"]:

        ev["informacion_faltante"] = [
            "Contexto local suficiente para evaluar "
            "la accion con seguridad"
        ]

    if not ev["riesgos_detectados"]:

        ev["riesgos_detectados"] = [
            "Riesgo agricola no caracterizado completamente"
        ]

    if (
        ev["nivel_riesgo"] in {"ALTO", "CRITICO"}
        and not ev.get(
            "evidencia_suficiente",
            False,
        )
    ):

        ev["debe_abstenerse"] = True

    if ev["confianza"] < 65:
        ev["debe_abstenerse"] = True

    ev["requiere_profesional"] = bool(
        ev.get(
            "requiere_profesional",
            ev["nivel_riesgo"] in {"ALTO", "CRITICO"},
        )
    )

    return ev


# ── Safety chain ──────────────────────────────────────────────────────────────

def _build_safety_chain(
    tenant_slug: str,
):
    """
    Construye el safety chain utilizado tanto por las consultas
    con sesión como por el endpoint stateless /api/risk-score.
    """

    retriever = get_retriever(tenant_slug)

    return (
        {
            "context": retriever,
            "agro_history": RunnablePassthrough(),
        }
        | ChatPromptTemplate.from_template(
            SAFETY_TMPL
        )
        | ChatGoogleGenerativeAI(
            model="gemini-3.6-flash",
            temperature=0.0,
        )
    )

def _extraer_producto_fitosanitario(historial: str) -> str | None:
    """
    Intenta extraer el nombre del producto fitosanitario
    mencionado por el usuario.
    """

    patrones = [
        r"(?:producto|herbicida|insecticida|fungicida|fitosanitario)"
        r"\s*(?:es|:)?\s*([A-Za-zÁÉÍÓÚáéíóúÑñ0-9\- ]{3,80})",

        r"(?:usar|aplicar|aplicando|apliqué|aplique)"
        r"\s+(?:el|la)?\s*"
        r"([A-Za-zÁÉÍÓÚáéíóúÑñ0-9\- ]{3,80})",

        r"(?:con)\s+"
        r"([A-Za-zÁÉÍÓÚáéíóúÑñ0-9\- ]{3,80})"
        r"\s+(?:para|en)",
    ]

    for patron in patrones:
        match = re.search(
            patron,
            historial,
            flags=re.IGNORECASE,
        )

        if match:
            producto = match.group(1).strip()

            producto = re.sub(
                r"\s+(?:para|en|sobre|contra)\s+.*$",
                "",
                producto,
                flags=re.IGNORECASE,
            )

            producto = producto.strip(" .,;:")

            if len(producto) >= 3:
                return producto

    return None
# ── Session processing ────────────────────────────────────────────────────────

async def _run_iteration(
    session: SessionState,
) -> dict:

    historial_str = "\n".join(
        f"- {s}"
        for s in session.historial_consulta
    )

    safety_chain = _build_safety_chain(
        session.tenant_slug
    )

    try:

        resp = safety_chain.invoke(
            historial_str
        )

        ev = _normalize_eval(
            _parse_json_safe(
                _extract_text(resp.content),
                _DEFAULT_EVAL.copy(),
            ),
            historial_str,
            session,
        )

    except Exception as exc:

        logger.error(
            "Safety chain error | tenant=%s | consulta=%s: %s",
            session.tenant_slug,
            session.consulta_id,
            exc,
        )

        ev = _normalize_eval(
            _DEFAULT_EVAL.copy(),
            historial_str,
            session,
        )
    dominios = ev.get("dominios_detectados", [])
    if "agroquimicos" in dominios:
        producto = _extraer_producto_fitosanitario(historial_str)
        if producto:
            try:
                senasa_resultado = await buscar_fitosanitario(producto)
                if senasa_resultado:
                    historial_senasa = (
                    f"VERIFICACIÓN SENASA: "
                    f"El producto '{producto}' figura registrado. "
                    f"Número de registro: "
                    f"{senasa_resultado.get('numero_registro') or 'No informado'}. "
                    f"Usos permitidos: "
                    f"{', '.join(senasa_resultado.get('usos_permitidos', [])) or 'No informados'}."
                )
                else:
                    historial_senasa = (
                    f"VERIFICACIÓN SENASA: "
                    f"No se encontró el producto '{producto}' "
                    f"en la búsqueda realizada."
                    )
                session.historial_consulta.append(historial_senasa)
            except Exception as exc:
                logger.warning(
                    "No se pudo verificar '%s' en SENASA: %s",
                    producto,
                    exc,
                )
    # ============================================================
# SENASA - VERIFICACIÓN DE FITOSANITARIOS
# ============================================================

    session.confianza_final = ev.get(
        "confianza",
        0,
    )

    session.riesgo_final = ev.get(
        "nivel_riesgo",
        "ALTO",
    )

    session.evidencia_final = ev.get(
        "evidencia_suficiente",
        False,
    )

    session.se_abstuvo_final = ev.get(
        "debe_abstenerse",
        True,
    )

    session.ultima_evaluacion = ev

    registrar_auditoria(
        session.consulta_id,
        session.iteracion_actual,
        "EVALUACION_ITERACION",
        {
            key: ev.get(key)
            for key in (
                "confianza",
                "nivel_riesgo",
                "dominios_detectados",
                "evidencia_suficiente",
                "debe_abstenerse",
            )
        },
    )

    should_complete = (

        (
            session.confianza_final
            >= session.umbral_confianza
            and session.evidencia_final
        )

        or session.iteracion_actual
        >= session.max_iteraciones
    )

    if should_complete:
        _finalize(session)

    return ev


def _finalize(
    session: SessionState,
) -> None:

    """
    Generate the final evaluation,
    run the evidence checker,
    and persist everything.
    """

    retriever = get_retriever(
        session.tenant_slug
    )

    all_info = "\n".join(
        f"- {s}"
        for s in session.historial_consulta
    )

    final_chain = (
        {
            "all_info": RunnablePassthrough(),
            "context": retriever,
        }
        | ChatPromptTemplate.from_template(
            FINAL_TMPL
        )
        | _llm
    )

    try:

        eval_text = _extract_text(
            final_chain.invoke(
                all_info
            ).content
        )

    except Exception as exc:

        logger.error(
            "Final eval error: %s",
            exc,
        )

        eval_text = (
            "No se pudo generar la evaluación final."
        )

    docs = retriever.invoke(
        "\n".join(
            session.historial_consulta[-3:]
        )
    )

    contexto = "\n\n".join(
        f"[Fuente: {d.metadata.get('source_file', 'N/A')} "
        f"| Pág: {d.metadata.get('page', 'N/A')}]\n"
        f"{d.page_content}"
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
                "question": "\n".join(
                    session.historial_consulta
                ),
                "answer": eval_text,
                "context": contexto,
            }
        )

        verificacion = _parse_json_safe(
            _extract_text(
                ev_resp.content
            ),
            default_fail,
        )

    except Exception as exc:

        logger.error(
            "Evidence checker error: %s",
            exc,
        )

        verificacion = default_fail

    if verificacion.get(
        "abstain_recommendation",
        False,
    ):

        session.se_abstuvo_final = True

        logger.warning(
            "Evidence checker recomienda abstención. "
            "hallucination_risk=%s",
            verificacion.get(
                "hallucination_risk"
            ),
        )

    duracion = (
        time.time()
        - session.inicio
    )

    guardar_evaluacion_final(
        session.consulta_id,
        eval_text,
        session.iteracion_actual - 1,
        session.se_abstuvo_final,
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
            "duracion_seg": round(
                duracion,
                2,
            ),
        },
    )

    session.evaluacion_final = eval_text
    session.verificacion = verificacion
    session.completado = True


# ── PDF helpers ───────────────────────────────────────────────────────────────

def _pdf_text(value) -> str:

    text = (
        ""
        if value is None
        else str(value)
    )

    return html.escape(text).replace(
        "\n",
        "<br/>",
    )


def _join_items(items) -> str:

    if not items:
        return "No registrado"

    if isinstance(items, str):
        return items

    return ", ".join(
        str(x)
        for x in items
    )


def _build_pdf_bytes(
    session: SessionState,
) -> bytes:

    try:

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import (
            getSampleStyleSheet,
            ParagraphStyle,
        )
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
        )
        from reportlab.graphics.shapes import (
            Drawing,
            Circle,
            Rect as GRect,
            String as GString,
        )

    except ImportError as exc:

        raise HTTPException(
            500,
            "Falta la dependencia reportlab. "
            "Instalar con: pip install reportlab",
        ) from exc

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=(
            f"AgroSafety diagnostico "
            f"{session.consulta_id}"
        ),
    )

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="Small",
            parent=styles["BodyText"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor(
                "#475569"
            ),
        )
    )

    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading2"],
            fontSize=12,
            leading=15,
            spaceBefore=10,
            spaceAfter=5,
            textColor=colors.HexColor(
                "#14532d"
            ),
        )
    )

    styles.add(
        ParagraphStyle(
            name="Box",
            parent=styles["BodyText"],
            fontSize=9,
            leading=12,
            backColor=colors.HexColor(
                "#f8fafc"
            ),
            borderColor=colors.HexColor(
                "#e2e8f0"
            ),
            borderWidth=0.5,
            borderPadding=6,
            spaceAfter=8,
        )
    )

    ev = (
        session.ultima_evaluacion
        or {}
    )

    verif = (
        session.verificacion
        or {}
    )

    generated_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M"
    )

    story = []

    story.append(
        Paragraph(
            "AgroSafety - Diagnostico de Seguridad Agricola",
            styles["Title"],
        )
    )

    story.append(
        Paragraph(
            "Reporte generado automaticamente "
            "por la capa de AI Safety agricola.",
            styles["Small"],
        )
    )

    story.append(
        Spacer(1, 8)
    )

    summary_data = [

        [
            Paragraph(
                "Consulta ID",
                styles["Small"],
            ),
            Paragraph(
                str(session.consulta_id),
                styles["Small"],
            ),
        ],

        [
            Paragraph(
                "Fecha",
                styles["Small"],
            ),
            Paragraph(
                generated_at,
                styles["Small"],
            ),
        ],

        [
            Paragraph(
                "Riesgo",
                styles["Small"],
            ),
            Paragraph(
                _pdf_text(
                    ev.get(
                        "nivel_riesgo",
                        session.riesgo_final,
                    )
                ),
                styles["Small"],
            ),
        ],

        [
            Paragraph(
                "Confianza",
                styles["Small"],
            ),
            Paragraph(
                f"{ev.get('confianza', session.confianza_final)}%",
                styles["Small"],
            ),
        ],

        [
            Paragraph(
                "Dominios",
                styles["Small"],
            ),
            Paragraph(
                _pdf_text(
                    _join_items(
                        ev.get(
                            "dominios_detectados",
                            [],
                        )
                    )
                ),
                styles["Small"],
            ),
        ],

        [
            Paragraph(
                "Abstencion",
                styles["Small"],
            ),
            Paragraph(
                "Si"
                if session.se_abstuvo_final
                else "No",
                styles["Small"],
            ),
        ],

        [
            Paragraph(
                "Requiere profesional",
                styles["Small"],
            ),
            Paragraph(
                "Si"
                if ev.get(
                    "requiere_profesional",
                    True,
                )
                else "No",
                styles["Small"],
            ),
        ],
    ]

    table = Table(
        summary_data,
        colWidths=[
            4.2 * cm,
            11.2 * cm,
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor(
                        "#dcfce7"
                    ),
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.35,
                    colors.HexColor(
                        "#cbd5e1"
                    ),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    story.append(table)

    # ── Visual: semáforo + barra de confianza + tabla de severidad ─────────────
    _nivel_norm = (
        ev.get("nivel_riesgo", session.riesgo_final) or "ALTO"
    ).upper().replace("CRÍTICO", "CRITICO")
    _conf_val = int(ev.get("confianza", session.confianza_final) or 0)

    story.append(Spacer(1, 10))
    story.append(Paragraph("Semáforo de riesgo", styles["Section"]))
    _GREY = colors.HexColor("#374151")
    _SEMA = {
        "BAJO":    (colors.HexColor("#22c55e"), _GREY,                     _GREY),
        "MEDIO":   (_GREY,                      colors.HexColor("#eab308"), _GREY),
        "ALTO":    (_GREY,                      _GREY,                     colors.HexColor("#f97316")),
        "CRITICO": (_GREY,                      _GREY,                     colors.HexColor("#ef4444")),
    }
    _sc1, _sc2, _sc3 = _SEMA.get(_nivel_norm, _SEMA["ALTO"])
    _risk_hex = {
        "BAJO": "#22c55e", "MEDIO": "#eab308",
        "ALTO": "#f97316", "CRITICO": "#ef4444",
    }.get(_nivel_norm, "#f97316")
    _sema = Drawing(110, 36)
    _sema.add(GRect(0, 0, 110, 36, fillColor=colors.HexColor("#1f2937"), strokeColor=None))
    for _xi, _col in [(16, _sc1), (50, _sc2), (84, _sc3)]:
        _sema.add(Circle(_xi, 18, 12, fillColor=_col,
                         strokeColor=colors.HexColor("#4b5563"), strokeWidth=1))
    story.append(_sema)
    story.append(Paragraph(
        f"<b>{_nivel_norm}</b> — "
        f"Abstención: {'Sí' if session.se_abstuvo_final else 'No'} — "
        f"Confianza: {_conf_val}%",
        styles["Small"],
    ))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Confianza del sistema", styles["Section"]))
    _BW = int(15.4 * cm)
    _BFW = max(0, int(_BW * _conf_val / 100))
    _bc = (
        colors.HexColor("#22c55e") if _conf_val >= 75
        else colors.HexColor("#eab308") if _conf_val >= 50
        else colors.HexColor("#ef4444")
    )
    _cd = Drawing(_BW, 26)
    _cd.add(GRect(0, 5, _BW, 14, fillColor=colors.HexColor("#e5e7eb"), strokeColor=None))
    if _BFW > 0:
        _cd.add(GRect(0, 5, _BFW, 14, fillColor=_bc, strokeColor=None))
    _cl = GString(_BW // 2, 8, f"{_conf_val}%")
    _cl.fontSize = 8
    _cl.fontName = "Helvetica-Bold"
    _cl.fillColor = colors.white if _conf_val > 25 else colors.HexColor("#111827")
    _cl.textAnchor = "middle"
    _cd.add(_cl)
    story.append(_cd)

    story.append(Spacer(1, 8))
    story.append(Paragraph("Contexto de severidad comparativa", styles["Section"]))
    _SEV_BG  = {"BAJO": colors.HexColor("#dcfce7"), "MEDIO": colors.HexColor("#fef9c3"),
                "ALTO": colors.HexColor("#ffedd5"), "CRITICO": colors.HexColor("#fee2e2")}
    _SEV_DESC = {
        "BAJO":    "Sin riesgo inmediato — accion preventiva",
        "MEDIO":   "Precaucion — verificar condiciones locales",
        "ALTO":    "Riesgo elevado — suspender y consultar",
        "CRITICO": "Situacion critica — accion urgente",
    }
    _SEV_BAR = {"BAJO": "█░░░", "MEDIO": "██░░", "ALTO": "███░", "CRITICO": "████"}
    _sev_rows = [[
        Paragraph("<b>Nivel</b>", styles["Small"]),
        Paragraph("<b>Descripcion de referencia</b>", styles["Small"]),
        Paragraph("<b>Escala</b>", styles["Small"]),
    ]]
    _sev_ts = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for _ri, _key in enumerate(("BAJO", "MEDIO", "ALTO", "CRITICO"), start=1):
        _cur = _key == _nivel_norm
        _sev_rows.append([
            Paragraph(f"<b>{_key}</b>" if _cur else _key, styles["Small"]),
            Paragraph(f"<b>{_SEV_DESC[_key]}</b>" if _cur else _SEV_DESC[_key], styles["Small"]),
            Paragraph(f"<b>{_SEV_BAR[_key]}</b>" if _cur else _SEV_BAR[_key], styles["Small"]),
        ])
        if _cur:
            _sev_ts += [
                ("BACKGROUND", (0, _ri), (-1, _ri), _SEV_BG[_key]),
                ("FONTNAME", (0, _ri), (-1, _ri), "Helvetica-Bold"),
            ]
    _sev_t = Table(_sev_rows, colWidths=[2.5 * cm, 9.4 * cm, 3.5 * cm])
    _sev_t.setStyle(TableStyle(_sev_ts))
    story.append(_sev_t)
    story.append(Spacer(1, 10))

    def section(
        title: str,
        body,
    ):

        story.append(
            Paragraph(
                title,
                styles["Section"],
            )
        )

        if isinstance(body, list):

            if body:

                for item in body:

                    story.append(
                        Paragraph(
                            f"- {_pdf_text(item)}",
                            styles["BodyText"],
                        )
                    )

            else:

                story.append(
                    Paragraph(
                        "No registrado",
                        styles["BodyText"],
                    )
                )

        else:

            story.append(
                Paragraph(
                    _pdf_text(
                        body
                        or "No registrado"
                    ),
                    styles["Box"],
                )
            )

    section(
        "Consulta e historial",
        session.historial_consulta,
    )

    section(
        "Justificacion tecnica",
        ev.get(
            "justificacion",
            "",
        ),
    )

    section(
        "Riesgos detectados",
        ev.get(
            "riesgos_detectados",
            [],
        ),
    )

    section(
        "Informacion faltante",
        ev.get(
            "informacion_faltante",
            [],
        ),
    )

    section(
        "Marco o autoridad aplicable",
        ev.get(
            "marco_regulatorio_aplicable",
            [],
        ),
    )

    section(
        "Evaluacion final",
        session.evaluacion_final
        or (
            "La consulta aun no tiene "
            "evaluacion final. Complete el "
            "flujo de preguntas para generar "
            "el diagnostico final."
        ),
    )

    if verif:

        section(
            "Verificacion de evidencia",
            verif.get(
                "explanation",
                "",
            ),
        )

        section(
            "Fuentes citadas",
            verif.get(
                "cited_sources",
                [],
            ),
        )

        section(
            "Afirmaciones sin respaldo",
            verif.get(
                "unsupported_claims",
                [],
            ),
        )

    story.append(
        Spacer(1, 10)
    )

    story.append(
        Paragraph(
            "Aviso: AgroSafety no reemplaza a "
            "profesionales habilitados ni autoridades "
            "sanitarias, fitosanitarias, ambientales "
            "o de emergencia.",
            styles["Small"],
        )
    )

    doc.build(story)

    buffer.seek(0)

    return buffer.getvalue()


def _to_response(
    session: SessionState,
) -> dict:

    ev = (
        session.ultima_evaluacion
        or {}
    )

    return {

        "consulta_id": session.consulta_id,

        "iteracion": session.iteracion_actual,

        "max_iteraciones": session.max_iteraciones,

        "completado": session.completado,

        "confianza": ev.get(
            "confianza",
            session.confianza_final,
        ),

        "nivel_riesgo": ev.get(
            "nivel_riesgo",
            session.riesgo_final,
        ),

        "evidencia_suficiente": ev.get(
            "evidencia_suficiente",
            session.evidencia_final,
        ),

        "dominios_detectados": ev.get(
            "dominios_detectados",
            [],
        ),

        "justificacion": ev.get(
            "justificacion",
            "",
        ),

        "riesgos_detectados": ev.get(
            "riesgos_detectados",
            [],
        ),

        "informacion_faltante": ev.get(
            "informacion_faltante",
            [],
        ),

        "preguntas_seguimiento": (
            ev.get(
                "preguntas_seguimiento",
                [],
            )
            if not session.completado
            else []
        ),

        "debe_abstenerse": ev.get(
            "debe_abstenerse",
            session.se_abstuvo_final,
        ),

        "marco_regulatorio_aplicable": ev.get(
            "marco_regulatorio_aplicable",
            [],
        ),

        "requiere_profesional": ev.get(
            "requiere_profesional",
            True,
        ),

        "evaluacion_final": session.evaluacion_final,

        "verificacion_evidencia": session.verificacion,

        "se_abstuvo_final": session.se_abstuvo_final,
    }


# ── Startup ───────────────────────────────────────────────────────────────────

def _sync_init() -> None:

    global _llm, _evidence_chain

    _connect_db()

    api_key = os.environ.get(
        "GOOGLE_API_KEY",
        "",
    )

    if not api_key:

        logger.error(
            "GOOGLE_API_KEY no está definida. "
            "La API no podrá responder consultas."
        )

        return

    _llm = ChatGoogleGenerativeAI(
        model="gemini-3.6-flash",
        temperature=0.2,
    )

    _evidence_chain = (
        ChatPromptTemplate.from_template(
            EVIDENCE_TMPL
        )
        | ChatGoogleGenerativeAI(
            model="gemini-3.6-flash",
            temperature=0.0,
        )
    )

    logger.info(
        "AgroSafety API lista"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):

    asyncio.create_task(
        asyncio.to_thread(
            _sync_init
        )
    )

    yield

    close_pool()

    logger.info(
        "AgroSafety API apagada"
    )


# ── FastAPI app ───────────────────────────────────────────────────────────────

limiter = Limiter(
    key_func=get_remote_address
)

app = FastAPI(
    title="AgroSafety API",
    description=(
        "Sistema de evaluacion integral "
        "de seguridad agricola con AI Safety"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# slowapi
app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)

app.include_router(
    auth_router
)

app.include_router(
    admin_router
)

app.include_router(
    keys_router
)
app.include_router(whatsapp_router)
app.include_router(voz_router)
app.include_router(imagen_router)
app.include_router(dashboard_router)
app.include_router(senasa_router)
_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",")
    if o.strip()
] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


FRONTEND_DIR = (
    pathlib.Path(__file__).parent
    / "frontend"
)

if FRONTEND_DIR.is_dir():

    app.mount(
        "/static",
        StaticFiles(
            directory=str(FRONTEND_DIR)
        ),
        name="static",
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
async def root():

    idx = (
        FRONTEND_DIR
        / "index.html"
    )

    if idx.exists():

        return FileResponse(
            str(idx)
        )

    return {
        "status": "AgroSafety API running",
        "frontend": (
            "frontend/index.html "
            "not found"
        ),
    }


@app.get("/landing")
async def landing():
    page = FRONTEND_DIR / "landing.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "Landing page not found"}


@app.get("/admin.html")
async def admin_page():
    page = FRONTEND_DIR / "admin.html"
    if page.exists():
        return FileResponse(str(page))
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/api/health")
async def health():

    return {

        "status": "ok",

        "db_connected": (
            _db_ready
            and is_pool_initialized()
        ),

        "ai_ready": (
            _llm is not None
        ),

        "safety_domains": [
            cfg["label"]
            for cfg in SAFETY_DOMAINS.values()
        ],
    }


@app.get("/api/public-config")
async def public_config():
    """Configuracion publica para el frontend (sin auth)."""
    raw = os.environ.get("TWILIO_WHATSAPP_FROM", "")  # e.g. "whatsapp:+14155238886"
    wa_number = raw.replace("whatsapp:", "").strip()
    return {
        "public_key": os.environ.get("PUBLIC_API_KEY", ""),
        "whatsapp_number": wa_number,
    }


# ── Día 7: Stateless Risk Score ──────────────────────────────────────────────

@app.get("/api/risk-score")
@limiter.limit("10/minute")
async def risk_score(
    request: Request,
    q: str = Query(
        ...,
        min_length=1,
        description="Consulta agricola a evaluar",
    ),
    current_user: dict = Depends(require_any),
):

    """
    Evaluacion stateless de riesgo agricola.

    No crea una sesion.
    No persiste la consulta.
    No modifica el historial.
    Limite: 10 requests por minuto por IP.
    """

    if _llm is None:

        raise HTTPException(
            status_code=503,
            detail=(
                "Sistema no inicializado. "
                "Verificar GOOGLE_API_KEY."
            ),
        )

    query = q.strip()

    if not query:

        raise HTTPException(
            status_code=400,
            detail=(
                "El parametro q no puede "
                "estar vacio."
            ),
        )

    try:

        # Endpoint stateless:
        # usamos el tenant por defecto.
        tenant_slug = "default"

        safety_chain = (
            _build_safety_chain(
                tenant_slug
            )
        )

        resp = safety_chain.invoke(
            query
        )

        ev = _parse_json_safe(
            _extract_text(
                resp.content
            ),
            _DEFAULT_EVAL.copy(),
        )

        ev = _normalize_eval(
            ev,
            query,
            session=None,
        )

        return {
            "query": query,
            **ev,
        }

    except Exception as exc:

        logger.exception(
            "Risk score error | query=%s: %s",
            query,
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "No se pudo evaluar "
                "el riesgo."
            ),
        )


# ── Consulta con sesión ──────────────────────────────────────────────────────

@app.post("/api/consulta")
async def iniciar_consulta(
    req: ConsultaRequest,
    current_user: dict = Depends(require_any),
):

    if _llm is None:

        raise HTTPException(
            503,
            (
                "Sistema no inicializado. "
                "Verificar GOOGLE_API_KEY "
                "y reiniciar el servidor."
            ),
        )

    tenant_slug = req.tenant_slug

    consulta_id = crear_consulta(
        req.consulta_inicial,
        tenant_slug,
    )

    session = SessionState(

        consulta_id=consulta_id,

        tenant_slug=tenant_slug,

        umbral_confianza=req.umbral_confianza,

        max_iteraciones=req.max_iteraciones,
    )

    session.historial_consulta.append(
        f"CONSULTA INICIAL: "
        f"{req.consulta_inicial}"
    )
    if req.lat is not None and req.lon is not None:
        clima=await _fetch_clima(
            req.lat,
            req.lon
        )
        session.historial_consulta.append(
                f"CLIMA:{clima}"
            )
    registrar_auditoria(
        consulta_id,
        0,
        "CONSULTA_INICIAL",
        {
            "consulta": req.consulta_inicial
        },
    )

    await _run_iteration(
        session
    )

    _sessions[consulta_id] = session

    return _to_response(
        session
    )

@app.get("/api/clima")
async def clima_actual(
    lat: float,
    lon: float,
    current_user: dict = Depends(require_any),
):
    return await _fetch_clima(lat, lon)

@app.post(
    "/api/consulta/{consulta_id}/responder"
)
async def responder_consulta(
    consulta_id: int,
    req: RespuestaRequest,
    current_user: dict = Depends(require_any),
):

    session = _sessions.get(
        consulta_id
    )

    if session is None:

        raise HTTPException(
            404,
            f"Consulta {consulta_id} no encontrada.",
        )

    if session.completado:

        raise HTTPException(
            400,
            "La consulta ya está completada.",
        )

    preguntas = (
        session.ultima_evaluacion
        or {}
    ).get(
        "preguntas_seguimiento",
        [],
    )

    guardar_respuesta(
        consulta_id,
        session.iteracion_actual,
        preguntas,
        req.respuesta,
        session.confianza_final,
        session.riesgo_final,
    )

    registrar_auditoria(
        consulta_id,
        session.iteracion_actual,
        "RESPUESTA_USUARIO",
        {
            "respuesta": req.respuesta
        },
    )

    if req.respuesta.strip():

        session.historial_consulta.append(
            f"Respuesta iteración "
            f"{session.iteracion_actual}: "
            f"{req.respuesta}"
        )

        session.historial_respuestas.append(
            {
                "iteracion": (
                    session.iteracion_actual
                ),
                "preguntas": preguntas,
                "respuesta": req.respuesta,
            }
        )

    session.iteracion_actual += 1

    await _run_iteration(
        session
    )

    return _to_response(
        session
    )


@app.get(
    "/api/consulta/{consulta_id}/pdf"
)
async def descargar_pdf_consulta(
    consulta_id: int,
    current_user: dict = Depends(require_any),
):

    session = _sessions.get(
        consulta_id
    )

    if session is None:

        raise HTTPException(
            404,
            f"Consulta {consulta_id} no encontrada.",
        )

    pdf_bytes = _build_pdf_bytes(
        session
    )

    filename = (
        f"agrosafety_diagnostico_"
        f"{consulta_id}.pdf"
    )

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f"attachment; filename={filename}"
        },
    )


@app.get(
    "/api/consulta/{consulta_id}"
)
async def get_consulta(
    consulta_id: int,
    current_user: dict = Depends(require_any),
):

    session = _sessions.get(
        consulta_id
    )

    if session is None:

        raise HTTPException(
            404,
            f"Consulta {consulta_id} no encontrada.",
        )

    return _to_response(
        session
    )


@app.delete(
    "/api/consulta/{consulta_id}"
)
async def descartar_consulta(
    consulta_id: int,
    current_user: dict = Depends(require_any),
):
    """Descarta la sesión en memoria. No borra datos de la DB."""
    _sessions.pop(consulta_id, None)
    return {"ok": True, "consulta_id": consulta_id}


# ── OpenAPI ───────────────────────────────────────────────────────────────────

def custom_openapi():

    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(

        title="AgroSafety API",

        version="1.0.0",

        description=(
            "Sistema de evaluación integral "
            "de seguridad agrícola con AI Safety."
        ),

        routes=app.routes,
    )

    openapi_schema["components"][
        "securitySchemes"
    ] = {

        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        },

        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        },
    }

    app.openapi_schema = (
        openapi_schema
    )

    return app.openapi_schema


app.openapi = custom_openapi
