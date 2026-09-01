from fastapi import APIRouter, Depends, HTTPException, Query

from core.deps import require_any
from core.senasa import buscar_fitosanitario
router=APIRouter(
    prefix="/api/senasa",
    tags=["SENASA"],
)
@router.get("/fitosanitario")
async def get_fitosanitario(
    producto: str = Query(
        ...,
        min_length=2,
        description="Nombre comercial o principio activo",
    ),
    user=Depends(require_any)
):
    producto=producto.strip()
    if not producto:
        raise HTTPException(
            status_code=400,
            detail="Debe indicar un producto fitosanitario.",
        )
    resultado=await buscar_fitosanitario(producto)
    return {
        "producto": producto,
        "resultado": resultado,
    }