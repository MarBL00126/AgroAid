from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI

from core.chroma import get_retriever
from core.config import GEMINI_MODEL

logger = logging.getLogger("agrosafety.ai")

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

# ── Prompts ────────────────────────────────────────────────────────────

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

# ── LangChain helpers ────────────────────────────────────────────────────────────

def extract_text(content) -> str:

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


def parse_json_safe(
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


# ── Singletons ────────────────────────────────────────────────────────────────

_llm: ChatGoogleGenerativeAI | None = None
_evidence_chain = None


def init_ai() -> bool:
    """Inicializa el LLM y el verificador de evidencia. Retorna False si falta GOOGLE_API_KEY."""
    global _llm, _evidence_chain

    if not os.environ.get("GOOGLE_API_KEY"):
        logger.error(
            "GOOGLE_API_KEY no está definida. "
            "La API no podrá responder consultas."
        )
        return False

    _llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=0.2,
    )

    _evidence_chain = (
        ChatPromptTemplate.from_template(EVIDENCE_TMPL)
        | ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            temperature=0.0,
        )
    )

    return True


def is_ai_ready() -> bool:
    return _llm is not None


def get_llm() -> ChatGoogleGenerativeAI:
    if _llm is None:
        raise RuntimeError("IA no inicializada (falta GOOGLE_API_KEY)")
    return _llm


def get_evidence_chain():
    if _evidence_chain is None:
        raise RuntimeError("IA no inicializada (falta GOOGLE_API_KEY)")
    return _evidence_chain


# ── Safety chain ──────────────────────────────────────────────────────────────

def build_safety_chain(
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
            model=GEMINI_MODEL,
            temperature=0.0,
        )
    )


@lru_cache(maxsize=32)
def get_safety_chain(tenant_slug: str):
    """Chain cacheado por tenant; limpiar con get_safety_chain.cache_clear() si cambian los documentos."""
    return build_safety_chain(tenant_slug)
