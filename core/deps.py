from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.database import db_fetch_one
from core.security import decode_token
from core.token_blacklist import is_revoked

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
        if api_key.strip().lower() in {
            "ags_su_api_key_aqui",
            "su_api_key_aqui",
            "your_api_key_here",
        }:
            row = db_fetch_one("SELECT id, slug FROM tenants WHERE slug = %s", ("default",))
            return {
                "id": None,
                "username": "guest",
                "email": None,
                "role": "user",
                "tenant_id": row["id"] if row else 1,
                "tenant_slug": row["slug"] if row else "default",
                "auth_type": "demo_key",
            }

        # Fast path: match PUBLIC_API_KEY directly without DB lookup
        public_key = os.environ.get("PUBLIC_API_KEY", "")
        if public_key and api_key == public_key:
            return {
                "id": None,
                "username": "public",
                "email": None,
                "role": "user",
                "tenant_id": 1,
                "tenant_slug": "default",
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

            tid = stored_key.get("tenant_id")
            slug = None
            if tid:
                try:
                    row = db_fetch_one("SELECT slug FROM tenants WHERE id = %s", (tid,))
                    slug = row["slug"] if row else None
                except Exception:
                    pass

            return {
                "id": None,
                "username": stored_key["name"],
                "email": None,
                "role": "admin",
                "tenant_id": tid,
                "tenant_slug": slug or "default",
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
        revoked = is_revoked(payload.get("jti"))
    except RuntimeError as exc:
        raise _db_unavailable() from exc

    if revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revocado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("guest") is True:
        # Sesión anónima del chat público: no existe fila en users.
        return {
            "id": None,
            "username": "guest",
            "email": None,
            "role": "user",
            "tenant_id": payload.get("tenant_id"),
            "tenant_slug": "default",
            "auth_type": "guest",
            "guest_id": str(user_id),
        }

    try:
        user = db_fetch_one(
            """
            SELECT u.id, u.username, u.email, u.role, u.tenant_id,
                   t.slug AS tenant_slug
            FROM users u
            LEFT JOIN tenants t ON t.id = u.tenant_id
            WHERE u.id = %s
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


def get_tenant_id_from_user(current_user: dict) -> int:
    """Tenant del usuario autenticado. Sin tenant no hay fallback: se rechaza el request."""
    tenant_id = current_user.get("tenant_id")

    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario sin tenant asignado",
        )

    return int(tenant_id)


def get_user_id_from_user(current_user: dict) -> int | None:
    raw = current_user.get("id")
    return int(raw) if raw is not None else None


def get_tenant_slug_from_user(current_user: dict) -> str:
    return (current_user.get("tenant_slug") or "default").strip() or "default"


def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador",
        )

    return current_user
