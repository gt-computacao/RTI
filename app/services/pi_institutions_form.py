from __future__ import annotations

import uuid
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import PI, PIInstitution
from app.services.participation import InstitutionInput


def _parse_float(raw: str, default: float = 0.0) -> float:
    try:
        return float((raw or "").replace(",", "."))
    except ValueError:
        return default


def parse_institutions_from_form(form) -> List[InstitutionInput]:
    ifms_pct = _parse_float(form.get("ifms_institution_percentage") or "100", 100.0)
    institutions = [
        InstitutionInput(
            name="IFMS",
            percentage=ifms_pct,
            is_ifms=True,
            client_key="ifms",
            sort_order=0,
        )
    ]

    names = form.getlist("partner_institution_name")
    pcts = form.getlist("partner_institution_percentage")
    cnpjs = form.getlist("partner_institution_cnpj")
    contacts = form.getlist("partner_institution_contact")
    keys = form.getlist("partner_institution_key")

    for idx, name in enumerate(names):
        name = (name or "").strip()
        if not name:
            continue
        key = keys[idx].strip() if idx < len(keys) and keys[idx] else f"partner-{idx}"
        institutions.append(
            InstitutionInput(
                name=name,
                percentage=_parse_float(pcts[idx] if idx < len(pcts) else "0"),
                is_ifms=False,
                cnpj=(cnpjs[idx] or "").strip() or None if idx < len(cnpjs) else None,
                contact=(contacts[idx] or "").strip() or None if idx < len(contacts) else None,
                client_key=key,
                sort_order=idx + 1,
            )
        )
    return institutions


def save_institutions(
    db: Session,
    pi: PI,
    institutions: List[InstitutionInput],
) -> Dict[str, PIInstitution]:
    key_map: Dict[str, PIInstitution] = {}
    for inst_in in institutions:
        row = PIInstitution(
            pi_id=pi.id,
            name=inst_in.name,
            is_ifms=inst_in.is_ifms,
            percentage=inst_in.percentage,
            cnpj=inst_in.cnpj,
            contact=inst_in.contact,
            sort_order=inst_in.sort_order,
        )
        db.add(row)
        db.flush()
        key_map[inst_in.client_key] = row
    return key_map


def replace_institutions(
    db: Session,
    pi: PI,
    institutions: List[InstitutionInput],
) -> Dict[str, PIInstitution]:
    old_insts = list(pi.institutions or [])
    old_ids = {inst.id for inst in old_insts}
    key_map = save_institutions(db, pi, institutions)
    new_ids = [row.id for row in key_map.values()]
    fallback_id = new_ids[0] if new_ids else None
    if fallback_id is not None:
        for author in list(getattr(pi, "authors", None) or []):
            if author.institution_id in old_ids or author.institution_id is None:
                author.institution_id = fallback_id
        db.flush()
    for inst in old_insts:
        db.delete(inst)
    db.flush()
    return key_map


def institutions_for_template(pi: Optional[PI]) -> Tuple[dict, List[dict]]:
    """Build form dict slice + partner rows for edit/create template."""
    ifms_pct = "100"
    partners: List[dict] = []
    if pi and pi.institutions:
        for inst in sorted(pi.institutions, key=lambda x: x.sort_order):
            if inst.is_ifms:
                ifms_pct = str(float(inst.percentage))
            else:
                partners.append(
                    {
                        "key": f"partner-{inst.id}",
                        "name": inst.name,
                        "percentage": str(float(inst.percentage)),
                        "cnpj": inst.cnpj or "",
                        "contact": inst.contact or "",
                    }
                )
    return {"ifms_institution_percentage": ifms_pct}, partners


def new_partner_key() -> str:
    return f"partner-new-{uuid.uuid4().hex[:8]}"


def partners_from_form_lists(form) -> List[dict]:
    names = form.getlist("partner_institution_name")
    pcts = form.getlist("partner_institution_percentage")
    cnpjs = form.getlist("partner_institution_cnpj")
    contacts = form.getlist("partner_institution_contact")
    keys = form.getlist("partner_institution_key")
    rows: List[dict] = []
    for idx, name in enumerate(names):
        name = (name or "").strip()
        if not name:
            continue
        rows.append(
            {
                "key": keys[idx].strip() if idx < len(keys) and keys[idx] else f"partner-{idx}",
                "name": name,
                "percentage": pcts[idx] if idx < len(pcts) else "",
                "cnpj": cnpjs[idx] if idx < len(cnpjs) else "",
                "contact": contacts[idx] if idx < len(contacts) else "",
            }
        )
    return rows


def institution_options(pi: Optional[PI], partners: List[dict]) -> List[dict]:
    opts = [{"key": "ifms", "name": "IFMS"}]
    for p in partners:
        opts.append({"key": p["key"], "name": p["name"]})
    if pi:
        for inst in pi.institutions or []:
            if not inst.is_ifms:
                key = f"partner-{inst.id}"
                if not any(o["key"] == key for o in opts):
                    opts.append({"key": key, "name": inst.name})
    return opts
