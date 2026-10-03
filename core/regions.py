"""
Localidades conocidas por país/región, cargadas desde config/regions.json
(o la ruta indicada en REGIONS_FILE). Se usan para reconocer cuándo una
respuesta del productor ya informó su ubicación.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import unicodedata
from functools import lru_cache

from core.config import BASE_DIR

logger = logging.getLogger("agrosafety.regions")


def _strip_accents(text: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


@lru_cache(maxsize=1)
def load_regions() -> dict[str, list[str]]:

    path = pathlib.Path(
        os.environ.get("REGIONS_FILE", BASE_DIR / "config" / "regions.json")
    )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("No se pudo cargar regiones desde %s: %s", path, exc)
        return {}

    if not isinstance(data, dict):
        logger.warning("%s debe contener un objeto {region: [localidades]}", path)
        return {}

    return {
        str(region): [str(name) for name in names]
        for region, names in data.items()
        if isinstance(names, list)
    }


@lru_cache(maxsize=1)
def known_localities() -> tuple[str, ...]:
    """Localidades de todas las regiones, en minúscula y con/sin acentos."""

    names: list[str] = []

    for localities in load_regions().values():
        for name in localities:
            low = name.strip().lower()
            for variant in (low, _strip_accents(low)):
                if variant and variant not in names:
                    names.append(variant)

    return tuple(names)
