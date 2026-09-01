from __future__ import annotations
import os
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
from routers.voz import _transcribir_bytes
from core.database import db_fetch_one, get_conn
import httpx

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])
logger = logging.getLogger("agrosafety.whatsapp")


def _get_tenant_info(phone: str):
    """Returns (tenant_id, tenant_slug) for the phone, falling back to default tenant."""
    row = db_fetch_one(
        """
        SELECT u.tenant_id, t.slug
        FROM users u
        JOIN tenants t ON t.id = u.tenant_id
        WHERE u.whatsapp = %s
        LIMIT 1
        """,
        (phone,),
    )
    if row:
        return row["tenant_id"], row["slug"]
    # Unknown number → use default tenant so anyone can consult
    default = db_fetch_one("SELECT id, slug FROM tenants WHERE slug = 'default' LIMIT 1")
    if default:
        return default["id"], default["slug"]
    return None


def _get_session(phone: str):
    return db_fetch_one(
        "SELECT phone, consulta_id, state, tenant_id FROM whatsapp_sessions WHERE phone = %s",
        (phone,),
    )


def _upsert_session(phone: str, consulta_id: int, tenant_id: int) -> None:
    with get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO whatsapp_sessions (phone, consulta_id, state, tenant_id)
                    VALUES (%s, %s, 'in_progress', %s)
                    ON CONFLICT (phone) DO UPDATE SET
                        consulta_id = EXCLUDED.consulta_id,
                        state       = 'in_progress',
                        tenant_id   = EXCLUDED.tenant_id,
                        updated_at  = NOW()
                    """,
                    (phone, consulta_id, tenant_id),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _clear_session(phone: str) -> None:
    with get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE whatsapp_sessions SET state='idle', consulta_id=NULL, updated_at=NOW() WHERE phone=%s",
                    (phone,),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _twiml(message: str) -> Response:
    resp = MessagingResponse()
    resp.message(message)
    return Response(content=str(resp), media_type="application/xml")


@router.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    phone = str(form.get("From", "")).strip()
    body = str(form.get("Body", "")).strip()
    media_url = form.get("MediaUrl0")
    media_type = str(form.get("MediaContentType0", "audio/ogg"))

    if not phone:
        raise HTTPException(status_code=400, detail="Missing From")

    # Validate Twilio signature
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not auth_token:
        raise HTTPException(status_code=500, detail="TWILIO_AUTH_TOKEN no configurado")

    validator = RequestValidator(auth_token)
    if not validator.validate(str(request.url), dict(form), request.headers.get("X-Twilio-Signature", "")):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    # Transcribe audio BEFORE the empty-body check
    if media_url and media_type.startswith("audio"):
        try:
            sid = os.environ["TWILIO_ACCOUNT_SID"]
            async with httpx.AsyncClient(auth=(sid, auth_token), timeout=30) as client:
                audio_resp = await client.get(media_url)
            body = await _transcribir_bytes(audio_resp.content, media_type)
        except Exception as exc:
            logger.warning("No se pudo transcribir audio de %s: %s", phone, exc)

    if not body:
        return _twiml("No recibi ningun mensaje. Por favor escribi tu consulta.")

    # Resolve tenant
    tenant_info = _get_tenant_info(phone)
    if tenant_info is None:
        return _twiml("El servicio no esta disponible en este momento. Intenta mas tarde.")
    tenant_id, tenant_slug = tenant_info

    # Import here to avoid circular imports at module load
    from app import (
        SessionState, _sessions, _to_response,
        crear_consulta, registrar_auditoria,
        _run_iteration, guardar_respuesta,
    )

    session_data = _get_session(phone)

    # ── CASO A: nueva consulta ────────────────────────────────────────────────
    if session_data is None or session_data["state"] == "idle" or not session_data.get("consulta_id"):
        consulta_id = crear_consulta(body, tenant_slug)

        session = SessionState(
            consulta_id=consulta_id,
            tenant_slug=tenant_slug,
            umbral_confianza=80,
            max_iteraciones=5,
        )
        session.historial_consulta.append(f"CONSULTA INICIAL: {body}")
        registrar_auditoria(consulta_id, 0, "CONSULTA_INICIAL_WHATSAPP",
                            {"phone": phone, "tenant_id": tenant_id, "consulta": body})

        await _run_iteration(session)
        _sessions[consulta_id] = session
        _upsert_session(phone, consulta_id, tenant_id)

        result = _to_response(session)
        if result["completado"]:
            _clear_session(phone)
            return _twiml(result.get("evaluacion_final") or result.get("justificacion") or "Evaluacion finalizada.")

        questions = result.get("preguntas_seguimiento", [])
        if not questions:
            return _twiml("Procesando tu consulta.")

        msg = "AgroSafety\n\nRecibi tu consulta.\nNecesito algunos datos:\n\n"
        for i, q in enumerate(questions, 1):
            msg += f"{i}. {q}\n"
        return _twiml(msg)

    # ── CASO B: sesion en progreso ────────────────────────────────────────────
    consulta_id = session_data["consulta_id"]
    session = _sessions.get(consulta_id)

    if session is None:
        # Server restarted — in-memory session lost
        logger.warning("Session %s no esta en memoria (reinicio de servidor)", consulta_id)
        _clear_session(phone)
        return _twiml("La sesion anterior no esta disponible (el servidor se reinicio). Envia tu consulta de nuevo.")

    if session.completado:
        _clear_session(phone)
        return _twiml(session.evaluacion_final or "La evaluacion ya fue completada.")

    preguntas = (session.ultima_evaluacion or {}).get("preguntas_seguimiento", [])
    guardar_respuesta(consulta_id, session.iteracion_actual, preguntas, body,
                      session.confianza_final, session.riesgo_final)
    registrar_auditoria(consulta_id, session.iteracion_actual, "RESPUESTA_USUARIO_WHATSAPP",
                        {"phone": phone, "respuesta": body})
    session.historial_consulta.append(f"Respuesta iteracion {session.iteracion_actual}: {body}")
    session.historial_respuestas.append({
        "iteracion": session.iteracion_actual,
        "preguntas": preguntas,
        "respuesta": body,
    })
    session.iteracion_actual += 1

    await _run_iteration(session)
    result = _to_response(session)

    # ── CASO C: finalizo ──────────────────────────────────────────────────────
    if result["completado"]:
        _clear_session(phone)
        final = result.get("evaluacion_final") or result.get("justificacion") or "Evaluacion finalizada."
        return _twiml(f"AgroSafety - Evaluacion final\n\n{final}")

    # ── CASO D: sigue preguntando ─────────────────────────────────────────────
    questions = result.get("preguntas_seguimiento", [])
    if not questions:
        return _twiml("Necesito mas informacion para continuar.")

    msg = "Gracias. Necesito algunos datos mas:\n\n"
    for i, q in enumerate(questions, 1):
        msg += f"{i}. {q}\n"
    return _twiml(msg)
