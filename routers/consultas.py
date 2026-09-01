"""
routers/consultas.py
====================
Los endpoints de consulta viven en app.py porque dependen de los singletons
_llm, _sessions, _build_safety_chain, etc. que son globales de ese módulo.

Este archivo existe para mantener la estructura de paquetes limpia y para
futuras refactorizaciones donde se muevan esos singletons a un módulo separado.

Si querés mover los endpoints acá en el futuro, el patrón es:
    from app import _sessions, _llm, ...
    router = APIRouter(prefix="/api", tags=["Consultas"])
    # pegar los @router.post/get aquí
    # y en app.py: app.include_router(consultas_router)
"""
from fastapi import APIRouter

router = APIRouter(
    prefix="/api",
    tags=["Consultas"],
)