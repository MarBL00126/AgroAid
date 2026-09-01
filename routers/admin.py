from __future__ import annotations

import os
import pathlib

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from core.chroma import get_retriever, get_vector_store
from core.deps import require_admin

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
)


def _data_dir() -> pathlib.Path:
    configured = os.environ.get("PDF_FOLDER", "data")
    path = pathlib.Path(configured)
    if not path.is_absolute():
        path = pathlib.Path(__file__).resolve().parents[1] / path
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _safe_pdf_path(filename: str) -> pathlib.Path:
    clean_name = pathlib.Path(filename).name

    if not clean_name or pathlib.Path(clean_name).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser un PDF.",
        )

    base_dir = _data_dir()
    target = (base_dir / clean_name).resolve()

    if base_dir not in target.parents and target != base_dir:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nombre de archivo inválido.",
        )

    return target


def _clear_chroma_cache() -> None:
    get_retriever.cache_clear()
    get_vector_store.cache_clear()


@router.get("/pdfs")
async def list_pdfs(current_user: dict = Depends(require_admin)):
    pdfs = []

    for path in sorted(_data_dir().glob("*.pdf"), key=lambda p: p.name.lower()):
        stat = path.stat()
        pdfs.append(
            {
                "filename": path.name,
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
            }
        )

    return pdfs


@router.post("/pdfs")
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_admin),
):
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Falta el nombre del archivo.",
        )

    target = _safe_pdf_path(file.filename)
    content = await file.read()

    if not content.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El contenido no parece ser un PDF válido.",
        )

    target.write_bytes(content)
    _clear_chroma_cache()

    return {
        "message": "PDF subido correctamente",
        "filename": target.name,
        "size_bytes": target.stat().st_size,
    }


@router.delete("/pdfs/{filename}")
async def delete_pdf(
    filename: str,
    current_user: dict = Depends(require_admin),
):
    target = _safe_pdf_path(filename)

    if not target.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF no encontrado.",
        )

    target.unlink()
    _clear_chroma_cache()

    return {
        "message": "PDF eliminado correctamente",
        "filename": target.name,
    }
