"""Persistencia de consultas, respuestas, auditoría y métricas."""
from __future__ import annotations

import hashlib
import json
import logging

from fastapi import HTTPException

from core.database import db_exec, get_conn, get_tenant_id

logger = logging.getLogger("agrosafety.consulta_repo")


def crear_consulta(
    texto: str,
    tenant_slug: str = "default",
) -> int:

    try:

        tenant_id = get_tenant_id(
            tenant_slug
        )

        with get_conn() as conn:

            try:

                with conn.cursor() as cur:

                    cur.execute(
                """
                INSERT INTO consultas (tenant_id, consulta_inicial)
                VALUES (%s, %s)
                RETURNING id
                """,
                        (
                            tenant_id,
                            texto,
                        ),
                    )

                    cid = cur.fetchone()[0]

                conn.commit()

                return cid

            except Exception:

                conn.rollback()
                raise

    except Exception as exc:

        logger.error(
            "crear_consulta error: %s",
            exc,
        )

        raise HTTPException(
            status_code=503,
            detail="Base de datos no disponible.",
        ) from exc


def guardar_respuesta(
    cid,
    it,
    preguntas,
    respuesta,
    confianza,
    riesgo,
):

    db_exec(
        """
        INSERT INTO respuestas
        (
            tenant_id,
            consulta_id,
            iteracion,
            preguntas,
            respuesta,
            confianza_antes,
            riesgo_antes
        )
        VALUES (
            (SELECT tenant_id FROM consultas WHERE id = %s),
            %s,%s,%s,%s,%s,%s
        )
        """,
        (
            cid,
            cid,
            it,
            json.dumps(
                preguntas,
                ensure_ascii=False,
            ),
            respuesta,
            confianza,
            riesgo,
        ),
    )


def registrar_auditoria(
    cid,
    it,
    accion,
    detalle,
):
    """
    Agrega un evento a la cadena de auditoría de la consulta.

    Una sola conexión y una sola transacción: el advisory lock serializa los
    eventos de la misma consulta para que la cadena de hashes no se bifurque.
    """
    detalle_json = json.dumps(detalle, ensure_ascii=False, sort_keys=True)

    with get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(%s)", (cid,))

                cur.execute(
                    """
                    SELECT entry_hash FROM auditoria
                    WHERE consulta_id = %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (cid,),
                )
                ultima = cur.fetchone()
                prev_hash = ultima[0] if ultima else None

                hash_data = json.dumps(
                    {
                        "consulta_id": cid,
                        "iteracion": it,
                        "accion": accion,
                        "detalle": detalle_json,
                        "prev_hash": prev_hash,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                entry_hash = hashlib.sha256(
                    hash_data.encode("utf-8")
                ).hexdigest()

                cur.execute(
                    """
                    INSERT INTO auditoria
                    (
                        tenant_id,
                        consulta_id,
                        iteracion,
                        accion,
                        detalle,
                        entry_hash,
                        prev_hash
                    )
                    VALUES (
                        (SELECT tenant_id FROM consultas WHERE id = %s),
                        %s,%s,%s,%s,%s,%s
                    )
                    """,
                    (
                        cid,
                        cid,
                        it,
                        accion,
                        detalle_json,
                        entry_hash,
                        prev_hash,
                    ),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    logger.info(
        "AUDIT | consulta=%s iter=%s accion=%s prev=%s",
        cid,
        it,
        accion,
        prev_hash,
    )


def guardar_evaluacion_final(
    cid,
    texto,
    iteraciones,
    se_abstuvo=False,
):

    db_exec(
        """
        INSERT INTO evaluaciones_finales
        (
            tenant_id,
            consulta_id,
            evaluacion_final,
            iteraciones_realizadas,
            abstuvo
        )
        VALUES (
            (SELECT tenant_id FROM consultas WHERE id = %s),
            %s,%s,%s,%s
        )
        """,
        (
            cid,
            cid,
            texto,
            iteraciones,
            se_abstuvo,
        ),
    )


def registrar_metrica(
    cid,
    se_abstuvo,
    riesgo,
    confianza,
    evidencia,
    iteraciones,
    duracion,
):

    db_exec(
        """
        INSERT INTO metricas_seguridad
        (
            tenant_id,
            consulta_id,
            se_abstuvo,
            nivel_riesgo,
            confianza_final,
            evidencia_suficiente,
            iteraciones,
            duracion_seg
        )
        VALUES (
            (SELECT tenant_id FROM consultas WHERE id = %s),
            %s,%s,%s,%s,%s,%s,%s
        )
        """,
        (
            cid,
            cid,
            se_abstuvo,
            riesgo,
            confianza,
            evidencia,
            iteraciones,
            duracion,
        ),
    )
