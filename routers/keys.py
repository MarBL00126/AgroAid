from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from core.database import db_exec, db_fetch_all, db_fetch_one
from core.deps import require_admin

router = APIRouter(
    prefix="/api/keys",
    tags=["API Keys"],
)


class CreateApiKeyRequest(BaseModel):
    name: str
    expires_at: datetime | None = None


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def _db_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Base de datos no disponible: {exc}",
    )


@router.post("")
@router.post("/")
def create_api_key(
    request: CreateApiKeyRequest,
    current_user: dict = Depends(require_admin),
):
    raw_key = "ags_" + secrets.token_urlsafe(32)

    try:
        db_exec(
            """
            INSERT INTO api_keys (tenant_id, name, key_hash, active, expires_at)
            VALUES (%s, %s, %s, TRUE, %s)
            """,
            (
                current_user.get("tenant_id"),
                request.name,
                hash_api_key(raw_key),
                request.expires_at,
            ),
        )
        api_key = db_fetch_one(
            """
            SELECT id, name, active, created_at, expires_at
            FROM api_keys
            WHERE key_hash = %s
            """,
            (hash_api_key(raw_key),),
        )
    except RuntimeError as exc:
        raise _db_unavailable(exc) from exc

    return {
        "id": api_key["id"],
        "name": api_key["name"],
        "api_key": raw_key,
        "active": api_key["active"],
        "created_at": api_key["created_at"],
        "expires_at": api_key["expires_at"],
        "warning": "Guarda esta API Key. No volverá a mostrarse.",
    }


@router.get("")
@router.get("/")
def get_api_keys(
    current_user: dict = Depends(require_admin),
):
    params: tuple = ()
    tenant_clause = ""

    if current_user.get("tenant_id") is not None:
        tenant_clause = "WHERE tenant_id = %s OR tenant_id IS NULL"
        params = (current_user["tenant_id"],)

    try:
        keys = db_fetch_all(
            f"""
            SELECT id, name, active, created_at, expires_at
            FROM api_keys
            {tenant_clause}
            ORDER BY created_at DESC
            """,
            params,
        )
    except RuntimeError as exc:
        raise _db_unavailable(exc) from exc

    return keys


@router.delete("/{key_id}")
def delete_api_key(
    key_id: int,
    current_user: dict = Depends(require_admin),
):
    try:
        api_key = db_fetch_one(
            "SELECT id, tenant_id FROM api_keys WHERE id = %s",
            (key_id,),
        )
    except RuntimeError as exc:
        raise _db_unavailable(exc) from exc

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key no encontrada",
        )

    if (
        current_user.get("tenant_id") is not None
        and api_key.get("tenant_id") not in (None, current_user["tenant_id"])
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puede eliminar API Keys de otro tenant",
        )

    try:
        db_exec("DELETE FROM api_keys WHERE id = %s", (key_id,))
    except RuntimeError as exc:
        raise _db_unavailable(exc) from exc

    return {"message": "API Key eliminada correctamente"}
