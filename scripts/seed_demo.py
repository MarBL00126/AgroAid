#!/usr/bin/env python3
"""
Seed script — inserts 3 demo tenants with admin users and branding.

Usage:
    python scripts/seed_demo.py

Environment variables required (same as the main app):
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
"""

from __future__ import annotations

import pathlib
import sys

# Allow running from any directory
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from core.database import close_pool, get_conn, init_pool
from core.security import hash_password

DEMO_TENANTS = [
    {
        "slug": "acopio",
        "name": "Acopio Demo",
        "admin_username": "admin_acopio",
        "admin_email": "admin@acopio.demo",
        "admin_password": "Demo1234!",
        "branding": {
            "app_name": "AgroAid — Acopio",
            "primary_color": "#16a34a",
            "accent_color": "#15803d",
            "logo_url": "",
            "footer_text": "Acopio Demo — AgroSafety",
        },
    },
    {
        "slug": "veterinaria",
        "name": "Veterinaria Demo",
        "admin_username": "admin_vet",
        "admin_email": "admin@veterinaria.demo",
        "admin_password": "Demo1234!",
        "branding": {
            "app_name": "AgroAid — Veterinaria",
            "primary_color": "#0284c7",
            "accent_color": "#0369a1",
            "logo_url": "",
            "footer_text": "Veterinaria Demo — AgroSafety",
        },
    },
    {
        "slug": "municipio",
        "name": "Municipio Demo",
        "admin_username": "admin_municipio",
        "admin_email": "admin@municipio.demo",
        "admin_password": "Demo1234!",
        "branding": {
            "app_name": "AgroAid — Municipio",
            "primary_color": "#7c3aed",
            "accent_color": "#6d28d9",
            "logo_url": "",
            "footer_text": "Municipio Demo — AgroSafety",
        },
    },
]


def seed() -> None:
    print("Connecting to database…")
    init_pool()

    with get_conn() as conn:
        with conn.cursor() as cur:
            for tenant_data in DEMO_TENANTS:
                slug = tenant_data["slug"]
                print(f"\n[{slug}]")

                cur.execute(
                    """
                    INSERT INTO tenants (slug, name)
                    VALUES (%s, %s)
                    ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
                    RETURNING id
                    """,
                    (slug, tenant_data["name"]),
                )
                tenant_id = cur.fetchone()[0]
                print(f"  tenant id={tenant_id}")

                b = tenant_data["branding"]
                cur.execute(
                    """
                    INSERT INTO tenant_branding
                        (tenant_id, logo_url, primary_color, accent_color, app_name, footer_text)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (tenant_id) DO UPDATE SET
                        logo_url      = EXCLUDED.logo_url,
                        primary_color = EXCLUDED.primary_color,
                        accent_color  = EXCLUDED.accent_color,
                        app_name      = EXCLUDED.app_name,
                        footer_text   = EXCLUDED.footer_text
                    """,
                    (
                        tenant_id,
                        b["logo_url"],
                        b["primary_color"],
                        b["accent_color"],
                        b["app_name"],
                        b["footer_text"],
                    ),
                )
                print(f"  branding set ({b['primary_color']})")

                password_hash = hash_password(tenant_data["admin_password"])
                cur.execute(
                    """
                    INSERT INTO users (tenant_id, username, email, password_hash, role)
                    VALUES (%s, %s, %s, %s, 'admin')
                    ON CONFLICT (email) DO NOTHING
                    """,
                    (
                        tenant_id,
                        tenant_data["admin_username"],
                        tenant_data["admin_email"],
                        password_hash,
                    ),
                )
                print(f"  user {tenant_data['admin_email']} / {tenant_data['admin_password']}")

        conn.commit()

    close_pool()
    print("\nDemo seed completed successfully.")
    print("\nCredentials:")
    for t in DEMO_TENANTS:
        print(f"  {t['admin_email']}  /  {t['admin_password']}  (slug: {t['slug']})")


if __name__ == "__main__":
    seed()
