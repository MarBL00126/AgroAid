from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import date
from io import StringIO, BytesIO
import csv

from openpyxl import Workbook

from core.database import db_fetch_all
from core.deps import require_admin


router = APIRouter(
    prefix="/api",
    tags=["dashboard"],
)


# ============================================================
# MODELOS
# ============================================================

class WebhookCreate(BaseModel):
    url: HttpUrl
    secret: str
    events: list[str] = []
    is_active: bool = True

# ============================================================
# WHITE-LABEL / BRANDING
# ============================================================

class BrandingUpdate(BaseModel):
    logo_url:Optional[str]=None
    primary_color:Optional[str]=None
    accent_color:Optional[str]=None
    app_name:Optional[str]=None
    footer_text:Optional[str]=None
@router.get("/branding")
async def get_branding(
    slug: str = Query(..., description="Slug del tenant"),
):
    rows=db_fetch_all(
    """
        SELECT
            tb.logo_url,
            tb.primary_color,
            tb.accent_color,
            tb.app_name,
            tb.footer_text
        FROM tenant_branding tb
        JOIN tenants t ON t.id = tb.tenant_id
        WHERE t.slug = %s
        """,
        (slug,),
    )
    if not rows:
        raise HTTPException(
          status_code=404,
            detail="Branding no encontrado",
        )
    return rows[0]
@router.put("/branding")
async def put_branding(
    data: BrandingUpdate,
    admin = Depends(require_admin),
):
    tenant_id=admin["tenant_id"]
    rows=db_fetch_all(
        """
        INSERT INTO tenant_branding (
            tenant_id,
            logo_url,
            primary_color,
            accent_color,
            app_name,
            footer_text
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id)
        DO UPDATE SET
            logo_url = EXCLUDED.logo_url,
            primary_color = EXCLUDED.primary_color,
            accent_color = EXCLUDED.accent_color,
            app_name = EXCLUDED.app_name,
            footer_text = EXCLUDED.footer_text
        RETURNING
            tenant_id,
            logo_url,
            primary_color,
            accent_color,
            app_name,
            footer_text
        """,
        (
            tenant_id,
            data.logo_url,
            data.primary_color,
            data.accent_color,
            data.app_name,
            data.footer_text
            
        ),
    )
    if not rows:
            raise HTTPException(
              status_code=500,
                detail="No se pudo actualizar el branding",
            )
    return rows[0]

     


# ============================================================
# DASHBOARD
# ============================================================

@router.get("/dashboard")
async def get_dashboard(
    admin=Depends(require_admin),
):
    """
    Devuelve los datos necesarios para el dashboard
    administrativo.
    """

    tenant_id = admin["tenant_id"]

    # --------------------------------------------------------
    # Consultas por día - últimos 30 días
    # --------------------------------------------------------

    consultas_por_dia = db_fetch_all(
        """
        SELECT
            DATE(created_at) AS fecha,
            COUNT(*) AS total
        FROM consultas
        WHERE tenant_id = %s
          AND created_at >= CURRENT_DATE - INTERVAL '29 days'
        GROUP BY DATE(created_at)
        ORDER BY fecha
        """,
        (tenant_id,),
    )

    # --------------------------------------------------------
    # Distribución de riesgo
    # --------------------------------------------------------

    distribucion_riesgo = db_fetch_all(
        """
        SELECT
            nivel_riesgo,
            COUNT(*) AS total
        FROM metricas_seguridad
        WHERE tenant_id = %s
        GROUP BY nivel_riesgo
        ORDER BY nivel_riesgo
        """,
        (tenant_id,),
    )

    # --------------------------------------------------------
    # KPIs
    # --------------------------------------------------------

    kpis = db_fetch_all(
        """
        SELECT
            COUNT(*) AS total,
            COALESCE(
                AVG(
                    CASE
                        WHEN se_abstuvo = TRUE THEN 1.0
                        ELSE 0.0
                    END
                ),
                0
            ) AS tasa_abstencion,
            COALESCE(
                AVG(confianza_final),
                0
            ) AS confianza_promedio
        FROM metricas_seguridad
        WHERE tenant_id = %s
        """,
        (tenant_id,),
    )

    return {
        "consultas_por_dia": consultas_por_dia,
        "distribucion_riesgo": distribucion_riesgo,
        "kpis": kpis[0] if kpis else {
            "total": 0,
            "tasa_abstencion": 0,
            "confianza_promedio": 0,
        },
    }


