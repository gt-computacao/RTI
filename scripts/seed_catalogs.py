#!/usr/bin/env python3
"""Seed application_fields and program_types catalogs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.catalog import parse_catalog_entry
from app.database import SessionLocal
from app.models import ApplicationField, ProgramType
from app.templating import APPLICATION_FIELDS, PROGRAM_TYPES


def seed_catalogs() -> None:
    with SessionLocal() as db:
        for entry in APPLICATION_FIELDS:
            code, label = parse_catalog_entry(entry)
            existing = db.query(ApplicationField).filter(ApplicationField.code == code).first()
            if existing:
                existing.label = label
            else:
                db.add(ApplicationField(code=code, label=label))

        for entry in PROGRAM_TYPES:
            code, label = parse_catalog_entry(entry)
            existing = db.query(ProgramType).filter(ProgramType.code == code).first()
            if existing:
                existing.label = label
            else:
                db.add(ProgramType(code=code, label=label))

        db.commit()
    print("Catalogs seeded: application_fields, program_types")


if __name__ == "__main__":
    seed_catalogs()
