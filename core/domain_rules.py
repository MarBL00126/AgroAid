"""Reglas de dominio de AI Safety agrícola: dominios, preguntas de seguimiento y normalización de evaluaciones."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

from core.regions import known_localities

if TYPE_CHECKING:
    from core.session_service import SessionState


DEFAULT_EVAL: dict = {
    "confianza": 30,
    "nivel_riesgo": "ALTO",
    "dominios_detectados": [],
    "evidencia_suficiente": False,
    "justificacion": "No se pudo evaluar con evidencia suficiente.",
    "riesgos_detectados": [
        "Recomendacion agricola potencialmente insegura o incompleta"
    ],
    "informacion_faltante": [
        "Datos criticos de contexto local"
    ],
    "preguntas_seguimiento": [
        "Que tarea agricola quiere realizar y en que ubicacion/pais/provincia?",
        "Hay personas, animales, agua, viviendas, escuelas o maquinaria involucradas?",
        "Que condiciones climaticas, producto/equipo o sintomas observa ahora?",
    ],
    "debe_abstenerse": True,
    "marco_regulatorio_aplicable": [
        "Principio preventivo de AI Safety agricola"
    ],
    "requiere_profesional": True,
}


# ── Safety domains ────────────────────────────────────────────────────────────

SAFETY_DOMAINS = {

    "agroquimicos": {
        "label": "Agroquimicos y sustancias reguladas",

        "keywords": [
            "agroquim",
            "fitosanit",
            "herbicida",
            "insecticida",
            "fungicida",
            "glifosato",
            "paraquat",
            "atrazina",
            "clorpirifos",
            "fumigar",
            "pulverizar",
            "dosis",
            "envase",
            "epp",
        ],

        "questions": [
            "Que producto, cultivo, dosis de etiqueta y metodo de aplicacion esta considerando?",
            "Cual es la velocidad del viento, temperatura y distancia a agua, viviendas o escuelas?",
            "Que EPP y manejo de envases/equipo tiene disponible?",
        ],
    },

    "clima_extremo": {

        "label": "Clima y eventos extremos",

        "keywords": [
            "helada",
            "calor",
            "ola de calor",
            "sequia",
            "sequía",
            "granizo",
            "inundacion",
            "inundación",
            "tormenta",
            "viento",
            "sembrar",
            "cosechar",
            "alerta",
        ],

        "questions": [
            "Que evento climatico afecta la tarea y cual es el pronostico/alerta local?",
            "Que cultivo o tarea quiere realizar: siembra, aplicacion, cosecha, riego o traslado?",
            "Cuales son temperatura, viento, humedad/suelo y nivel de anegamiento actuales?",
        ],
    },

    "seguridad_laboral": {

        "label": "Seguridad laboral rural",

        "keywords": [
            "tractor",
            "maquinaria",
            "maquina",
            "fumigadora",
            "motosierra",
            "silo",
            "bomba",
            "riego",
            "electric",
            "electrocucion",
            "electrocución",
            "deshidrat",
            "golpe de calor",
        ],

        "questions": [
            "Que maquina/equipo se usara y que tarea exacta se quiere hacer?",
            "Hay riesgo de energia electrica, partes moviles, altura, encierro en silo o calor extremo?",
            "Que EPP, bloqueo de energia, acompanante, agua/sombra y capacitacion hay disponibles?",
        ],
    },

    "agua_contaminacion": {

        "label": "Agua y contaminacion",

        "keywords": [
            "pozo",
            "rio",
            "río",
            "arroyo",
            "canal",
            "laguna",
            "agua",
            "escuela",
            "vivienda",
            "casa",
            "lavado",
            "escorrentia",
            "escorrentía",
            "contamin",
        ],

        "questions": [
            "A que distancia estan pozos, rios, canales, viviendas, escuelas o animales?",
            "Hay pendiente, lluvia reciente o riesgo de escorrentia hacia fuentes de agua?",
            "Como se lavaran equipos/envases y donde se dispondra el residuo?",
        ],
    },

    "zoonosis_salud_animal": {

        "label": "Zoonosis y salud animal",

        "keywords": [
            "brucelosis",
            "leptospirosis",
            "rabia",
            "gripe aviar",
            "fiebre aftosa",
            "animal",
            "vaca",
            "cerdo",
            "ave",
            "gallina",
            "perro",
            "mordedura",
            "leche",
            "carne",
            "huevo",
            "veterinario",
        ],

        "questions": [
            "Que especie animal, sintomas, cantidad de animales afectados y fecha de inicio observa?",
            "Hubo contacto con personas, mordeduras, abortos, muerte subita o signos neurologicos/respiratorios?",
            "Los animales/productos estan aislados y ya contacto a veterinario o autoridad sanitaria?",
        ],
    },

    "seguridad_alimentaria": {

        "label": "Seguridad alimentaria",

        "keywords": [
            "carencia",
            "intervalo de carencia",
            "cosecha",
            "cosechar",
            "grano",
            "granos",
            "maiz",
            "maíz",
            "trigo",
            "soja",
            "micotoxina",
            "micotoxinas",
            "aflatoxina",
            "fumonisina",
            "hongo",
            "hongos",
            "moho",
            "humedad",
            "almacenamiento",
            "silo",
            "bolsa",
            "secado",
            "alimento",
            "consumo",
        ],

        "questions": [
            "Que cultivo/alimento quiere cosechar o almacenar y que tratamiento reciente recibio?",
            "Se cumplio el intervalo de carencia de la etiqueta y cual es la fecha de ultima aplicacion?",
            "Cual es la humedad, presencia de hongos/moho y condicion de silo/bolsa/secado?",
        ],
    },

    "incendios_rurales": {

        "label": "Incendios rurales",

        "keywords": [
            "incendio",
            "fuego",
            "quema",
            "quemar",
            "pastizal",
            "rastrojo",
            "sequía",
            "sequia",
            "viento",
            "maquinaria caliente",
            "chispa",
            "cortafuego",
            "bombero",
            "bomberos",
            "indice de riesgo",
            "riesgo de incendio",
        ],

        "questions": [
            "Que tarea con fuego o maquinaria caliente quiere realizar y en que zona?",
            "Cuales son viento, sequia/humedad, temperatura, combustible seco e indice local de riesgo de incendio?",
            "Tiene permiso, cortafuegos, agua/equipo de control y contacto de autoridad local/bomberos?",
        ],
    },

    "riego_suelo": {

        "label": "Riego y suelo",

        "keywords": [
            "riego",
            "suelo",
            "salinidad",
            "salinizacion",
            "salinización",
            "erosion",
            "erosión",
            "fertilizante",
            "fertilizacion",
            "fertilización",
            "urea",
            "nitrato",
            "fosforo",
            "fósforo",
            "napas",
            "napa",
            "lixiviacion",
            "lixiviación",
            "escorrentia",
            "escorrentía",
            "pendiente",
            "compactacion",
            "compactación",
        ],

        "questions": [
            "Que cultivo, suelo, pendiente y sistema de riego/fertilizacion esta usando?",
            "Tiene analisis de suelo/agua, salinidad, dosis de fertilizante y pronostico de lluvia/riego?",
            "Hay napas, pozos, cursos de agua o signos de erosion/escorrentia cerca del lote?",
        ],
    },

    "bioseguridad_vegetal": {

        "label": "Bioseguridad vegetal",

        "keywords": [
            "plaga",
            "enfermedad",
            "cuarenten",
            "mancha",
            "marchitez",
            "roya",
            "cancro",
            "mosca",
            "picudo",
            "material vegetal",
            "semilla",
            "plantin",
            "plantín",
            "trasladar",
            "senasa",
        ],

        "questions": [
            "Que cultivo, sintomas, ubicacion y velocidad de avance observa?",
            "Movio semillas, frutos, plantas, suelo, herramientas o maquinaria desde/hacia otro lote?",
            "Puede aislar el material, evitar traslados, tomar fotos y consultar autoridad fitosanitaria?",
        ],
    },
}


ALLOWED_RISKS = {
    "BAJO",
    "MEDIO",
    "ALTO",
    "CRITICO",
}


_DOMAIN_PATTERNS: dict[str, re.Pattern] = {
    key: re.compile(
        "|".join(re.escape(keyword) for keyword in cfg["keywords"]),
        re.IGNORECASE,
    )
    for key, cfg in SAFETY_DOMAINS.items()
}


def infer_domains(text: str) -> list[str]:

    text = text or ""

    detected = [
        key
        for key, pattern in _DOMAIN_PATTERNS.items()
        if pattern.search(text)
    ]

    return detected or ["agroquimicos"]


def fallback_questions(
    domains: list[str],
) -> list[str]:

    questions = []

    for domain in domains:

        questions.extend(
            SAFETY_DOMAINS
            .get(domain, {})
            .get("questions", [])
        )

    seen = []

    for question in questions:

        if question not in seen:
            seen.append(question)

    return (
        seen[:3]
        or DEFAULT_EVAL["preguntas_seguimiento"]
    )


def _norm_text(text: str) -> str:

    normalized = (text or "").lower()

    normalized = re.sub(
        r"[^\w\s]",
        " ",
        normalized,
        flags=re.UNICODE,
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()

    return normalized


def _question_tokens(
    text: str,
) -> set[str]:

    stopwords = {
        "a",
        "al",
        "algo",
        "con",
        "cual",
        "cuales",
        "cuando",
        "de",
        "del",
        "el",
        "en",
        "es",
        "estan",
        "esta",
        "fue",
        "ha",
        "hay",
        "la",
        "las",
        "lo",
        "los",
        "o",
        "para",
        "por",
        "que",
        "se",
        "si",
        "su",
        "sus",
        "te",
        "tiene",
        "tus",
        "un",
        "una",
        "y",
        "ya",
    }

    return {
        word
        for word in _norm_text(text).split()
        if len(word) > 3
        and word not in stopwords
    }


def _is_similar_question(
    question: str,
    previous_questions: list[str],
) -> bool:

    current = _question_tokens(question)

    if not current:
        return True

    for previous in previous_questions:

        prev = _question_tokens(previous)

        if not prev:
            continue

        overlap = (
            len(current & prev)
            / max(
                1,
                min(
                    len(current),
                    len(prev),
                ),
            )
        )

        if overlap >= 0.55:
            return True

    return False


def _answer_seems_to_cover_question(
    question: str,
    answers_text: str,
) -> bool:

    q = _norm_text(question)
    a = _norm_text(answers_text)

    if not a:
        return False

    coverage_groups = (

        (
            ("vacun", "vacuna"),
            ("vacun",),
        ),

        (
            (
                "sintoma",
                "sintomas",
                "enfermedad",
                "inusual",
            ),
            (
                "sintoma",
                "enfermedad",
                "sanas",
                "sano",
                "sana",
            ),
        ),

        (
            (
                "veterinario",
                "profesional",
                "autoridad",
            ),
            (
                "veterinario",
                "profesional",
                "autoridad",
            ),
        ),

        (
            (
                "ubicacion",
                "zona",
                "localidad",
                "provincia",
                "pais",
            ),
            known_localities(),
        ),

        (
            (
                "contacto",
                "aislado",
                "aislar",
            ),
            (
                "aislad",
                "contact",
                "separad",
            ),
        ),

        (
            (
                "alimentacion",
                "alimento",
            ),
            (
                "alimento",
                "alimentacion",
                "pasto",
                "balanceado",
                "silo",
            ),
        ),
    )

    for q_terms, a_terms in coverage_groups:

        if (
            any(term in q for term in q_terms)
            and any(term in a for term in a_terms)
        ):
            return True

    return False


def filter_followup_questions(
    questions: list[str],
    session: Optional[SessionState],
    domains: list[str],
    allow_fallback: bool = True,
) -> list[str]:

    if session is None:

        previous_questions = []
        answers_text = ""

    else:

        previous_questions = [
            question
            for item in session.historial_respuestas
            for question in item.get(
                "preguntas",
                [],
            )
        ]

        answers_text = "\n".join(
            item.get("respuesta", "")
            for item in session.historial_respuestas
        )

    filtered = []

    for question in questions:

        if _is_similar_question(
            question,
            previous_questions + filtered,
        ):
            continue

        if _answer_seems_to_cover_question(
            question,
            answers_text,
        ):
            continue

        filtered.append(question)

    if len(filtered) >= 3 or not allow_fallback:
        return filtered[:3]

    for question in fallback_questions(domains):

        if _is_similar_question(
            question,
            previous_questions + filtered,
        ):
            continue

        if _answer_seems_to_cover_question(
            question,
            answers_text,
        ):
            continue

        filtered.append(question)

        if len(filtered) == 3:
            break

    if not filtered:

        filtered.append(
            "Podes darnos mas detalles especificos de tu situacion "
            "(ubicacion, producto/tarea exacta, cantidades, fechas) "
            "que todavia no hayas mencionado?"
        )

    return filtered


def normalize_eval(
    ev: dict,
    history_text: str,
    session: Optional[SessionState] = None,
) -> dict:

    if not isinstance(ev, dict):
        ev = DEFAULT_EVAL.copy()

    domains = (
        ev.get("dominios_detectados")
        or infer_domains(history_text)
    )

    if isinstance(domains, str):
        domains = [domains]

    domains = [
        domain
        for domain in domains
        if domain in SAFETY_DOMAINS
    ] or infer_domains(history_text)

    ev["dominios_detectados"] = domains

    risk = str(
        ev.get(
            "nivel_riesgo",
            "ALTO",
        )
    ).upper().replace(
        "CRÍTICO",
        "CRITICO",
    )

    ev["nivel_riesgo"] = (
        risk
        if risk in ALLOWED_RISKS
        else "ALTO"
    )

    try:

        ev["confianza"] = max(
            0,
            min(
                100,
                int(
                    ev.get(
                        "confianza",
                        30,
                    )
                ),
            ),
        )

    except Exception:

        ev["confianza"] = 30

    for field_name in (
        "riesgos_detectados",
        "informacion_faltante",
        "preguntas_seguimiento",
        "marco_regulatorio_aplicable",
    ):

        value = ev.get(field_name)

        if isinstance(value, str):

            ev[field_name] = [value]

        elif not isinstance(value, list):

            ev[field_name] = []

    needs_more_evidence = not ev.get(
        "evidencia_suficiente",
        False,
    )

    if (
        not ev["preguntas_seguimiento"]
        and needs_more_evidence
    ):

        ev["preguntas_seguimiento"] = (
            fallback_questions(domains)
        )

    ev["preguntas_seguimiento"] = (
        filter_followup_questions(
            ev["preguntas_seguimiento"],
            session,
            domains,
            allow_fallback=needs_more_evidence,
        )
    )

    if not ev["informacion_faltante"]:

        ev["informacion_faltante"] = [
            "Contexto local suficiente para evaluar "
            "la accion con seguridad"
        ]

    if not ev["riesgos_detectados"]:

        ev["riesgos_detectados"] = [
            "Riesgo agricola no caracterizado completamente"
        ]

    if (
        ev["nivel_riesgo"] in {"ALTO", "CRITICO"}
        and not ev.get(
            "evidencia_suficiente",
            False,
        )
    ):

        ev["debe_abstenerse"] = True

    if ev["confianza"] < 65:
        ev["debe_abstenerse"] = True

    ev["requiere_profesional"] = bool(
        ev.get(
            "requiere_profesional",
            ev["nivel_riesgo"] in {"ALTO", "CRITICO"},
        )
    )

    return ev




def extraer_producto_fitosanitario(historial: str) -> str | None:
    """
    Intenta extraer el nombre del producto fitosanitario
    mencionado por el usuario.
    """

    patrones = [
        r"(?:producto|herbicida|insecticida|fungicida|fitosanitario)"
        r"\s*(?:es|:)?\s*([A-Za-zÁÉÍÓÚáéíóúÑñ0-9\- ]{3,80})",

        r"(?:usar|aplicar|aplicando|apliqué|aplique)"
        r"\s+(?:el|la)?\s*"
        r"([A-Za-zÁÉÍÓÚáéíóúÑñ0-9\- ]{3,80})",

        r"(?:con)\s+"
        r"([A-Za-zÁÉÍÓÚáéíóúÑñ0-9\- ]{3,80})"
        r"\s+(?:para|en)",
    ]

    for patron in patrones:
        match = re.search(
            patron,
            historial,
            flags=re.IGNORECASE,
        )

        if match:
            producto = match.group(1).strip()

            producto = re.sub(
                r"\s+(?:para|en|sobre|contra)\s+.*$",
                "",
                producto,
                flags=re.IGNORECASE,
            )

            producto = producto.strip(" .,;:")

            if len(producto) >= 3:
                return producto

    return None
