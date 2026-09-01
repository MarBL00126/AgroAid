from __future__ import annotations

import asyncio
import logging
import os
import re

import httpx
from bs4 import BeautifulSoup


logger = logging.getLogger("agrosafety.senasa")

# Public Vademecum SENASA — no auth required, returns full HTML table.
VADEMECUM_URL = "https://aps2.senasa.gov.ar/vademecum/app/publico/formulados"
SENASA_ENABLED = os.environ.get("SENASA_ENABLED", "1") != "0"

# In-memory catalog loaded once on first search.
_catalog: list[dict] | None = None
_catalog_lock = asyncio.Lock()


def _norm(texto: str) -> str:
    t = re.sub(r"\s+", " ", (texto or "")).strip().lower()
    for a, b in (
        ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ü", "u"), ("ñ", "n"),
    ):
        t = t.replace(a, b)
    return t


def _fetch_catalog_sync() -> list[dict]:
    """Downloads and parses the full Vademecum table. Runs in a thread."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AgroSafety/1.0; +https://agrosafety.app)"}
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(VADEMECUM_URL)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("No se pudo cargar el Vademecum SENASA: %s", exc)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        logger.warning("Vademecum SENASA: no se encontró tabla en la respuesta")
        return []

    productos = []
    for row in table.find_all("tr"):
        celdas = [re.sub(r"\s+", " ", c.get_text(" ", strip=True)) for c in row.find_all(["td", "th"])]
        if len(celdas) < 4 or not celdas[0] or not celdas[1]:
            continue
        # Skip header rows
        if _norm(celdas[1]) in {"nombre", "producto", "denominacion"}:
            continue
        productos.append({
            "numero_registro":       celdas[0],
            "nombre_producto":       celdas[1],
            "empresa":               celdas[2] if len(celdas) > 2 else "",
            "principio_activo":      celdas[3] if len(celdas) > 3 else "",
            "categoria_toxicologica": celdas[4] if len(celdas) > 4 else "",
        })

    logger.info("Vademecum SENASA cargado: %d productos formulados", len(productos))
    return productos


async def _get_catalog() -> list[dict]:
    global _catalog
    if _catalog is not None:
        return _catalog
    async with _catalog_lock:
        if _catalog is not None:  # re-check after acquiring lock
            return _catalog
        _catalog = await asyncio.to_thread(_fetch_catalog_sync)
    return _catalog


def _buscar_en_catalogo(nombre: str, catalog: list[dict]) -> dict | None:
    needle = _norm(nombre)
    if not needle:
        return None

    needle_words = set(needle.split())
    best: tuple[int, dict] = (0, {})

    for p in catalog:
        n = _norm(p["nombre_producto"])
        a = _norm(p["principio_activo"])

        if needle == n:
            score = 100
        elif n.startswith(needle):
            score = 80
        elif needle in n:
            score = 60
        elif needle in a:
            score = 40
        else:
            shared = needle_words & set(n.split()) or needle_words & set(a.split())
            score = int(35 * len(shared) / len(needle_words)) if shared else 0

        if score > best[0]:
            best = (score, p)

    if best[0] >= 20:
        p = best[1]
        return {
            "registrado":             True,
            "numero_registro":        p["numero_registro"],
            "nombre_producto":        p["nombre_producto"],
            "empresa":                p["empresa"],
            "principio_activo":       p["principio_activo"],
            "categoria_toxicologica": p["categoria_toxicologica"],
            "usos_permitidos":        [],
        }
    return None


async def buscar_fitosanitario(nombre: str) -> dict | None:
    """
    Busca un producto formulado en el Vademecum público de SENASA.

    Devuelve:

    {
        "registrado": True,
        "numero_registro": "...",
        "nombre_producto": "...",
        "empresa": "...",
        "principio_activo": "...",
        "categoria_toxicologica": "I|II|III|IV|S/D",
        "usos_permitidos": []
    }

    o None si no se encuentra o SENASA_ENABLED=0.
    """
    if not SENASA_ENABLED:
        return None

    nombre = re.sub(r"\s+", " ", (nombre or "")).strip()
    if not nombre:
        return None

    try:
        catalog = await _get_catalog()
        return _buscar_en_catalogo(nombre, catalog) if catalog else None
    except Exception as exc:
        logger.exception("Error buscando '%s' en Vademecum SENASA: %s", nombre, exc)
        return None

