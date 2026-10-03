"""
AgroSafety API
==============

Hackathon Global South AI Safety 2026 | Track Latinoamérica

Backend FastAPI para el sistema de evaluación de seguridad agrícola.
Este módulo solo ensambla la aplicación (lifespan, middlewares, routers y
endpoints de sistema). La lógica vive en core/ y routers/.

Uso:

    pip install -r requirements.txt

    # Variables de entorno:

    #   JWT_SECRET_KEY   — requerida (mínimo 32 caracteres)
    #   GOOGLE_API_KEY   — requerida (clave de Gemini / Google AI Studio)
    #   GEMINI_MODEL     — default: gemini-3.6-flash
    #   DB_PASSWORD      — contraseña PostgreSQL
    #   DB_HOST          — default: localhost
    #   DB_NAME          — default: agrosafety
    #   DB_USER          — default: postgres
    #   PDF_FOLDER       — default: data
    #   CHROMA_DIR       — default: db_agro_docs

    uvicorn app:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

# Debe ir primero: carga el .env antes de que otros módulos lean variables.
from core.config import FRONTEND_DIR

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from core.ai_chains import init_ai, is_ai_ready
from core.clima import close_clima_client
from core.clima import get_clima as _fetch_clima
from core.database import (
    close_pool,
    ensure_schema,
    init_pool,
    is_pool_initialized,
)
from core.deps import require_any
from core.domain_rules import SAFETY_DOMAINS
from core.limiter import limiter
from routers.admin import router as admin_router
from routers.auth import router as auth_router
from routers.consultas import risk_router
from routers.consultas import router as consultas_router
from routers.dashboard import router as dashboard_router
from routers.imagen import router as imagen_router
from routers.keys import router as keys_router
from routers.mapa import router as mapa_router
from routers.prevuelo import router as prevuelo_router
from routers.recetas import router as recetas_router
from routers.senasa import router as senasa_router
from routers.voz import router as voz_router
from routers.whatsapp import router as whatsapp_router


# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger("agrosafety")


# ── Startup ───────────────────────────────────────────────────────────────────

_db_ready = False


def _connect_db() -> None:

    global _db_ready

    try:

        init_pool()

        ensure_schema()

        _db_ready = True

        logger.info("PostgreSQL conectado")

    except Exception as exc:

        _db_ready = False

        logger.error(
            "DB no disponible: %s",
            exc,
        )


def _sync_init() -> None:

    _connect_db()

    if init_ai():

        logger.info(
            "AgroSafety API lista"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):

    # Se espera a que termine: la app no acepta requests hasta estar inicializada.
    await asyncio.to_thread(_sync_init)

    yield

    await close_clima_client()

    close_pool()

    logger.info(
        "AgroSafety API apagada"
    )


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="AgroSafety API",
    description=(
        "Sistema de evaluacion integral "
        "de seguridad agricola con AI Safety"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# slowapi
app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(keys_router)
app.include_router(whatsapp_router)
app.include_router(voz_router)
app.include_router(imagen_router)
app.include_router(consultas_router)
app.include_router(risk_router)
app.include_router(dashboard_router)
app.include_router(senasa_router)
app.include_router(mapa_router)
app.include_router(prevuelo_router)
app.include_router(recetas_router)

_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",")
    if o.strip()
] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_DIR.is_dir():

    app.mount(
        "/static",
        StaticFiles(
            directory=str(FRONTEND_DIR)
        ),
        name="static",
    )


# ── Endpoints de sistema ──────────────────────────────────────────────────────

@app.get("/")
async def root():

    idx = (
        FRONTEND_DIR
        / "index.html"
    )

    if idx.exists():

        return FileResponse(
            str(idx)
        )

    return {
        "status": "AgroSafety API running",
        "frontend": (
            "frontend/index.html "
            "not found"
        ),
    }


@app.get("/landing")
async def landing():
    page = FRONTEND_DIR / "landing.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "Landing page not found"}


@app.get("/admin.html")
async def admin_page():
    page = FRONTEND_DIR / "admin.html"
    if page.exists():
        return FileResponse(str(page))
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/api/health")
async def health():

    return {

        "status": "ok",

        "db_connected": (
            _db_ready
            and is_pool_initialized()
        ),

        "ai_ready": is_ai_ready(),

        "safety_domains": [
            cfg["label"]
            for cfg in SAFETY_DOMAINS.values()
        ],
    }


@app.get("/api/public-config")
async def public_config():
    """Configuracion publica para el frontend (sin auth). No incluye secretos."""
    raw = os.environ.get("TWILIO_WHATSAPP_FROM", "")  # e.g. "whatsapp:+14155238886"
    wa_number = raw.replace("whatsapp:", "").strip()
    return {
        "whatsapp_number": wa_number,
    }


@app.get("/api/clima")
async def clima_actual(
    lat: float,
    lon: float,
    current_user: dict = Depends(require_any),
):
    return await _fetch_clima(lat, lon)


# ── OpenAPI ───────────────────────────────────────────────────────────────────

def custom_openapi():

    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(

        title="AgroSafety API",

        version="1.0.0",

        description=(
            "Sistema de evaluación integral "
            "de seguridad agrícola con AI Safety."
        ),

        routes=app.routes,
    )

    openapi_schema["components"][
        "securitySchemes"
    ] = {

        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        },

        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        },
    }

    app.openapi_schema = (
        openapi_schema
    )

    return app.openapi_schema


app.openapi = custom_openapi
