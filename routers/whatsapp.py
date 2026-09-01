import os
import logging

import psycopg2

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
from routers.voz import _transcribir_bytes
import httpx
router = APIRouter(
    prefix="/api/whatsapp",
    tags=["whatsapp"],
)
logger = logging.getLogger("agrosafety.whatsapp")
def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", 5432)),
        database=os.environ.get("DB_NAME", "agrosafety"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
    )

def get_tenant_by_phone(phone:str):
    """
    Busca el usuario asociado al número de WhatsApp
    y obtiene su tenant.
    """
    conn=get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                 """
                SELECT tenant_id
                FROM users
                WHERE whatsapp = %s
                LIMIT 1
                """,
                (phone,)
            )
            row=cur.fetchone()
            if not row:
                return None
            return row[0]
    finally:
        conn.close()
def get_whatsapp_session(phone: str):
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT phone, consulta_id, state, tenant_id
                FROM whatsapp_sessions
                WHERE phone = %s
                """,
                (phone,),
            )

            row = cur.fetchone()

            if not row:
                return None

            return {
                "phone": row[0],
                "consulta_id": row[1],
                "state": row[2],
                "tenant_id": row[3],
            }

    finally:
        conn.close()
def create_whatsapp_session(
    phone: str,
    consulta_id: int,
    tenant_id: int,
):
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO whatsapp_sessions (
                    phone,
                    consulta_id,
                    state,
                    tenant_id
                )
                VALUES (%s, %s, 'in_progress', %s)
                ON CONFLICT (phone)
                DO UPDATE SET
                    consulta_id = EXCLUDED.consulta_id,
                    state = 'in_progress',
                    tenant_id = EXCLUDED.tenant_id,
                    updated_at = NOW()
                """,
                (
                    phone,
                    consulta_id,
                    tenant_id,
                ),
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def update_whatsapp_session(
    phone: str,
    state: str,
    consulta_id: int | None = None,
):
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE whatsapp_sessions
                SET
                    state = %s,
                    consulta_id = %s,
                    updated_at = NOW()
                WHERE phone = %s
                """,
                (
                    state,
                    consulta_id,
                    phone,
                ),
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
def twiml_response(message:str)->Response:
    response=MessagingResponse()
    response.message(message)
    return Response(
        content=str(response),
        media_type="application/xml"
    )
@router.post("/webhook")
async def whatsapp_webhook(request:Request):
    # ---------------------------------------------------------
    # 1. Leer formulario enviado por Twilio
    # ---------------------------------------------------------
    form=await request.form()
    phone=str(form.get("From","")).strip()
    body=str(form.get("Body","")).strip()
    media_url = form.get("MediaUrl0")
    media_type = form.get(
    "MediaContentType0",
    "audio/ogg",
    )
    if not phone:
        raise HTTPException(
            status_code=400,
            detail="Missing From",
        )
    if not body:
        return twiml_response(
            "No recibí ningún mensaje. Por favor escribí tu consulta."
        )
    # ---------------------------------------------------------
    # 2. Validar firma de Twilio
    # ---------------------------------------------------------

    auth_token=os.environ.get("TWILIO_AUTH_TOKEN")
    if not auth_token:
        logger.error("TWILIO_AUTH_TOKEN no está configurado.")
        raise HTTPException(
            status_code=500,
            detail="Twilio Auth Token no configurado.",
        )
    validator=RequestValidator(auth_token)
    signature = request.headers.get(
        "X-Twilio-Signature",
        "",
    )
    is_valid=validator.validate(
        str(request.url),
        dict(form),
        signature
    )
    if not is_valid:
        logger.warning(
            "Firma Twilio inválida desde %s",
            phone,
        )

        raise HTTPException(
            status_code=403,
            detail="Invalid Twilio signature",
        )
    if media_url and media_type and media_type.startswith("audio"):
        sid  = os.environ["TWILIO_ACCOUNT_SID"]
        tok  = os.environ["TWILIO_AUTH_TOKEN"]
        async with httpx.AsyncClient(auth=(sid, tok), timeout=30) as client:
            audio_resp = await client.get(media_url)
        audio_bytes=audio_resp.content
        body=await _transcribir_bytes(audio_bytes, media_type)

        

    # ---------------------------------------------------------
    # 3. Identificar tenant
    # ---------------------------------------------------------
    tenant_id = get_tenant_by_phone(phone)

    if tenant_id is None:
        return twiml_response(
            "Este número de WhatsApp no está registrado. "
            "Contactá al administrador de AgroSafety."
        )
    # ---------------------------------------------------------
    # 4. Import local para evitar circular import
    # ---------------------------------------------------------

    from app import (
        _sessions,
        _to_response,
        crear_consulta,
        registrar_auditoria,
        _run_iteration,
        SessionState,
    )
    # ---------------------------------------------------------
    # 5. Buscar sesión WhatsApp
    # ---------------------------------------------------------
    session_data=get_whatsapp_session(phone)
    # =========================================================
    # CASO A — NO EXISTE SESIÓN / IDLE
    # =========================================================
    if (
        session_data is None
        or session_data["state"] == "idle"
        or session_data["consulta_id"] is None
    ):

        consulta_id = crear_consulta(body)

        session = SessionState(
            consulta_id=consulta_id,
            umbral_confianza=80,
            max_iteraciones=5,
        )

        session.historial_consulta.append(
            f"CONSULTA INICIAL: {body}"
        )

        registrar_auditoria(
            consulta_id,
            0,
            "CONSULTA_INICIAL_WHATSAPP",
            {
                "phone": phone,
                "tenant_id": tenant_id,
                "consulta": body,
            },
        )

        await _run_iteration(session)

        _sessions[consulta_id] = session

        create_whatsapp_session(
            phone=phone,
            consulta_id=consulta_id,
            tenant_id=tenant_id,
        )

        result = _to_response(session)

        # -----------------------------------------------------
        # Si ya terminó en la primera evaluación
        # -----------------------------------------------------

        if result["completado"]:

            update_whatsapp_session(
                phone=phone,
                state="idle",
                consulta_id=None,
            )

            return twiml_response(
                result.get("evaluacion_final")
                or result.get("justificacion")
                or "La evaluación ha finalizado."
            )

        # -----------------------------------------------------
        # Continuar con preguntas
        # -----------------------------------------------------

        questions = result.get(
            "preguntas_seguimiento",
            [],
        )

        if not questions:
            return twiml_response(
                "Estoy procesando tu consulta. "
                "Por favor esperá unos instantes."
            )

        message = (
            "🌱 *AgroSafety*\n\n"
            "Recibí tu consulta.\n\n"
            "Necesito algunos datos adicionales:\n\n"
        )

        for i, question in enumerate(
            questions,
            start=1,
        ):
            message += f"{i}. {question}\n"

        return twiml_response(message)

    # =========================================================
    # CASO B — SESIÓN EN PROGRESO
    # =========================================================

    consulta_id = session_data["consulta_id"]

    session = _sessions.get(consulta_id)

    if session is None:
        logger.error(
            "Sesión %s no encontrada en memoria para WhatsApp %s",
            consulta_id,
            phone,
        )

        update_whatsapp_session(
            phone=phone,
            state="idle",
            consulta_id=None,
        )

        return twiml_response(
            "La sesión anterior ya no está disponible. "
            "Por favor enviá nuevamente tu consulta."
        )

    if session.completado:

        update_whatsapp_session(
            phone=phone,
            state="idle",
            consulta_id=None,
        )

        return twiml_response(
            session.evaluacion_final
            or "La evaluación ya fue completada."
        )

    # ---------------------------------------------------------
    # Guardar respuesta
    # ---------------------------------------------------------

    preguntas = (
        session.ultima_evaluacion or {}
    ).get(
        "preguntas_seguimiento",
        [],
    )

    from app import (
        guardar_respuesta,
    )

    guardar_respuesta(
        consulta_id,
        session.iteracion_actual,
        preguntas,
        body,
        session.confianza_final,
        session.riesgo_final,
    )

    registrar_auditoria(
        consulta_id,
        session.iteracion_actual,
        "RESPUESTA_USUARIO_WHATSAPP",
        {
            "phone": phone,
            "tenant_id": tenant_id,
            "respuesta": body,
        },
    )

    session.historial_consulta.append(
        f"Respuesta iteración "
        f"{session.iteracion_actual}: {body}"
    )

    session.historial_respuestas.append(
        {
            "iteracion": session.iteracion_actual,
            "preguntas": preguntas,
            "respuesta": body,
        }
    )

    session.iteracion_actual += 1

    # ---------------------------------------------------------
    # Ejecutar siguiente evaluación
    # ---------------------------------------------------------

    await _run_iteration(session)

    result = _to_response(session)

    # =========================================================
    # CASO C — FINALIZÓ
    # =========================================================

    if result["completado"]:

        update_whatsapp_session(
            phone=phone,
            state="idle",
            consulta_id=None,
        )

        final_text = (
            result.get("evaluacion_final")
            or result.get("justificacion")
            or "La evaluación ha finalizado."
        )

        return twiml_response(
            "🌱 *AgroSafety — Evaluación final*\n\n"
            + final_text
        )

    # =========================================================
    # CASO D — SIGUE PREGUNTANDO
    # =========================================================

    questions = result.get(
        "preguntas_seguimiento",
        [],
    )

    if not questions:
        return twiml_response(
            "Necesito más información para continuar "
            "con una evaluación segura."
        )

    message = (
        "Gracias. Necesito algunos datos más:\n\n"
    )

    for i, question in enumerate(
        questions,
        start=1,
    ):
        message += f"{i}. {question}\n"

    return twiml_response(message)
