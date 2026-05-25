from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.models import User, UserRole


def get_admin_emails(db: Session) -> List[str]:
    rows = db.query(User.email).filter(User.role == UserRole.admin).all()
    return [r[0] for r in rows if r[0]]
