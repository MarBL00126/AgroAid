from __future__ import annotations
import pathlib
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field
from core.database import db_fetch_all, db_fetch_one, get_conn,db_execute_returning_one
from core.deps import (
    get_tenant_id_from_user,
    get_tenant_slug_from_user,
    get_user_id_from_user,
    require_admin,
    require_any,
)
from core.pdf_receta import crear_pdf_receta
router = APIRouter(prefix="/api/recetas", tags=["Recetas agronomicas"])
class RecetaCreate(BaseModel):
    consulta_id: int | None = None
    producto: str
    principio_activo: str | None = None
    cultivo: str
    lote: str | None = None
    superficie_ha: float | None = Field(default=None, ge=0)
    dosis: str
    volumen_agua: str | None = None
    fecha_aplicacion: date | None = None
    observaciones: str | None = None
    nivel_riesgo: str | None = None
_tenant_id = get_tenant_id_from_user
_user_id = get_user_id_from_user
_tenant_slug = get_tenant_slug_from_user
def _next_numero_receta(cur) -> tuple[int, str]:
    cur.execute("SELECT nextval('recetas_agronomicas_id_seq') AS id")
    row = cur.fetchone()
    receta_id = int(row["id"] if isinstance(row, dict) else row[0])
    numero = f"RA-{date.today().year}-{receta_id:06d}"
    return receta_id, numero
def _insert_receta(
    req: RecetaCreate,
    current_user: dict,
    estado: str = "borrador",
) -> dict:
    tenant_id = _tenant_id(current_user)
    user_id = _user_id(current_user)
    with get_conn() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                receta_id, numero = _next_numero_receta(cur)
                cur.execute(
                    """
                    INSERT INTO recetas_agronomicas
                        (id, tenant_id, user_id, consulta_id, numero_receta,
                         producto, principio_activo, cultivo, lote, superficie_ha,
                         dosis, volumen_agua, fecha_aplicacion, observaciones,
                         nivel_riesgo, estado)
                    VALUES
                        (%s, %s, %s, %s, %s,
                         %s, %s, %s, %s, %s,
                         %s, %s, %s, %s,
                         %s, %s)
                    RETURNING *
                    """,
                    (
                        receta_id,
                        tenant_id,
                        user_id,
                        req.consulta_id,
                        numero,
                        req.producto,
                        req.principio_activo,
                        req.cultivo,
                        req.lote,
                        req.superficie_ha,
                        req.dosis,
                        req.volumen_agua,
                        req.fecha_aplicacion,
                        req.observaciones,
                        req.nivel_riesgo,
                        estado,
                    ),
                )
                receta = dict(cur.fetchone())
            conn.commit()
            return receta
        except Exception:
            conn.rollback()
            raise
def _update_pdf_path(receta_id: int, tenant_id: int, pdf_path: str) -> None:
    with get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE recetas_agronomicas
                    SET pdf_path = %s
                    WHERE id = %s
                      AND tenant_id = %s
                    """,
                    (pdf_path, receta_id, tenant_id),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
def create_receta_borrador(
    current_user: dict,
    producto: str,
    cultivo: str,
    dosis: str,
    consulta_id: int | None = None,
    principio_activo: str | None = None,
    nivel_riesgo: str | None = None,
    observaciones: str | None = None,
) -> dict:
    req = RecetaCreate(
        consulta_id=consulta_id,
        producto=producto,
        principio_activo=principio_activo,
        cultivo=cultivo,
        dosis=dosis,
        nivel_riesgo=nivel_riesgo,
        observaciones=observaciones,
    )
    receta = _insert_receta(req, current_user, estado="borrador")
    pdf_path = crear_pdf_receta(receta, _tenant_slug(current_user))
    _update_pdf_path(receta["id"], receta["tenant_id"], pdf_path)
    receta["pdf_path"] = pdf_path
    receta["pdf_url"] = f"/api/recetas/{receta['id']}/pdf"
    return receta
@router.post("")
def crear_receta(
    req: RecetaCreate,
    current_user: dict = Depends(require_any),
):
    receta = _insert_receta(req, current_user, estado="borrador")
    pdf_path = crear_pdf_receta(receta, _tenant_slug(current_user))
    _update_pdf_path(receta["id"], receta["tenant_id"], pdf_path)
    receta["pdf_path"] = pdf_path
    receta["pdf_url"] = f"/api/recetas/{receta['id']}/pdf"
    return receta
@router.get("")
def listar_recetas(
    current_user: dict = Depends(require_any),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    return db_fetch_all(
        """
        SELECT id, numero_receta, producto, principio_activo, cultivo, lote,
               superficie_ha, dosis, fecha_aplicacion, nivel_riesgo, estado,
               pdf_path, created_at
        FROM recetas_agronomicas
        WHERE tenant_id = %s
        ORDER BY created_at DESC, id DESC
        LIMIT %s OFFSET %s
        """,
        (_tenant_id(current_user), page_size, (page - 1) * page_size),
    )
@router.get("/{receta_id}/pdf")
def descargar_pdf_receta(
    receta_id: int,
    current_user: dict = Depends(require_any),
):
    row = db_fetch_one(
        """
        SELECT pdf_path, numero_receta
        FROM recetas_agronomicas
        WHERE id = %s
          AND tenant_id = %s
        """,
        (receta_id, _tenant_id(current_user)),
    )
    if not row or not row.get("pdf_path"):
        raise HTTPException(status_code=404, detail="PDF no encontrado")
    path = pathlib.Path(row["pdf_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Archivo PDF no encontrado")
    return FileResponse(
        str(path),
        media_type="application/pdf",
        filename=f"{row['numero_receta']}.pdf",
    )
def _cambiar_estado(receta_id: int, current_user: dict, estado: str) -> dict:
    row = db_execute_returning_one(
        """
        UPDATE recetas_agronomicas
        SET estado = %s
        WHERE id = %s
          AND tenant_id = %s
        RETURNING *
        """,
        (
            estado,
            receta_id,
            _tenant_id(current_user),
        ),
    )
    if not row:
            raise HTTPException(status_code=404, detail="Receta no encontrada")
    return row

@router.put("/{receta_id}/emitir")
def emitir_receta(
    receta_id: int,
    current_user: dict = Depends(require_admin),
):
    return _cambiar_estado(receta_id, current_user, "emitida")
@router.put("/{receta_id}/anular")
def anular_receta(
    receta_id: int,
    current_user: dict = Depends(require_admin),
):
    return _cambiar_estado(receta_id, current_user, "anulada")
