"""
routers/consultas.py
====================
Endpoints de consulta con sesión (/api/consulta/...) y evaluación stateless
(/api/risk-score).

El estado de la sesión se persiste en PostgreSQL (ver core.session_service),
por lo que cualquier worker puede continuar una consulta iniciada en otro.
"""
from __future__ import annotations

import asyncio
import logging
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.ai_chains import (
    get_safety_chain,
    extract_text,
    is_ai_ready,
    parse_json_safe,
)
from core.clima import get_clima as _fetch_clima
from core.config import (
    RATE_LIMIT_CONSULTA,
    RATE_LIMIT_RESPONDER,
    RATE_LIMIT_RISK_SCORE,
)
from core.consulta_repo import (
    crear_consulta,
    guardar_respuesta,
    registrar_auditoria,
)
from core.deps import require_any
from core.domain_rules import DEFAULT_EVAL, normalize_eval
from core.limiter import limiter
from core.pdf_service import build_pdf_bytes
from core.session_service import (
    SessionState,
    cargar_session_state,
    descartar_session_state,
    guardar_session_state,
    run_iteration,
    to_response,
)

logger = logging.getLogger("agrosafety.consultas")

router = APIRouter(
    prefix="/api/consulta",
    tags=["Consultas"],
)

risk_router = APIRouter(
    prefix="/api",
    tags=["Consultas"],
)

CONSULTA_MIN_CHARS = 10
CONSULTA_MAX_CHARS = 2000
RESPUESTA_MAX_CHARS = 2000


# ── Modelos de request ────────────────────────────────────────────────────────

class ConsultaRequest(BaseModel):

    consulta_inicial: str = Field(
        ...,
        min_length=CONSULTA_MIN_CHARS,
        max_length=CONSULTA_MAX_CHARS,
    )

    umbral_confianza: int = Field(default=80, ge=50, le=100)

    max_iteraciones: int = Field(default=5, ge=1, le=10)

    # Opcional: si se envía, debe coincidir con el tenant del usuario autenticado.
    tenant_slug: str | None = Field(
        default=None,
        pattern=r"^[a-z0-9_\-]{1,50}$",
    )

    lat: float | None = Field(default=None, ge=-90, le=90)

    lon: float | None = Field(default=None, ge=-180, le=180)


class RespuestaRequest(BaseModel):

    respuesta: str = Field(..., max_length=RESPUESTA_MAX_CHARS)


def _require_ai() -> None:

    if not is_ai_ready():

        raise HTTPException(
            503,
            (
                "Sistema no inicializado. "
                "Verificar GOOGLE_API_KEY "
                "y reiniciar el servidor."
            ),
        )


def _user_tenant_slug(current_user: dict) -> str:

    return (current_user.get("tenant_slug") or "default").strip() or "default"


def _load_owned_session(
    consulta_id: int,
    current_user: dict,
) -> SessionState:
    """Carga la sesión; si es de otro tenant responde 404 para no revelar su existencia."""

    session = cargar_session_state(consulta_id)

    guest_id = current_user.get("guest_id")

    if (
        session is None
        or session.tenant_slug != _user_tenant_slug(current_user)
        # Un invitado solo accede a las consultas de su propia sesión
        or (guest_id is not None and session.owner != guest_id)
    ):

        raise HTTPException(
            404,
            f"Consulta {consulta_id} no encontrada.",
        )

    return session


# ── Consulta con sesión ───────────────────────────────────────────────────────

@router.post("")
@limiter.limit(RATE_LIMIT_CONSULTA)
async def iniciar_consulta_endpoint(
    request: Request,
    req: ConsultaRequest,
    current_user: dict = Depends(require_any),
):
    return await iniciar_consulta(req, current_user)


