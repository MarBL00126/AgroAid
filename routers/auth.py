from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from core.database import db_fetch_one, db_fetch_val, get_conn, get_tenant_id
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)

VALID_ROLES = {"user", "admin"}


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    tenant_slug: str = "default"
    role: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


def _db_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Base de datos no disponible: {exc}",
    )


@router.post("/register")
async def register(req: RegisterRequest):
    try:
        existing = db_fetch_one(
            """
            SELECT id
            FROM users
            WHERE email = %s OR username = %s
            """,
            (req.email, req.username),
        )
    except RuntimeError as exc:
        raise _db_unavailable(exc) from exc

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email o username ya está registrado.",
        )

    try:
        user_count = int(db_fetch_val("SELECT COUNT(*) FROM users") or 0)
        tenant_id = get_tenant_id(req.tenant_slug)
    except RuntimeError as exc:
        raise _db_unavailable(exc) from exc

    requested_role = (req.role or "").strip().lower()
    role = requested_role if requested_role in VALID_ROLES else "user"
    if user_count == 0:
        role = "admin"

    password_hash = hash_password(req.password)

    try:
        with get_conn() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO users (
                            tenant_id,
                            username,
                            email,
                            password_hash,
                            role
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id, username, email, role, created_at
                        """,
                        (
                            tenant_id,
                            req.username,
                            req.email,
                            password_hash,
                            role,
                        ),
                    )
                    user = cur.fetchone()
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    except RuntimeError as exc:
        raise _db_unavailable(exc) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error registrando usuario: {exc}",
        ) from exc

    return {
        "message": "Usuario registrado correctamente",
        "user": {
            "id": user[0],
            "username": user[1],
            "email": user[2],
            "role": user[3],
            "created_at": user[4],
        },
    }


@router.post("/login")
async def login(req: LoginRequest):
    try:
        user = db_fetch_one(
            """
            SELECT id, username, email, password_hash, role, tenant_id
            FROM users
            WHERE email = %s
            """,
            (req.email,),
        )
    except RuntimeError as exc:
        raise _db_unavailable(exc) from exc

    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas.",
        )

    token_data = {
        "sub": str(user["id"]),
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "tenant_id": user["tenant_id"],
    }

    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer",
    }


@router.post("/refresh")
async def refresh(req: RefreshRequest):
    payload = decode_token(req.refresh_token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado.",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token proporcionado no es un refresh token.",
        )

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido.",
        )

    token_data = {
        "sub": user_id,
        "username": payload.get("username"),
        "email": payload.get("email"),
        "role": payload.get("role"),
        "tenant_id": payload.get("tenant_id"),
    }

    return {
        "access_token": create_access_token(token_data),
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout():
    return {"message": "Logout realizado correctamente."}
