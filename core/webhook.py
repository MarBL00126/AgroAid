import hashlib
import hmac
import json
import logging

import httpx

from core.database import db_fetch_all


logger = logging.getLogger(__name__)


async def dispatch_webhook(
    tenant_id,
    event,
    payload,
):
    """
    Envía un evento a todos los webhooks activos
    configurados para un tenant.

    La firma se genera mediante HMAC-SHA256 usando
    el secret del webhook.
    """

    try:
        webhooks = db_fetch_all(
            """
            SELECT
                id,
                url,
                secret,
                events
            FROM webhooks
            WHERE tenant_id = %s
              AND is_active = TRUE
            """,
            (tenant_id,),
        )

    except Exception:
        logger.exception(
            "Error buscando webhooks del tenant %s",
            tenant_id,
        )
        return

    body = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    async with httpx.AsyncClient(timeout=10.0) as client:

        for webhook in webhooks:

            webhook_id = webhook["id"]
            url = webhook["url"]
            secret = webhook["secret"]
            events = webhook["events"] or []

            # Si el webhook tiene eventos configurados,
            # solamente recibe los eventos suscriptos.
            if events and event not in events:
                continue

            signature = hmac.new(
                secret.encode("utf-8"),
                body,
                hashlib.sha256,
            ).hexdigest()

            headers = {
                "Content-Type": "application/json",
                "X-AgroAid-Signature": signature,
                "X-AgroAid-Event": event,
            }

            try:
                response = await client.post(
                    url,
                    content=body,
                    headers=headers,
                )

                response.raise_for_status()

                logger.info(
                    "Webhook enviado correctamente: "
                    "webhook_id=%s tenant_id=%s event=%s status=%s",
                    webhook_id,
                    tenant_id,
                    event,
                    response.status_code,
                )

            except Exception:
                logger.exception(
                    "Error enviando webhook "
                    "webhook_id=%s tenant_id=%s event=%s url=%s",
                    webhook_id,
                    tenant_id,
                    event,
                    url,
                )