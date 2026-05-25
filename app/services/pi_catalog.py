from __future__ import annotations

from typing import List, Tuple

from sqlalchemy.orm import Session

from app.models import ApplicationField, PI, ProgramType


def parse_ids_from_form(form, key: str) -> List[int]:
    seen: set[int] = set()
    result: List[int] = []
    for raw in form.getlist(key):
        try:
            val = int(raw)
        except (TypeError, ValueError):
            continue
        if val > 0 and val not in seen:
            seen.add(val)
            result.append(val)
    return result


def load_catalogs(db: Session) -> Tuple[List[ApplicationField], List[ProgramType]]:
    app_fields = db.query(ApplicationField).order_by(ApplicationField.code).all()
    prog_types = db.query(ProgramType).order_by(ProgramType.code).all()
    return app_fields, prog_types


def assign_pi_catalogs(
    db: Session,
    pi: PI,
    application_field_ids: List[int],
    program_type_ids: List[int],
) -> Tuple[List[ApplicationField], List[ProgramType]]:
    app_fields = (
        db.query(ApplicationField)
        .filter(ApplicationField.id.in_(application_field_ids))
        .all()
        if application_field_ids
        else []
    )
    prog_types = (
        db.query(ProgramType)
        .filter(ProgramType.id.in_(program_type_ids))
        .all()
        if program_type_ids
        else []
    )
    pi.application_fields = app_fields
    pi.program_types = prog_types
    return app_fields, prog_types
