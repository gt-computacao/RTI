#!/usr/bin/env python3
"""Seed default admin user in the database.

Usage (inside Docker container):
    docker compose exec app python scripts/seed_admin.py --email admin@ifms.edu.br --name "Admin IFMS"

Or without arguments (uses SEED_ADMIN_EMAIL / SEED_ADMIN_NAME from .env):
    docker compose exec app python scripts/seed_admin.py
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.database import SessionLocal
from app.models import User, UserRole


def seed_admin(email: str, name: str) -> None:
    email = email.lower().strip()
    with SessionLocal() as db:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            if existing.role != UserRole.admin:
                existing.role = UserRole.admin
                db.commit()
                print(f"User '{email}' promoted to admin.")
            else:
                print(f"User '{email}' is already an admin.")
            return

        user = User(
            name=name,
            email=email,
            role=UserRole.admin,
        )
        db.add(user)
        db.commit()
        print(f"Admin user created: {email} (name={name})")


def main():
    parser = argparse.ArgumentParser(description="Seed admin user")
    parser.add_argument("--email", type=str, default=None, help="Admin email")
    parser.add_argument("--name", type=str, default=None, help="Admin name")
    args = parser.parse_args()

    email = args.email or settings.seed_admin_email
    name = args.name or settings.seed_admin_name

    if not email:
        print("ERROR: No --email provided and SEED_ADMIN_EMAIL is empty")
        sys.exit(1)

    seed_admin(email, name)


if __name__ == "__main__":
    main()
