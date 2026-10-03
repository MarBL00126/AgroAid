"""
Blacklist de tokens JWT revocados (logout).

Se guarda el jti de cada token revocado hasta su vencimiento; después ya no
hace falta recordarlo porque el token expira solo.
"""
from __future__ import annotations

from datetime import datetime, timezone

from core.database import db_exec, db_fetch_val


def revoke_token(payload: dict) -> None:
    jti = payload.get("jti")
    exp = payload.get("exp")

    if not jti or exp is None:
        return

    db_exec(
        """
        INSERT INTO revoked_tokens (jti, expires_at)
        VALUES (%s, %s)
        ON CONFLICT (jti) DO NOTHING
        """,
        (jti, datetime.fromtimestamp(exp, tz=timezone.utc)),
    )


def is_revoked(jti: str | None) -> bool:
    if not jti:
        return False

    return bool(
        db_fetch_val(
            "SELECT 1 FROM revoked_tokens WHERE jti = %s",
            (jti,),
        )
    )


def purge_expired() -> None:
    db_exec("DELETE FROM revoked_tokens WHERE expires_at < now()")