# ============================================================
# HISTORIAL
# ============================================================

def _build_historial_filters(
    tenant_id: int,
    fecha_desde: Optional[date],
    fecha_hasta: Optional[date],
    nivel_riesgo: Optional[str],
):
    """
    Construye el WHERE del historial utilizando parámetros
    SQL para evitar inyección.
    """

    conditions = [
        "tenant_id = %s"
    ]

    params = [
        tenant_id
    ]

    if fecha_desde:
        conditions.append(
            "fecha_consulta >= %s"
        )
        params.append(fecha_desde)

    if fecha_hasta:
        # La fecha_hasta se interpreta como inclusiva.
        conditions.append(
            "fecha_consulta < (%s + INTERVAL '1 day')"
        )
        params.append(fecha_hasta)

    if nivel_riesgo:
        conditions.append(
            "nivel_riesgo = %s"
        )
        params.append(nivel_riesgo)

    return " AND ".join(conditions), params


@router.get("/historial")
async def get_historial(
    page: int = Query(
        1,
        ge=1,
        description="Número de página",
    ),
    per_page: int = Query(
        20,
        ge=1,
        le=100,
        description="Cantidad de registros por página",
    ),
    fecha_desde: Optional[date] = Query(
        None,
        description="Fecha inicial",
    ),
    fecha_hasta: Optional[date] = Query(
        None,
        description="Fecha final",
    ),
    nivel_riesgo: Optional[str] = Query(
        None,
        description="Nivel de riesgo",
    ),
    admin=Depends(require_admin),
):
    """
    Historial paginado de consultas del tenant autenticado.
    """

    tenant_id = admin["tenant_id"]

    if (
        fecha_desde is not None
        and fecha_hasta is not None
        and fecha_desde > fecha_hasta
    ):
        raise HTTPException(
            status_code=400,
            detail="fecha_desde no puede ser posterior a fecha_hasta",
        )

    where, params = _build_historial_filters(
        tenant_id,
        fecha_desde,
        fecha_hasta,
        nivel_riesgo,
    )

    # --------------------------------------------------------
    # TOTAL DE REGISTROS
    # --------------------------------------------------------

    total_rows = db_fetch_all(
        f"""
        SELECT COUNT(*) AS total
        FROM historial_consultas
        WHERE {where}
        """,
        tuple(params),
    )

    total = (
        total_rows[0]["total"]
        if total_rows
        else 0
    )

    # --------------------------------------------------------
    # PAGINACIÓN
    # --------------------------------------------------------

    offset = (page - 1) * per_page

    rows = db_fetch_all(
        f"""
        SELECT
            consulta_id,
            consulta_inicial,
            fecha_consulta,
            se_abstuvo,
            nivel_riesgo,
            confianza_final,
            evidencia_suficiente,
            iteraciones,
            duracion_seg
        FROM historial_consultas
        WHERE {where}
        ORDER BY fecha_consulta DESC
        LIMIT %s
        OFFSET %s
        """,
        tuple(params + [per_page, offset]),
    )

    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": (
            (total + per_page - 1) // per_page
            if total
            else 0
        ),
        "items": rows,
    }


# ============================================================
# HISTORIAL - EXPORTACIÓN
# ============================================================

async def _get_historial_export(
    tenant_id: int,
    fecha_desde: Optional[date],
    fecha_hasta: Optional[date],
    nivel_riesgo: Optional[str],
):
    """
    Obtiene el historial completo filtrado para exportación.
    """

    if (
        fecha_desde is not None
        and fecha_hasta is not None
        and fecha_desde > fecha_hasta
    ):
        raise HTTPException(
            status_code=400,
            detail="fecha_desde no puede ser posterior a fecha_hasta",
        )

    where, params = _build_historial_filters(
        tenant_id,
        fecha_desde,
        fecha_hasta,
        nivel_riesgo,
    )

    return db_fetch_all(
        f"""
        SELECT
            consulta_id,
            consulta_inicial,
            fecha_consulta,
            se_abstuvo,
            nivel_riesgo,
            confianza_final,
            evidencia_suficiente,
            iteraciones,
            duracion_seg
        FROM historial_consultas
        WHERE {where}
        ORDER BY fecha_consulta DESC
        """,
        tuple(params),
    )


