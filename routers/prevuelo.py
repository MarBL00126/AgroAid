from __future__ import annotations
import asyncio
import hashlib
import json
import pathlib
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from core.clima import get_clima
from core.database import db_fetch_one, get_conn
from core.deps import (
    get_tenant_id_from_user,
    get_tenant_slug_from_user,
    get_user_id_from_user,
    require_any,
)
router = APIRouter(prefix="/api", tags=["Pre-aplicacion"])
class PreAplicacionRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    producto: str
    dosis_l_ha: float | None = Field(default=None, ge=0)
    cultivo: str | None = None
    distancia_agua_m: float = Field(..., ge=0)
    hora_aplicacion: datetime | None = None
    tipo_equipo: str = "terrestre"
    epp_disponible: list[str] = []
_tenant_id = get_tenant_id_from_user
_user_id = get_user_id_from_user
_tenant_slug = get_tenant_slug_from_user
def _normalizar_epp(items: list[str]) -> set[str]:
    normalizados = set()
    for item in items or []:
        value = item.strip().lower()
        normalizados.add(value)
        if value == "mascara":
            normalizados.add("máscara")
        if value == "máscara":
            normalizados.add("mascara")
    return normalizados
async def evaluar_pre_aplicacion(req: PreAplicacionRequest) -> dict:
    clima = await get_clima(req.lat, req.lon)
    viento = float(clima.get("wind") or 0)
    lluvia = float(clima.get("rain") or 0)
    checks = []
    go = True
    if viento > 15:
        checks.append({
            "check": "viento",
            "resultado": "NO-GO",
            "detalle": f"Viento {viento:.1f} km/h - maximo permitido 15 km/h",
        })
        go = False
    else:
        checks.append({
            "check": "viento",
            "resultado": "GO",
            "detalle": f"Viento {viento:.1f} km/h - dentro del limite",
        })
    if lluvia > 0:
        checks.append({
            "check": "lluvia",
            "resultado": "NO-GO",
            "detalle": f"Precipitacion actual {lluvia:.1f} mm - no aplicar",
        })
        go = False
    else:
        checks.append({
            "check": "lluvia",
            "resultado": "GO",
            "detalle": "Sin precipitacion actual registrada",
        })
    if req.distancia_agua_m < 50:
        checks.append({
            "check": "distancia_agua",
            "resultado": "NO-GO",
            "detalle": f"Solo {req.distancia_agua_m:.0f} m del agua - minimo 50 m",
        })
        go = False
    else:
        checks.append({
            "check": "distancia_agua",
            "resultado": "GO",
            "detalle": f"{req.distancia_agua_m:.0f} m a agua - cumple minimo",
        })
    epp = _normalizar_epp(req.epp_disponible)
    epp_minimo = ["guantes", "mascara"]
    faltante = [item for item in epp_minimo if item not in epp]
    if faltante:
        checks.append({
            "check": "epp",
            "resultado": "NO-GO",
            "detalle": f"Falta EPP: {', '.join(faltante)}",
        })
        go = False
    else:
        checks.append({
            "check": "epp",
            "resultado": "GO",
            "detalle": "EPP minimo disponible",
        })
    equipo = (req.tipo_equipo or "terrestre").lower()
    factor_equipo = 1.5 if equipo == "drone" else 1.0
    deriva_m = viento * 0.5 * factor_equipo
    if deriva_m > req.distancia_agua_m * 0.3:
        checks.append({
            "check": "deriva",
            "resultado": "PRECAUCION",
            "detalle": (
                f"Deriva estimada {deriva_m:.0f} m - revisar direccion de viento"
            ),
        })
    else:
        checks.append({
            "check": "deriva",
            "resultado": "GO",
            "detalle": f"Deriva estimada {deriva_m:.0f} m",
        })
    return {
        "resultado_global": "GO" if go else "NO-GO",
        "hora_evaluacion": datetime.now(timezone.utc).isoformat(),
        "clima": clima,
        "checks": checks,
        "recomendacion": (
            "Proceder con precaucion" if go else "No aplicar en estas condiciones"
        ),
    }
