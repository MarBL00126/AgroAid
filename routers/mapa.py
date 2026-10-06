from __future__ import annotations
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from core.database import (
    db_execute_returning_one_async,
    db_fetch_all_async,
)
from core.deps import (
    get_tenant_id_from_user,
    get_user_id_from_user,
    require_admin,
    require_any,
)
from core.webhook import dispatch_webhook

router = APIRouter(prefix="/api/mapa", tags=["Mapa fitosanitario"])
TipoEvento=Literal["plaga","enfermedad","contaminacion","incendio"]
RIESGO_POR_TIPO={
    "plaga":"ALTO",
    "enfermedad":"ALTO",
    "contaminacion":"CRITICO",
    "incendio":"CRITICO",
}

class EventoCreate(BaseModel):
    lat:float=Field(..., ge=-90, le=90)
    lon:float=Field(..., ge=-180, le=180)
    tipo:TipoEvento
    descripcion: str | None = Field(default=None, max_length=2000)
    nivel_riesgo:str| None=None
    radio_km:float= Field(default=5, gt=0, le=200)

_tenant_id = get_tenant_id_from_user
_user_id = get_user_id_from_user

@router.post("/eventos")
async def crear_evento(
    req:EventoCreate,
    current_user:dict = Depends(require_any),
):
    tenant_id=_tenant_id(current_user)
    user_id=_user_id(current_user)
    nivel=(req.nivel_riesgo or RIESGO_POR_TIPO[req.tipo]).upper()
    evento = await db_execute_returning_one_async(
        """
        INSERT INTO eventos_fitosanitarios
            (tenant_id, user_id, lat, lon, tipo, descripcion,
             nivel_riesgo, radio_km)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, tenant_id, user_id, lat, lon, tipo, descripcion,
                  nivel_riesgo, radio_km, verificado, created_at
        """,
        (
            tenant_id,
            user_id,
            req.lat,
            req.lon,
             req.tipo,
            req.descripcion,
            nivel,
            req.radio_km,
        ),
    )
    if nivel in {"ALTO","CRITICO"}:
        await dispatch_webhook(
            tenant_id,
            "evento_fitosanitario",
            {
                "evento_id":evento["id"],
                "tipo":evento["tipo"],
                "nivel_riesgo":evento["nivel_riesgo"],
                "lat": evento["lat"],
                "lon": evento["lon"],
                "descripcion": evento["descripcion"],   
            } 
        )
    return evento
@router.get("/eventos")
async def listar_eventos(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radio_km: float = Query(default=50, gt=0, le=500),
    current_user: dict = Depends(require_any),
):
    tenant_id=_tenant_id(current_user)
    return await db_fetch_all_async(
        """
        SELECT *
        FROM (
            SELECT
                e.id, e.tenant_id, e.user_id, e.lat, e.lon, e.tipo,
                e.descripcion, e.nivel_riesgo, e.radio_km, e.verificado,
                e.created_at,
                6371 * acos(
                    LEAST(
                        1,
                        GREATEST(
                            -1,
                            cos(radians(%s)) * cos(radians(e.lat)) *
                            cos(radians(e.lon) - radians(%s)) +
                            sin(radians(%s)) * sin(radians(e.lat))
                        )
                    )
                ) AS distancia_km
            FROM eventos_fitosanitarios e
            WHERE e.tenant_id = %s
        ) q
        WHERE q.distancia_km <= %s
        ORDER BY q.distancia_km ASC
        LIMIT 200
        """,
        (lat, lon, lat, tenant_id, radio_km),
    )
@router.put("/eventos/{evento_id}/verificar")
async def verificar_evento(
    evento_id:int,
    current_user: dict = Depends(require_admin),
):
    tenant_id=_tenant_id(current_user)
    evento = await db_execute_returning_one_async(
        """
        UPDATE eventos_fitosanitarios
        SET verificado = TRUE
        WHERE id = %s
          AND tenant_id = %s
        RETURNING id, tenant_id, user_id, lat, lon, tipo, descripcion,
                  nivel_riesgo, radio_km, verificado, created_at
        """,
        (evento_id,tenant_id)
    )
    if not evento:
        raise HTTPException(status_code=404,detail="Evento no encontrado")
    return evento