@router.get("/historial/export")
async def export_historial(
    format: str = Query(
        ...,
        pattern="^(csv|xlsx)$",
        description="Formato de exportación",
    ),
    fecha_desde: Optional[date] = Query(
        None,
        description="Fecha inicial",
    ),
    fecha_hasta: Optional[date] = Query(
        None,
        description="Fecha final",
    ),
    nivel_riesgo: Optional[str] = Query(
        None,
        description="Nivel de riesgo",
    ),
    admin=Depends(require_admin),
):
    """
    Exporta el historial del tenant autenticado
    en CSV o XLSX.
    """

    tenant_id = admin["tenant_id"]

    rows = await _get_historial_export(
        tenant_id,
        fecha_desde,
        fecha_hasta,
        nivel_riesgo,
    )

    # ========================================================
    # CSV
    # ========================================================

    if format == "csv":

        output = StringIO()

        fieldnames = [
            "consulta_id",
            "consulta_inicial",
            "fecha_consulta",
            "se_abstuvo",
            "nivel_riesgo",
            "confianza_final",
            "evidencia_suficiente",
            "iteraciones",
            "duracion_seg",
        ]

        writer = csv.DictWriter(
            output,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for row in rows:
            writer.writerow({
                field: row.get(field)
                for field in fieldnames
            })

        output.seek(0)

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition":
                    "attachment; filename=historial_consultas.csv"
            },
        )

    # ========================================================
    # XLSX
    # ========================================================

    wb = Workbook()

    ws = wb.active
    ws.title = "Historial"

    headers = [
        "Consulta ID",
        "Consulta inicial",
        "Fecha",
        "Abstención",
        "Nivel de riesgo",
        "Confianza",
        "Evidencia suficiente",
        "Iteraciones",
        "Duración (seg)",
    ]

    ws.append(headers)

    for row in rows:
        ws.append([
            row.get("consulta_id"),
            row.get("consulta_inicial"),
            row.get("fecha_consulta"),
            row.get("se_abstuvo"),
            row.get("nivel_riesgo"),
            row.get("confianza_final"),
            row.get("evidencia_suficiente"),
            row.get("iteraciones"),
            row.get("duracion_seg"),
        ])

    # --------------------------------------------------------
    # Ancho de columnas
    # --------------------------------------------------------

    widths = {
        "A": 14,
        "B": 60,
        "C": 25,
        "D": 14,
        "E": 18,
        "F": 14,
        "G": 24,
        "H": 14,
        "I": 18,
    }

    for column, width in widths.items():
        ws.column_dimensions[column].width = width

    buffer = BytesIO()

    wb.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition":
                "attachment; filename=historial_consultas.xlsx"
        },
    )


# ============================================================
# WEBHOOKS - LISTAR
# ============================================================

@router.get("/webhooks")
async def list_webhooks(
    admin=Depends(require_admin),
):
    """
    Lista los webhooks configurados para el tenant.
    """

    tenant_id = admin["tenant_id"]

    return db_fetch_all(
        """
        SELECT
            id,
            url,
            events,
            is_active,
            created_at
        FROM webhooks
        WHERE tenant_id = %s
        ORDER BY id DESC
        """,
        (tenant_id,),
    )


# ============================================================
# WEBHOOKS - CREAR
# ============================================================

@router.post("/webhooks")
async def create_webhook(
    data: WebhookCreate,
    admin=Depends(require_admin),
):
    """
    Crea un nuevo webhook para el tenant.
    """

    tenant_id = admin["tenant_id"]

    rows = db_fetch_all(
        """
        INSERT INTO webhooks
        (
            tenant_id,
            url,
            secret,
            events,
            is_active
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING
            id,
            url,
            events,
            is_active,
            created_at
        """,
        (
            tenant_id,
            str(data.url),
            data.secret,
            data.events,
            data.is_active,
        ),
    )

    return rows[0]


# ============================================================
# WEBHOOKS - ELIMINAR
# ============================================================

@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: int,
    admin=Depends(require_admin),
):
    """
    Elimina un webhook del tenant actual.
    """

    tenant_id = admin["tenant_id"]

    rows = db_fetch_all(
        """
        DELETE FROM webhooks
        WHERE id = %s
          AND tenant_id = %s
        RETURNING id
        """,
        (
            webhook_id,
            tenant_id,
        ),
    )

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Webhook no encontrado",
        )

    return {
        "ok": True,
        "id": rows[0]["id"],
    }

