from __future__ import annotations

from datetime import datetime
import html
from io import BytesIO

from reportlab.graphics.shapes import (
    Circle,
    Drawing,
    Rect as GRect,
    String as GString,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.session_service import SessionState


def build_pdf_bytes(
    session: SessionState,
) -> bytes:

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=(
            f"AgroSafety diagnostico "
            f"{session.consulta_id}"
        ),
    )

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="Small",
            parent=styles["BodyText"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor(
                "#475569"
            ),
        )
    )

    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading2"],
            fontSize=12,
            leading=15,
            spaceBefore=10,
            spaceAfter=5,
            textColor=colors.HexColor(
                "#14532d"
            ),
        )
    )

    styles.add(
        ParagraphStyle(
            name="Box",
            parent=styles["BodyText"],
            fontSize=9,
            leading=12,
            backColor=colors.HexColor(
                "#f8fafc"
            ),
            borderColor=colors.HexColor(
                "#e2e8f0"
            ),
            borderWidth=0.5,
            borderPadding=6,
            spaceAfter=8,
        )
    )

    ev = (
        session.ultima_evaluacion
        or {}
    )

    verif = (
        session.verificacion
        or {}
    )

    generated_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M"
    )

    story = []

    story.append(
        Paragraph(
            "AgroSafety - Diagnostico de Seguridad Agricola",
            styles["Title"],
        )
    )

    story.append(
        Paragraph(
            "Reporte generado automaticamente "
            "por la capa de AI Safety agricola.",
            styles["Small"],
        )
    )

    story.append(
        Spacer(1, 8)
    )

    summary_data = [

        [
            Paragraph(
                "Consulta ID",
                styles["Small"],
            ),
            Paragraph(
                str(session.consulta_id),
                styles["Small"],
            ),
        ],

        [
            Paragraph(
                "Fecha",
                styles["Small"],
            ),
            Paragraph(
                generated_at,
                styles["Small"],
            ),
        ],

        [
            Paragraph(
                "Riesgo",
                styles["Small"],
            ),
            Paragraph(
                _pdf_text(
                    ev.get(
                        "nivel_riesgo",
                        session.riesgo_final,
                    )
                ),
                styles["Small"],
            ),
        ],

        [
            Paragraph(
                "Confianza",
                styles["Small"],
            ),
            Paragraph(
                f"{ev.get('confianza', session.confianza_final)}%",
                styles["Small"],
            ),
        ],

        [
            Paragraph(
                "Dominios",
                styles["Small"],
            ),
            Paragraph(
                _pdf_text(
                    _join_items(
                        ev.get(
                            "dominios_detectados",
                            [],
                        )
                    )
                ),
                styles["Small"],
            ),
        ],

        [
            Paragraph(
                "Abstencion",
                styles["Small"],
            ),
            Paragraph(
                "Si"
                if session.se_abstuvo_final
                else "No",
                styles["Small"],
            ),
        ],

        [
            Paragraph(
                "Requiere profesional",
                styles["Small"],
            ),
            Paragraph(
                "Si"
                if ev.get(
                    "requiere_profesional",
                    True,
                )
                else "No",
                styles["Small"],
            ),
        ],
    ]

    table = Table(
        summary_data,
        colWidths=[
            4.2 * cm,
            11.2 * cm,
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor(
                        "#dcfce7"
                    ),
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.35,
                    colors.HexColor(
                        "#cbd5e1"
                    ),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    story.append(table)

    # ── Visual: semáforo + barra de confianza + tabla de severidad ─────────────
    _nivel_norm = (
        ev.get("nivel_riesgo", session.riesgo_final) or "ALTO"
    ).upper().replace("CRÍTICO", "CRITICO")
    _conf_val = int(ev.get("confianza", session.confianza_final) or 0)

    story.append(Spacer(1, 10))
    story.append(Paragraph("Semáforo de riesgo", styles["Section"]))
    _GREY = colors.HexColor("#374151")
    _SEMA = {
        "BAJO":    (colors.HexColor("#22c55e"), _GREY,                     _GREY),
        "MEDIO":   (_GREY,                      colors.HexColor("#eab308"), _GREY),
        "ALTO":    (_GREY,                      _GREY,                     colors.HexColor("#f97316")),
        "CRITICO": (_GREY,                      _GREY,                     colors.HexColor("#ef4444")),
    }
    _sc1, _sc2, _sc3 = _SEMA.get(_nivel_norm, _SEMA["ALTO"])
    _risk_hex = {
        "BAJO": "#22c55e", "MEDIO": "#eab308",
        "ALTO": "#f97316", "CRITICO": "#ef4444",
    }.get(_nivel_norm, "#f97316")
    _sema = Drawing(110, 36)
    _sema.add(GRect(0, 0, 110, 36, fillColor=colors.HexColor("#1f2937"), strokeColor=None))
    for _xi, _col in [(16, _sc1), (50, _sc2), (84, _sc3)]:
        _sema.add(Circle(_xi, 18, 12, fillColor=_col,
                         strokeColor=colors.HexColor("#4b5563"), strokeWidth=1))
    story.append(_sema)
    story.append(Paragraph(
        f"<b>{_nivel_norm}</b> — "
        f"Abstención: {'Sí' if session.se_abstuvo_final else 'No'} — "
        f"Confianza: {_conf_val}%",
        styles["Small"],
    ))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Confianza del sistema", styles["Section"]))
    _BW = int(15.4 * cm)
    _BFW = max(0, int(_BW * _conf_val / 100))
    _bc = (
        colors.HexColor("#22c55e") if _conf_val >= 75
        else colors.HexColor("#eab308") if _conf_val >= 50
        else colors.HexColor("#ef4444")
    )
    _cd = Drawing(_BW, 26)
    _cd.add(GRect(0, 5, _BW, 14, fillColor=colors.HexColor("#e5e7eb"), strokeColor=None))
    if _BFW > 0:
        _cd.add(GRect(0, 5, _BFW, 14, fillColor=_bc, strokeColor=None))
    _cl = GString(_BW // 2, 8, f"{_conf_val}%")
    _cl.fontSize = 8
    _cl.fontName = "Helvetica-Bold"
    _cl.fillColor = colors.white if _conf_val > 25 else colors.HexColor("#111827")
    _cl.textAnchor = "middle"
    _cd.add(_cl)
    story.append(_cd)

    story.append(Spacer(1, 8))
    story.append(Paragraph("Contexto de severidad comparativa", styles["Section"]))
    _SEV_BG  = {"BAJO": colors.HexColor("#dcfce7"), "MEDIO": colors.HexColor("#fef9c3"),
                "ALTO": colors.HexColor("#ffedd5"), "CRITICO": colors.HexColor("#fee2e2")}
    _SEV_DESC = {
        "BAJO":    "Sin riesgo inmediato — accion preventiva",
        "MEDIO":   "Precaucion — verificar condiciones locales",
        "ALTO":    "Riesgo elevado — suspender y consultar",
        "CRITICO": "Situacion critica — accion urgente",
    }
    _SEV_BAR = {"BAJO": "█░░░", "MEDIO": "██░░", "ALTO": "███░", "CRITICO": "████"}
    _sev_rows = [[
        Paragraph("<b>Nivel</b>", styles["Small"]),
        Paragraph("<b>Descripcion de referencia</b>", styles["Small"]),
        Paragraph("<b>Escala</b>", styles["Small"]),
    ]]
    _sev_ts = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for _ri, _key in enumerate(("BAJO", "MEDIO", "ALTO", "CRITICO"), start=1):
        _cur = _key == _nivel_norm
        _sev_rows.append([
            Paragraph(f"<b>{_key}</b>" if _cur else _key, styles["Small"]),
            Paragraph(f"<b>{_SEV_DESC[_key]}</b>" if _cur else _SEV_DESC[_key], styles["Small"]),
            Paragraph(f"<b>{_SEV_BAR[_key]}</b>" if _cur else _SEV_BAR[_key], styles["Small"]),
        ])
        if _cur:
            _sev_ts += [
                ("BACKGROUND", (0, _ri), (-1, _ri), _SEV_BG[_key]),
                ("FONTNAME", (0, _ri), (-1, _ri), "Helvetica-Bold"),
            ]
    _sev_t = Table(_sev_rows, colWidths=[2.5 * cm, 9.4 * cm, 3.5 * cm])
    _sev_t.setStyle(TableStyle(_sev_ts))
    story.append(_sev_t)
    story.append(Spacer(1, 10))

    def section(
        title: str,
        body,
    ):

        story.append(
            Paragraph(
                title,
                styles["Section"],
            )
        )

        if isinstance(body, list):

            if body:

                for item in body:

                    story.append(
                        Paragraph(
                            f"- {_pdf_text(item)}",
                            styles["BodyText"],
                        )
                    )

            else:

                story.append(
                    Paragraph(
                        "No registrado",
                        styles["BodyText"],
                    )
                )

        else:

            story.append(
                Paragraph(
                    _pdf_text(
                        body
                        or "No registrado"
                    ),
                    styles["Box"],
                )
            )

    section(
        "Consulta e historial",
        session.historial_consulta,
    )

    section(
        "Justificacion tecnica",
        ev.get(
            "justificacion",
            "",
        ),
    )

    section(
        "Riesgos detectados",
        ev.get(
            "riesgos_detectados",
            [],
        ),
    )

    section(
        "Informacion faltante",
        ev.get(
            "informacion_faltante",
            [],
        ),
    )

    section(
        "Marco o autoridad aplicable",
        ev.get(
            "marco_regulatorio_aplicable",
            [],
        ),
    )

    section(
        "Evaluacion final",
        session.evaluacion_final
        or (
            "La consulta aun no tiene "
            "evaluacion final. Complete el "
            "flujo de preguntas para generar "
            "el diagnostico final."
        ),
    )

    if verif:

        section(
            "Verificacion de evidencia",
            verif.get(
                "explanation",
                "",
            ),
        )

        section(
            "Fuentes citadas",
            verif.get(
                "cited_sources",
                [],
            ),
        )

        section(
            "Afirmaciones sin respaldo",
            verif.get(
                "unsupported_claims",
                [],
            ),
        )

    story.append(
        Spacer(1, 10)
    )

    story.append(
        Paragraph(
            "Aviso: AgroSafety no reemplaza a "
            "profesionales habilitados ni autoridades "
            "sanitarias, fitosanitarias, ambientales "
            "o de emergencia.",
            styles["Small"],
        )
    )

    doc.build(story)

    buffer.seek(0)

    return buffer.getvalue()
def _pdf_text(value) -> str:

    text = (
        ""
        if value is None
        else str(value)
    )

    return html.escape(text).replace(
        "\n",
        "<br/>",
    )


def _join_items(items) -> str:

    if not items:
        return "No registrado"

    if isinstance(items, str):
        return items

    return ", ".join(
        str(x)
        for x in items
    )