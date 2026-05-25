from __future__ import annotations

from typing import Dict, List, Tuple

from app.services.participation import (
    InstitutionInput,
    validate_author_global_shares,
    validate_authors_match_institutions,
    validate_institution_shares,
)
from app.services.pi_institutions_form import parse_institutions_from_form


def parse_coauthors_from_form(form, user_email: str) -> Tuple[List[dict], List[str], List[str]]:
    names = form.getlist("coauthor_name")
    emails = form.getlist("coauthor_email")
    percentages = form.getlist("coauthor_percentage")
    inst_keys = form.getlist("coauthor_institution_key")

    coauthors: List[dict] = []
    errors: List[str] = []
    seen = {user_email.lower()}

    for idx, (nm, em, pc) in enumerate(zip(names, emails, percentages)):
        nm = (nm or "").strip()
        em = (em or "").strip().lower()
        pc = (pc or "").strip().replace(",", ".")
        key = (inst_keys[idx] if idx < len(inst_keys) else "ifms").strip() or "ifms"
        if not nm and not em and not pc:
            continue
        if not nm or not em or not pc:
            errors.append("Coautor com dados incompletos.")
            continue
        if em in seen:
            errors.append(f"Email duplicado: {em}")
            continue
        try:
            pcv = float(pc)
        except ValueError:
            errors.append(f"Porcentagem inválida para {em}.")
            continue
        seen.add(em)
        coauthors.append({"name": nm, "email": em, "percentage": pcv, "institution_key": key})

    return coauthors, inst_keys, errors


def validate_participation_form(
    form,
    user_email: str,
    primary_percentage_raw: str,
) -> Tuple[List[InstitutionInput], float, List[dict], List[str]]:
    errors: List[str] = []

    institutions = parse_institutions_from_form(form)
    errors.extend(validate_institution_shares(institutions))

    try:
        primary_pct = float((primary_percentage_raw or "").replace(",", "."))
    except ValueError:
        primary_pct = 0.0
        errors.append("A porcentagem do autor principal é inválida.")

    coauthors, coauthor_keys, coauthor_errors = parse_coauthors_from_form(form, user_email)
    errors.extend(coauthor_errors)

    errors.extend(validate_author_global_shares(primary_pct, coauthors))

    primary_key = (form.get("primary_institution_key") or "ifms").strip() or "ifms"
    errors.extend(
        validate_authors_match_institutions(
            institutions,
            primary_key,
            [c["institution_key"] for c in coauthors],
            primary_pct,
            coauthors,
        )
    )

    return institutions, primary_pct, coauthors, errors
