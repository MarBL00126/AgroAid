from __future__ import annotations
import os, tempfile, pathlib
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from google import genai
from google.genai import types
from core.deps import require_any
from fastapi import Request as FastAPIRequest
router=APIRouter(
    prefix="/api/voz",
    tags=["Voz"]
)
SUPPORTED_MINE ={"audio/webm","audio/ogg","audio/wav","audio/mp3"
                 "audio/mpeg","audio/aac","audio/flac","audio/mp4"
                }
def _get_client():
    return genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
async def _transcribir_bytes(audio_bytes:bytes,mime_type:str)->str:
    if mime_type not in SUPPORTED_MINE:
        mime_type="audio/webm"
    client=_get_client()
    response=client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                   types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                "Transcribí este audio exactamente en español latinoamericano. "
                "Devolvé solo la transcripción, sin explicaciones ni formato adicional.",
            ])
    return (response.text or "").strip()
@router.post("/transcribir")
async def transcribir(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_any),
):
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Audio vacío")
    text = await _transcribir_bytes(audio_bytes, file.content_type or "audio/webm")
    return {"text": text}
@router.post("/consulta")
async def voz_consulta(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_any),
):
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,"Audio vacio")
    text=await _transcribir_bytes(audio_bytes,file.content_type or "audio/webm")
    if not text:
        raise HTTPException(status.HTTP_UNPROCESSABLE_ENTITY,"No se pudo transmitir")
    # Reutilizar la lógica de /api/consulta directamente
    # (importar las funciones de app.py o duplicar el flujo aquí)
    from app import iniciar_consulta,ConsultaRequest
    req=ConsultaRequest(
        consulta_inicial=text,
        tenant_slug=current_user.get("tenant_slug", "default"),
    )
    return await iniciar_consulta(req,current_user)
