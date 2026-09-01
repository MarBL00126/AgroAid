from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.database import db_fetch_one
from core.security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


def _db_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Base de datos no disponible",
    )


def _parse_expires_at(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    if api_key:
        # Fast path: match PUBLIC_API_KEY directly without DB lookup
        public_key = os.environ.get("PUBLIC_API_KEY", "")
        if public_key and api_key == public_key:
            return {
                "id": None,
                "username": "public",
                "email": None,
                "role": "user",
                "tenant_id": 1,
                "auth_type": "public_key",
            }

        key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()

        try:
            stored_key = db_fetch_one(
                """
                SELECT id, name, expires_at, tenant_id
                FROM api_keys
                WHERE key_hash = %s
                  AND active = TRUE
                """,
                (key_hash,),
            )
        except RuntimeError as exc:
            raise _db_unavailable() from exc

        if stored_key:
            expires_at = _parse_expires_at(stored_key.get("expires_at"))
            now = datetime.now(expires_at.tzinfo or timezone.utc)

            if expires_at is not None and expires_at <= now:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API Key expirada",
                )

            return {
                "id": None,
                "username": stored_key["name"],
                "email": None,
                "role": "admin",
                "tenant_id": stored_key.get("tenant_id"),
                "auth_type": "api_key",
            }

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere JWT o X-API-Key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere un access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )

    try:
        user = db_fetch_one(
            """
            SELECT id, username, email, role, tenant_id
            FROM users
            WHERE id = %s
            """,
            (int(user_id),),
        )
    except (RuntimeError, ValueError) as exc:
        if isinstance(exc, RuntimeError):
            raise _db_unavailable() from exc
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        ) from exc

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        )

    user["auth_type"] = "jwt"
    return user


def require_any(
    current_user: dict = Depends(get_current_user),
) -> dict:
    return current_user


def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador",
        )

    return current_user