def _entry_hash(detalle: dict, prev_hash: str | None) -> str:
    raw = json.dumps(
        {"detalle": detalle, "prev_hash": prev_hash},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
def _build_pdf(path: pathlib.Path, req: PreAplicacionRequest, detalle: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    story = [
        Paragraph("Evaluacion pre-aplicacion GO/NO-GO", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Producto: {req.producto}", styles["Normal"]),
        Paragraph(f"Cultivo: {req.cultivo or '-'}", styles["Normal"]),
        Paragraph(f"Resultado global: {detalle['resultado_global']}", styles["Heading2"]),
        Paragraph(f"Recomendacion: {detalle['recomendacion']}", styles["Normal"]),
        Spacer(1, 12),
    ]
    rows = [["Check", "Resultado", "Detalle"]]
    rows.extend(
        [c["check"], c["resultado"], c["detalle"]]
        for c in detalle["checks"]
    )
    table = Table(rows, colWidths=[95, 90, 310])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dcfce7")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#94a3b8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 12))
    story.append(Paragraph("Clima consultado", styles["Heading2"]))
    story.append(Paragraph(json.dumps(detalle["clima"], ensure_ascii=False), styles["Normal"]))
    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            "Documento generado por AgroAid. No reemplaza criterio profesional, "
            "etiqueta oficial ni normativa local vigente.",
            styles["Italic"],
        )
    )
    doc.build(story)
def _insert_pre_aplicacion(
    req: PreAplicacionRequest,
    detalle: dict,
    current_user: dict,
    pdf_path: str | None,
) -> dict:
    tenant_id = _tenant_id(current_user)
    user_id = _user_id(current_user)
    prev = db_fetch_one(
        """
        SELECT entry_hash
        FROM pre_aplicaciones
        WHERE tenant_id = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (tenant_id,),
    )
    prev_hash = prev["entry_hash"] if prev else None
    entry_hash = _entry_hash(detalle, prev_hash)   
    with get_conn() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO pre_aplicaciones
                        (tenant_id, user_id, lat, lon, producto, dosis_l_ha,
                         cultivo, distancia_agua_m, hora_aplicacion, tipo_equipo,
                         resultado_global, detalle, pdf_path, entry_hash, prev_hash)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                         %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        tenant_id,
                        user_id,
                        req.lat,
                        req.lon,
                        req.producto,
                        req.dosis_l_ha,
                        req.cultivo,
                        req.distancia_agua_m,
                        req.hora_aplicacion,
                        req.tipo_equipo,
                        detalle["resultado_global"],
                        json.dumps(detalle, ensure_ascii=False, default=str),
                        pdf_path,
                        entry_hash,
                        prev_hash,
                    ),
                )
                row = dict(cur.fetchone())
            conn.commit()
            return row
        except Exception:
            conn.rollback()
            raise
def _update_pdf_path(pre_aplicacion_id: int, pdf_path: str) -> None:
    with get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE pre_aplicaciones SET pdf_path = %s WHERE id = %s",
                    (pdf_path, pre_aplicacion_id),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
@router.post("/pre-aplicacion")
async def crear_pre_aplicacion(
    req: PreAplicacionRequest,
    current_user: dict = Depends(require_any),
):
    detalle = await evaluar_pre_aplicacion(req)
    tenant_slug = _tenant_slug(current_user)
    row = await asyncio.to_thread(_insert_pre_aplicacion, req, detalle, current_user, None)
    pdf_rel = pathlib.Path("data") / tenant_slug / "prevuelo" / f"pre_aplicacion_{row['id']}.pdf"
    await asyncio.to_thread(_build_pdf, pdf_rel, req, detalle)
    await asyncio.to_thread(_update_pdf_path, row["id"], str(pdf_rel))
    row["pdf_path"] = str(pdf_rel)
    row["pdf_url"] = f"/api/pre-aplicacion/{row['id']}/pdf"
    return {"evaluacion": detalle, "registro": row}
@router.get("/pre-aplicacion/{pre_aplicacion_id}/pdf")
def descargar_pre_aplicacion_pdf(
    pre_aplicacion_id: int,
    current_user: dict = Depends(require_any),
):
    row = db_fetch_one(
        """
        SELECT pdf_path
        FROM pre_aplicaciones
        WHERE id = %s
          AND tenant_id = %s
        """,
        (pre_aplicacion_id, _tenant_id(current_user)),
    )
    if not row or not row.get("pdf_path"):
        raise HTTPException(status_code=404, detail="PDF no encontrado")
    path = pathlib.Path(row["pdf_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Archivo PDF no encontrado")
    return FileResponse(str(path), media_type="application/pdf", filename=path.name)