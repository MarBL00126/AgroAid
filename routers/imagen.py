from __future__ import annotations
import os
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from google import genai
from google.genai import types
from core.deps import require_any
router=APIRouter(
    prefix="/api/consulta",
    tags=["Imagen"]
)
SUPPORTED_MINE ={"image/jpeg","image/jpg","image/png","image/webp","image/heic"}
LABEL_PROMPT = """
Analizá esta foto de etiqueta de agroquímico, fitosanitario o producto veterinario.
Extraé SOLO lo que sea legible en la imagen, en formato JSON:
{
  "producto": "nombre comercial visible",
  "principio_activo": "ingrediente activo",
  "cultivos_o_especies_permitidos": ["cultivo o animal"],
  "dosis_recomendada": "dosis y unidad",
  "intervalo_carencia_dias": null,
  "epp_requerido": ["guantes", "máscara", etc.],
  "categoria_toxicologica": "Ia / Ib / II / III / IV o null",
  "frases_de_seguridad": ["texto de la etiqueta"],
  "texto_completo_visible": "todo el texto legible de la etiqueta"
}
Si un campo no es legible o no aparece en la imagen, poné null.
No inventes datos. Respondé únicamente con el JSON, sin markdown ni explicaciones.
"""
def _get_client():
    return genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
@router.post("/imagen")
async def consulta_imagen(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_any),):
    mime=(file.content_type or "image/jpeg").lower()
    if mime not in SUPPORTED_MINE:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Solo se aceptan imágenes JPEG, PNG, WEBP o HEIC"
        )
    img_bytes=await file.read()
    if not img_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Imagen vacía")
    client=_get_client()
    try:
        resp=client.models.generate_content(
            model="gemini-3.6-flash",
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type=mime),
                LABEL_PROMPT,
            ])
        label_json_str =resp.text or "".strip()
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Error al analizar imagen: {exc}")
    import json, re
    label_data = {}
    try:
        clean = re.sub(r"```(?:json)?|```", "", label_json_str).strip()
        label_data = json.loads(clean)
    except json.JSONDecodeError:
        label_data = {"texto_completo_visible": label_json_str}
    producto=label_data.get("producto") or "producto no identificado"
    principio=label_data.get("principio activo") or ""
    texto_etiqueta=label_data.get("texto_completo_visible") or label_json_str
    consulta_texto = (
        f"Etiqueta analizada — Producto: {producto}. "
        f"Principio activo: {principio}. "
        f"Datos completos de la etiqueta:\n{texto_etiqueta}"
    )
    from app import ConsultaRequest, iniciar_consulta
    req = ConsultaRequest(
        consulta_inicial=consulta_texto,
        tenant_slug=current_user.get("tenant_slug", "default"),
    )
    evaluacion = await iniciar_consulta(req, current_user)
    return {
        "etiqueta_parseada": label_data,
        "consulta_generada": consulta_texto,
        "evaluacion": evaluacion,
    }
