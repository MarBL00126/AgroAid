"""
Estado de sesión de una consulta y su ciclo de evaluación.

El estado vive en PostgreSQL (consultas.session_state), no en memoria del
proceso, por lo que es válido con múltiples workers y sobrevive reinicios.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass, field, fields
from typing import Optional

from core.ai_chains import (
    FINAL_TMPL,
    extract_text,
    get_evidence_chain,
    get_llm,
    get_safety_chain,
    parse_json_safe,
)
from core.chroma import get_retriever
from core.consulta_repo import (
    guardar_evaluacion_final,
    registrar_auditoria,
    registrar_metrica,
)
from core.database import db_exec, db_fetch_one
from core.domain_rules import (
    DEFAULT_EVAL,
    extraer_producto_fitosanitario,
    normalize_eval,
)
from core.senasa import buscar_fitosanitario
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

logger = logging.getLogger("agrosafety.session_service")


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

    # Identificador de la sesión de invitado que creó la consulta (None si fue un usuario registrado)
    owner: Optional[str] = None

# ── Persistencia de la sesión ─────────────────────────────────────────────────

def descartar_session_state(consulta_id: int) -> None:
    db_exec(
        """
        UPDATE consultas
        SET session_status = 'discarded',
            updated_at = now()
        WHERE id = %s
        """,
        (consulta_id,),
    )


def guardar_session_state(session: SessionState) -> None:
    db_exec(
        """
        UPDATE consultas
        SET session_state = %s::jsonb,
            session_status = %s,
            session_version = session_version + 1,
            updated_at = now()
        WHERE id = %s
        """,
        (
            json.dumps(asdict(session), ensure_ascii=False),
            "completed" if session.completado else "in_progress",
            session.consulta_id,
        ),
    )


def cargar_session_state(consulta_id: int) -> SessionState | None:
    row = db_fetch_one(
        """
        SELECT session_state
        FROM consultas
        WHERE id = %s
          AND session_status <> 'discarded'
        """,
        (consulta_id,),
    )
    if not row or not row["session_state"]:
        return None

    state = row["session_state"]
    if isinstance(state, str):
        state = json.loads(state)

    # Ignora claves desconocidas (estados guardados por versiones anteriores)
    known = {f.name for f in fields(SessionState)}
    return SessionState(**{k: v for k, v in state.items() if k in known})


# ── Respuesta HTTP ────────────────────────────────────────────────────────────

def to_response(
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


# ── Session processing ────────────────────────────────────────────────────────
async def run_iteration(
    session: SessionState,
) -> dict:

    historial_str = "\n".join(
        f"- {s}"
        for s in session.historial_consulta
    )

    safety_chain = await asyncio.to_thread(
        get_safety_chain,
        session.tenant_slug,
    )

    try:

        resp = await asyncio.to_thread(
            safety_chain.invoke,
            historial_str,
        )

        ev = normalize_eval(
            parse_json_safe(
                extract_text(resp.content),
                DEFAULT_EVAL.copy(),
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

        ev = normalize_eval(
            DEFAULT_EVAL.copy(),
            historial_str,
            session,
        )
    dominios = ev.get("dominios_detectados", [])
    if "agroquimicos" in dominios:
        producto = extraer_producto_fitosanitario(historial_str)
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

    await asyncio.to_thread(
        registrar_auditoria,
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
        # finalize_session es bloqueante (LLM, verificador de evidencia y DB)
        await asyncio.to_thread(finalize_session, session)

    return ev
def finalize_session(
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
        | get_llm()
    )

    try:

        eval_text = extract_text(
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

        ev_resp = get_evidence_chain().invoke(
            {
                "question": "\n".join(
                    session.historial_consulta
                ),
                "answer": eval_text,
                "context": contexto,
            }
        )

        verificacion = parse_json_safe(
            extract_text(
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
