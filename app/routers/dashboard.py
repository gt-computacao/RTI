from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import get_current_user, home_url_for
from app.models import AdminNotification, PI, PIAuthor, PIAuthorStatus, PIStatus, PIType, UserRole
from app.templating import IFMS_CAMPUSES, PI_TYPE_LABELS, STATUS_LABELS, templates

router = APIRouter()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _primary_campus(pi: PI) -> Optional[str]:
    primary = next((a for a in pi.authors if a.is_primary), None)
    if primary and primary.profile:
        return primary.profile.campus
    return None


@router.get("/", include_in_schema=False)
async def root(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(url=home_url_for(user), status_code=303)
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@router.get("/dashboard", name="dashboard")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)

    is_admin = user.role == UserRole.admin
    status_filter = request.query_params.get("status", "").strip()
    type_filter = request.query_params.get("type", "").strip()
    campus_filter = request.query_params.get("campus", "").strip()
    q_filter = request.query_params.get("q", "").strip()
    scope_filter = request.query_params.get("scope", "").strip()

    base_q = db.query(PI).options(
        selectinload(PI.authors),
        selectinload(PI.documents),
        selectinload(PI.owner),
        selectinload(PI.institutions),
    ).filter(PI.deleted_at.is_(None))

    if not is_admin:
        base_q = base_q.filter(PI.owner_id == user.id)

    stats_q = base_q
    stats: dict = {
        "total": stats_q.count(),
        "awaiting_authors": stats_q.filter(PI.status == PIStatus.awaiting_authors).count(),
        "awaiting_signatures": stats_q.filter(PI.status == PIStatus.awaiting_signatures).count(),
        "awaiting_corrections": stats_q.filter(PI.status == PIStatus.awaiting_corrections).count(),
        "completed": stats_q.filter(PI.status == PIStatus.completed).count(),
        "recent_30d": stats_q.filter(
            PI.created_at >= _utcnow() - timedelta(days=30)
        ).count(),
    }
    if is_admin:
        stats["unread_notifications"] = (
            db.query(AdminNotification)
            .filter(AdminNotification.is_read == False)  # noqa: E712
            .count()
        )

    q = base_q
    if status_filter:
        try:
            q = q.filter(PI.status == PIStatus(status_filter))
        except ValueError:
            pass
    if type_filter:
        try:
            q = q.filter(PI.type == PIType(type_filter))
        except ValueError:
            pass
    if q_filter:
        q = q.filter(PI.title.ilike(f"%{q_filter}%"))

    pis = q.order_by(PI.created_at.desc()).all()

    if campus_filter and is_admin:
        pis = [pi for pi in pis if _primary_campus(pi) == campus_filter]

    if scope_filter == "action_needed":
        filtered = []
        for pi in pis:
            if pi.status == PIStatus.awaiting_corrections:
                filtered.append(pi)
                continue
            pending_authors = any(
                a.status != PIAuthorStatus.completed for a in pi.authors
            )
            if pi.status == PIStatus.awaiting_authors and pending_authors:
                filtered.append(pi)
        pis = filtered

    has_filters = bool(status_filter or type_filter or campus_filter or q_filter or scope_filter)

    return templates.TemplateResponse(
        request, "dashboard.html",
        {
            "user": user,
            "pis": pis,
            "is_admin": is_admin,
            "stats": stats,
            "status_labels": STATUS_LABELS,
            "pi_type_labels": PI_TYPE_LABELS,
            "campuses": IFMS_CAMPUSES if is_admin else [],
            "status_filter": status_filter,
            "type_filter": type_filter,
            "campus_filter": campus_filter,
            "q_filter": q_filter,
            "scope_filter": scope_filter,
            "has_filters": has_filters,
            "result_count": len(pis),
        },
    )
