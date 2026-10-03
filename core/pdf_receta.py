from __future__ import annotations
import pathlib
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from core.database import db_fetch_one
def _safe_slug(value: str) -> str:
    value = (value or "default").strip().lower()
    return re.sub(r"[^a-z0-9_-]+", "-", value).strip("-") or "default"
def _text(value) -> str:
    return "" if value is None else str(value)
def crear_pdf_receta(receta: dict, tenant_slug: str = "default") -> str:
    safe_slug = _safe_slug(tenant_slug)
    numero = receta["numero_receta"]
    out_dir = pathlib.Path("data") / safe_slug / "recetas"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{numero}.pdf"
    branding = db_fetch_one(
        """
        SELECT app_name, footer_text, primary_color, accent_color, logo_url
        FROM tenant_branding
        WHERE tenant_id = %s
        """,
        (receta["tenant_id"],),
    ) or {}
    app_name = branding.get("app_name") or "AgroAid"
    footer = (
        "Documento generado por AgroAid - "
        "NO reemplaza firma profesional habilitada"
    )
    primary = branding.get("primary_color") or "#16a34a"
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        rightMargin=42,
        leftMargin=42,
        topMargin=42,
        bottomMargin=42,
    )
    story = [
        Paragraph(app_name, styles["Title"]),
        Paragraph("Receta agronomica electronica", styles["Heading1"]),
        Spacer(1, 10),
        Paragraph(f"Numero: <b>{numero}</b>", styles["Normal"]),
        Paragraph(f"Estado: <b>{receta.get('estado', 'borrador')}</b>", styles["Normal"]),
        Paragraph(f"Fecha de emision: {_text(receta.get('created_at'))}", styles["Normal"]),
        Spacer(1, 12),
    ]
    rows = [
        ["Campo", "Valor"],
        ["Producto", _text(receta.get("producto"))],
        ["Principio activo", _text(receta.get("principio_activo"))],
        ["Cultivo", _text(receta.get("cultivo"))],
        ["Lote", _text(receta.get("lote"))],
        ["Superficie", f"{_text(receta.get('superficie_ha'))} ha"],
        ["Dosis", _text(receta.get("dosis"))],
        ["Volumen de agua", _text(receta.get("volumen_agua"))],
        ["Fecha de aplicacion", _text(receta.get("fecha_aplicacion"))],
        ["Nivel de riesgo", _text(receta.get("nivel_riesgo"))],
        ["Observaciones", _text(receta.get("observaciones"))],
    ]
    table = Table(rows, colWidths=[150, 340])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(primary)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#f1f5f9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 18))
    story.append(Paragraph(footer, styles["Italic"]))
    story.append(Paragraph(_text(branding.get("footer_text") or ""), styles["Normal"]))
    doc.build(story)
    return str(out_path)