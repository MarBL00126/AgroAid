from __future__ import annotations
import asyncio
import os
import tempfile
import pathlib
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from google import genai
from google.genai import types
from core.config import GEMINI_MODEL, RATE_LIMIT_MULTIMEDIA
from core.deps import require_any
from core.limiter import limiter
from fastapi import Request
from routers.consultas import (
    CONSULTA_MAX_CHARS,
    CONSULTA_MIN_CHARS,
    ConsultaRequest,
    iniciar_consulta,
)

router = APIRouter(prefix="/api/voz", tags=["Voz"])

SUPPORTED_MIME = {
    "audio/webm", "audio/ogg", "audio/wav", "audio/mp3",
    "audio/mpeg", "audio/aac", "audio/flac", "audio/mp4",
}


def _get_client():
    return genai.Client(api_key=os.environ["GOOGLE_API_KEY"])


def _transcribir_sync(audio_bytes: bytes, mime_type: str) -> str:
    if mime_type not in SUPPORTED_MIME:
        mime_type = "audio/webm"
    client = _get_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
            "Transcribi este audio exactamente en español latinoamericano. "
            "Devuelve solo la transcripcion, sin explicaciones ni formato adicional.",
        ],
    )
    return (response.text or "").strip()


async def _transcribir_bytes(audio_bytes: bytes, mime_type: str) -> str:
    return await asyncio.to_thread(_transcribir_sync, audio_bytes, mime_type)
@router.post("/transcribir")
@limiter.limit(RATE_LIMIT_MULTIMEDIA)
async def transcribir(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(require_any),
):
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Audio vacío")
    text = await _transcribir_bytes(audio_bytes, file.content_type or "audio/webm")
    return {"text": text}
@router.post("/consulta")
@limiter.limit(RATE_LIMIT_MULTIMEDIA)
async def voz_consulta(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(require_any),
):
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Audio vacio")
    try:
        text = await _transcribir_bytes(audio_bytes, file.content_type or "audio/webm")
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=f"Error al transcribir: {exc}") from exc
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No se pudo transcribir el audio")
    text = text[:CONSULTA_MAX_CHARS]
    if len(text) < CONSULTA_MIN_CHARS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El audio es demasiado corto para generar una consulta")
    req = ConsultaRequest(
        consulta_inicial=text,
    )
    return await iniciar_consulta(req, current_user)