async def iniciar_consulta(
    req: ConsultaRequest,
    current_user: dict,
):
    """Lógica de alta de consulta; la reutilizan voz e imagen (con su propio rate limit)."""

    _require_ai()

    tenant_slug = _user_tenant_slug(current_user)

    if req.tenant_slug is not None and req.tenant_slug != tenant_slug:

        raise HTTPException(
            403,
            "tenant_slug no coincide con el tenant del usuario.",
        )

    consulta_id = await asyncio.to_thread(
        crear_consulta,
        req.consulta_inicial,
        tenant_slug,
    )

    session = SessionState(

        consulta_id=consulta_id,

        tenant_slug=tenant_slug,

        umbral_confianza=req.umbral_confianza,

        max_iteraciones=req.max_iteraciones,

        owner=current_user.get("guest_id"),
    )

    session.historial_consulta.append(
        f"CONSULTA INICIAL: "
        f"{req.consulta_inicial}"
    )

    if req.lat is not None and req.lon is not None:

        try:

            clima = await _fetch_clima(
                req.lat,
                req.lon,
            )

            session.historial_consulta.append(
                f"CLIMA: {clima}"
            )

        except Exception as exc:

            logger.warning(
                "No se pudo obtener el clima | consulta=%s: %s",
                consulta_id,
                exc,
            )

    await asyncio.to_thread(
        registrar_auditoria,
        consulta_id,
        0,
        "CONSULTA_INICIAL",
        {
            "consulta": req.consulta_inicial
        },
    )

    await run_iteration(
        session
    )

    await asyncio.to_thread(guardar_session_state, session)

    return to_response(
        session
    )


@router.post(
    "/{consulta_id}/responder"
)
@limiter.limit(RATE_LIMIT_RESPONDER)
async def responder_consulta(
    request: Request,
    consulta_id: int,
    req: RespuestaRequest,
    current_user: dict = Depends(require_any),
):

    _require_ai()

    session = await asyncio.to_thread(_load_owned_session, consulta_id, current_user)

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

    await asyncio.to_thread(
        guardar_respuesta,
        consulta_id,
        session.iteracion_actual,
        preguntas,
        req.respuesta,
        session.confianza_final,
        session.riesgo_final,
    )

    await asyncio.to_thread(
        registrar_auditoria,
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

    await run_iteration(
        session
    )

    await asyncio.to_thread(guardar_session_state, session)

    return to_response(
        session
    )


@router.get(
    "/{consulta_id}/pdf"
)
async def descargar_pdf_consulta(
    consulta_id: int,
    current_user: dict = Depends(require_any),
):

    session = await asyncio.to_thread(_load_owned_session, consulta_id, current_user)

    pdf_bytes = await asyncio.to_thread(
        build_pdf_bytes,
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


@router.get(
    "/{consulta_id}"
)
async def get_consulta(
    consulta_id: int,
    current_user: dict = Depends(require_any),
):

    session = await asyncio.to_thread(_load_owned_session, consulta_id, current_user)

    return to_response(
        session
    )


@router.delete(
    "/{consulta_id}"
)
async def descartar_consulta(
    consulta_id: int,
    current_user: dict = Depends(require_any),
):
    """Descarta la sesión. No borra datos de la DB."""
    await asyncio.to_thread(_load_owned_session, consulta_id, current_user)
    await asyncio.to_thread(descartar_session_state, consulta_id)
    return {"ok": True, "consulta_id": consulta_id}


# ── Stateless Risk Score ──────────────────────────────────────────────────────

@risk_router.get("/risk-score")
@limiter.limit(RATE_LIMIT_RISK_SCORE)
async def risk_score(
    request: Request,
    q: str = Query(
        ...,
        min_length=1,
        max_length=CONSULTA_MAX_CHARS,
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

    if not is_ai_ready():

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

        # Endpoint stateless: usamos el tenant por defecto.
        safety_chain = await asyncio.to_thread(
            get_safety_chain,
            "default",
        )

        resp = await asyncio.to_thread(
            safety_chain.invoke,
            query,
        )

        ev = parse_json_safe(
            extract_text(
                resp.content
            ),
            DEFAULT_EVAL.copy(),
        )

        ev = normalize_eval(
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
