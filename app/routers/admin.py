from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.deps import require_admin
from app.models import (
    AdminNotification,
    ApplicationField,
    Document,
    NotificationType,
    PI,
    PIAuthor,
    PIStatus,
    ProgramType,
    User,
    UserRole,
    pi_application_fields,
    pi_program_types,
)
from app.templating import IFMS_CAMPUSES, STATUS_LABELS, templates

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get("", name="admin_panel")
async def admin_panel(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    campus_filter = request.query_params.get("campus", "").strip()
    status_filter = request.query_params.get("status", "").strip()
    admin_msg = request.query_params.get("admin_msg", "").strip()
    admin_error = request.query_params.get("admin_error", "").strip()

    q = (
        db.query(PI)
        .options(
            selectinload(PI.authors).selectinload(PIAuthor.profile),
            selectinload(PI.owner),
        )
        .filter(PI.deleted_at.is_(None))
    )

    if status_filter:
        q = q.filter(PI.status == status_filter)

    pis = q.order_by(PI.created_at.desc()).all()

    # Filter by campus (from primary author's profile)
    if campus_filter:
        filtered = []
        for pi in pis:
            primary = next((a for a in pi.authors if a.is_primary), None)
            if primary and primary.profile and primary.profile.campus == campus_filter:
                filtered.append(pi)
        pis = filtered

    # Notifications
    unread_count = db.query(AdminNotification).filter(AdminNotification.is_read == False).count()  # noqa: E712
    notifications = (
        db.query(AdminNotification)
        .order_by(AdminNotification.created_at.desc())
        .limit(50)
        .all()
    )

    admins = (
        db.query(User)
        .filter(User.role == UserRole.admin)
        .order_by(User.name)
        .all()
    )

    return templates.TemplateResponse(
        request, "admin/panel.html",
        {
            "user": user,
            "pis": pis,
            "campuses": IFMS_CAMPUSES,
            "status_labels": STATUS_LABELS,
            "campus_filter": campus_filter,
            "status_filter": status_filter,
            "notifications": notifications,
            "unread_count": unread_count,
            "admins": admins,
            "admin_msg": admin_msg,
            "admin_error": admin_error,
        },
    )


@router.post("/admins", name="admin_add_admin")
async def add_admin(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    form = await request.form()
    email = (form.get("email") or "").strip().lower()
    name = (form.get("name") or "").strip()

    if not email:
        return RedirectResponse(url="/admin?admin_error=Informe+o+email", status_code=303)
    if "@" not in email:
        return RedirectResponse(url="/admin?admin_error=Email+inválido", status_code=303)

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        if existing.role != UserRole.admin:
            existing.role = UserRole.admin
            if name:
                existing.name = name
            db.commit()
        return RedirectResponse(
            url="/admin?admin_msg=Administrador+atualizado:+"
            + email.replace("@", "%40"),
            status_code=303,
        )

    db.add(User(name=name or email.split("@")[0], email=email, role=UserRole.admin))
    db.commit()
    return RedirectResponse(
        url="/admin?admin_msg=Novo+administrador:+"
        + email.replace("@", "%40"),
        status_code=303,
    )


@router.post("/admins/{admin_id}/revoke", name="admin_revoke_admin")
async def revoke_admin(
    admin_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    admin_count = db.query(User).filter(User.role == UserRole.admin).count()
    if admin_count <= 1:
        return RedirectResponse(
            url="/admin?admin_error=Não+é+possível+remover+o+último+administrador",
            status_code=303,
        )

    target = db.get(User, admin_id)
    if not target or target.role != UserRole.admin:
        raise HTTPException(status_code=404)

    if target.id == user.id:
        return RedirectResponse(
            url="/admin?admin_error=Você+não+pode+remover+a+si+mesmo",
            status_code=303,
        )

    target.role = UserRole.author
    db.commit()
    return RedirectResponse(url="/admin?admin_msg=Administrador+removido", status_code=303)


@router.post("/pis/{pi_id}/return-for-correction", name="admin_return_correction")
async def return_for_correction(
    pi_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    pi = db.query(PI).options(selectinload(PI.documents)).filter(PI.id == pi_id).first()
    if not pi:
        raise HTTPException(status_code=404)

    form = await request.form()
    notes = (form.get("admin_notes") or "").strip()

    pi.status = PIStatus.awaiting_corrections
    pi.admin_notes = notes
    pi.completed_at = None

    # Reset signed status on all documents
    for doc in pi.documents:
        doc.is_signed = False
        doc.signed_file_path = None

    db.commit()

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            '<span class="badge badge-awaiting_corrections">Aguardando correções</span>'
        )
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/pis/{pi_id}/delete", name="admin_delete_pi")
async def delete_pi(
    pi_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    pi = db.query(PI).filter(PI.id == pi_id).first()
    if not pi:
        raise HTTPException(status_code=404)

    pi.deleted_at = _utcnow()
    db.commit()

    if request.headers.get("HX-Request"):
        return HTMLResponse("")
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/notifications/{notif_id}/read", name="admin_notif_read")
async def mark_notification_read(
    notif_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    notif = db.get(AdminNotification, notif_id)
    if not notif:
        raise HTTPException(status_code=404)
    notif.is_read = True
    db.commit()

    if request.headers.get("HX-Request"):
        return HTMLResponse("")
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/notifications/read-all", name="admin_notif_read_all")
async def mark_all_notifications_read(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    db.query(AdminNotification).filter(AdminNotification.is_read == False).update(  # noqa: E712
        {"is_read": True}
    )
    db.commit()

    if request.headers.get("HX-Request"):
        return HTMLResponse('<span class="muted">Todas lidas</span>')
    return RedirectResponse(url="/admin", status_code=303)


# ---------------------------------------------------------------------------
# CRUD: catálogos (application_fields / program_types)
# ---------------------------------------------------------------------------

_CATALOG_MODELS = {
    "application-fields": (ApplicationField, pi_application_fields, "application_field_id"),
    "program-types": (ProgramType, pi_program_types, "program_type_id"),
}


def _catalogs_redirect(
    msg: str | None = None,
    error: str | None = None,
    tab: str | None = None,
) -> RedirectResponse:
    params = []
    if msg:
        params.append("catalog_msg=" + quote(msg))
    if error:
        params.append("catalog_error=" + quote(error))
    if tab:
        params.append("tab=" + quote(tab))
    suffix = ("?" + "&".join(params)) if params else ""
    return RedirectResponse(url="/admin/catalogs" + suffix, status_code=303)


def _validate_catalog_input(form_code: str, form_label: str) -> tuple[str, str] | str:
    code = (form_code or "").strip()
    label = (form_label or "").strip()
    if not code:
        return "Informe o código"
    if len(code) > 10:
        return "O código deve ter no máximo 10 caracteres"
    if not label:
        return "Informe o rótulo (label)"
    if len(label) > 500:
        return "O rótulo deve ter no máximo 500 caracteres"
    return code, label


def _count_usages(db: Session, assoc_table, fk_column_name: str, item_id: int) -> int:
    fk_col = assoc_table.c[fk_column_name]
    return db.query(func.count()).select_from(assoc_table).filter(fk_col == item_id).scalar() or 0


@router.get("/catalogs", name="admin_catalogs")
async def admin_catalogs(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    catalog_msg = request.query_params.get("catalog_msg", "").strip()
    catalog_error = request.query_params.get("catalog_error", "").strip()

    app_fields = db.query(ApplicationField).order_by(ApplicationField.code).all()
    prog_types = db.query(ProgramType).order_by(ProgramType.code).all()

    def usage_map(assoc_table, fk_name: str, items):
        if not items:
            return {}
        fk_col = assoc_table.c[fk_name]
        rows = (
            db.query(fk_col, func.count())
            .group_by(fk_col)
            .all()
        )
        return {row[0]: row[1] for row in rows}

    app_field_usage = usage_map(pi_application_fields, "application_field_id", app_fields)
    prog_type_usage = usage_map(pi_program_types, "program_type_id", prog_types)

    return templates.TemplateResponse(
        request,
        "admin/catalogs.html",
        {
            "user": user,
            "application_fields": app_fields,
            "program_types": prog_types,
            "application_field_usage": app_field_usage,
            "program_type_usage": prog_type_usage,
            "catalog_msg": catalog_msg,
            "catalog_error": catalog_error,
        },
    )


@router.post("/{kind}/create", name="admin_catalog_create")
async def admin_catalog_create(
    kind: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    if kind not in _CATALOG_MODELS:
        raise HTTPException(status_code=404)
    Model, _assoc, _fk = _CATALOG_MODELS[kind]

    form = await request.form()
    validated = _validate_catalog_input(form.get("code"), form.get("label"))
    if isinstance(validated, str):
        return _catalogs_redirect(error=validated, tab=kind)
    code, label = validated

    existing = db.query(Model).filter(Model.code == code).first()
    if existing:
        return _catalogs_redirect(error=f"Já existe um item com o código '{code}'", tab=kind)

    db.add(Model(code=code, label=label))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _catalogs_redirect(error=f"Já existe um item com o código '{code}'", tab=kind)

    return _catalogs_redirect(msg=f"Item '{code}' criado", tab=kind)


@router.post("/{kind}/{item_id}/update", name="admin_catalog_update")
async def admin_catalog_update(
    kind: str,
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    if kind not in _CATALOG_MODELS:
        raise HTTPException(status_code=404)
    Model, _assoc, _fk = _CATALOG_MODELS[kind]

    item = db.get(Model, item_id)
    if not item:
        raise HTTPException(status_code=404)

    form = await request.form()
    validated = _validate_catalog_input(form.get("code"), form.get("label"))
    if isinstance(validated, str):
        return _catalogs_redirect(error=validated, tab=kind)
    code, label = validated

    if code != item.code:
        clash = db.query(Model).filter(Model.code == code, Model.id != item.id).first()
        if clash:
            return _catalogs_redirect(error=f"Já existe um item com o código '{code}'", tab=kind)

    item.code = code
    item.label = label
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _catalogs_redirect(error=f"Já existe um item com o código '{code}'", tab=kind)

    return _catalogs_redirect(msg=f"Item '{code}' atualizado", tab=kind)


@router.post("/{kind}/{item_id}/delete", name="admin_catalog_delete")
async def admin_catalog_delete(
    kind: str,
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    if kind not in _CATALOG_MODELS:
        raise HTTPException(status_code=404)
    Model, assoc, fk_name = _CATALOG_MODELS[kind]

    item = db.get(Model, item_id)
    if not item:
        raise HTTPException(status_code=404)

    code = item.code
    usages = _count_usages(db, assoc, fk_name, item.id)
    db.delete(item)
    db.commit()

    note = f" (vínculos com {usages} PI{'s' if usages != 1 else ''} removidos)" if usages else ""
    return _catalogs_redirect(msg=f"Item '{code}' removido{note}", tab=kind)
