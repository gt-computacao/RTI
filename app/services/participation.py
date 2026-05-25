from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Union

from app.models import PI, PIAuthor, PIInstitution

AuthorLike = Union[PIAuthor, dict]
InstitutionLike = Union[PIInstitution, dict]


@dataclass
class InstitutionInput:
    name: str
    percentage: float
    is_ifms: bool = False
    cnpj: Optional[str] = None
    contact: Optional[str] = None
    sort_order: int = 0
    client_key: str = ""


def _pct(value) -> float:
    return float(value or 0)


def has_external_partners(pi: PI) -> bool:
    return any(not inst.is_ifms for inst in (pi.institutions or []))


def get_ifms_institution(pi: PI) -> Optional[PIInstitution]:
    for inst in pi.institutions or []:
        if inst.is_ifms:
            return inst
    return None


def authors_grouped_by_institution(pi: PI) -> Dict[PIInstitution, List[PIAuthor]]:
    groups: Dict[PIInstitution, List[PIAuthor]] = {inst: [] for inst in (pi.institutions or [])}
    for author in pi.authors or []:
        if author.institution in groups:
            groups[author.institution].append(author)
    return groups


def institution_author_total(institution: PIInstitution, authors: Sequence[PIAuthor]) -> float:
    peers = [a for a in authors if a.institution_id == institution.id]
    return sum(_pct(a.percentage) for a in peers)


def within_institution_percent(author: PIAuthor, peers: Sequence[PIAuthor]) -> float:
    total = institution_author_total(author.institution, peers)
    if total <= 0:
        return _pct(author.percentage)
    return (_pct(author.percentage) / total) * 100.0


def validate_institution_shares(institutions: Sequence[InstitutionInput]) -> List[str]:
    errors: List[str] = []
    if not institutions:
        errors.append("Cadastre a instituição IFMS.")
        return errors

    ifms_rows = [i for i in institutions if i.is_ifms]
    if len(ifms_rows) != 1:
        errors.append("Deve existir exatamente uma instituição IFMS.")

    total = sum(i.percentage for i in institutions)
    if abs(total - 100.0) > 0.01:
        errors.append(f"A soma das porcentagens das instituições deve ser 100% (atual: {total:g}%).")

    for inst in institutions:
        if not inst.is_ifms:
            if not (inst.name or "").strip():
                errors.append("Informe o nome de cada instituição parceira.")
            if inst.percentage <= 0:
                errors.append(f"Informe a porcentagem de titularidade de {inst.name or 'parceira'}.")

    return errors


def validate_author_global_shares(
    primary_percentage: float,
    coauthors: Sequence[dict],
) -> List[str]:
    total = primary_percentage + sum(_pct(c.get("percentage")) for c in coauthors)
    if abs(total - 100.0) > 0.01:
        return [f"A soma das porcentagens dos participantes deve ser 100% (atual: {total:g}%)."]
    return []


def validate_authors_match_institutions(
    institutions: Sequence[InstitutionInput],
    primary_institution_key: str,
    coauthor_institution_keys: Sequence[str],
    primary_percentage: float,
    coauthors: Sequence[dict],
) -> List[str]:
    errors: List[str] = []
    keys = {i.client_key for i in institutions if i.client_key}
    ifms_key = next((i.client_key for i in institutions if i.is_ifms), "ifms")

    if primary_institution_key and primary_institution_key not in keys:
        errors.append("Instituição do autor principal inválida.")
    if not primary_institution_key:
        primary_institution_key = ifms_key

    for idx, key in enumerate(coauthor_institution_keys):
        if key and key not in keys:
            errors.append(f"Instituição do coautor {idx + 1} inválida.")

    authors_by_key: Dict[str, float] = {}
    authors_by_key[primary_institution_key] = authors_by_key.get(primary_institution_key, 0) + primary_percentage
    for c, key in zip(coauthors, coauthor_institution_keys):
        k = key or ifms_key
        authors_by_key[k] = authors_by_key.get(k, 0) + _pct(c.get("percentage"))

    for inst in institutions:
        if inst.percentage > 0 and authors_by_key.get(inst.client_key, 0) <= 0:
            errors.append(
                f"A instituição {inst.name} tem titularidade na PI, mas nenhum participante foi vinculado a ela."
            )

    return errors
