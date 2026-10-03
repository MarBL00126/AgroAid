"""
Configuración central. Importar este módulo antes de leer variables de
entorno garantiza que el .env ya fue cargado.
"""
from __future__ import annotations

import os
import pathlib

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

# Única definición del modelo Gemini usado por toda la app.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

# Límites por IP para los endpoints que consumen Gemini (formato slowapi).
RATE_LIMIT_CONSULTA = os.environ.get("RATE_LIMIT_CONSULTA", "5/minute")
RATE_LIMIT_RESPONDER = os.environ.get("RATE_LIMIT_RESPONDER", "20/minute")
RATE_LIMIT_MULTIMEDIA = os.environ.get("RATE_LIMIT_MULTIMEDIA", "5/minute")
RATE_LIMIT_RISK_SCORE = os.environ.get("RATE_LIMIT_RISK_SCORE", "10/minute")
RATE_LIMIT_GUEST = os.environ.get("RATE_LIMIT_GUEST", "20/minute")

# Duración de la sesión de invitado del chat público (minutos).
GUEST_TOKEN_MINUTES = int(os.environ.get("GUEST_TOKEN_MINUTES", "360"))
