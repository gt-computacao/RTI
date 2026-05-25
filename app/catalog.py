from __future__ import annotations

from typing import Tuple

from app.templating import APPLICATION_FIELDS, PROGRAM_TYPES


def parse_catalog_entry(entry: str) -> Tuple[str, str]:
    """Parse 'AD01 - Label...' into (code, full_label)."""
    entry = entry.strip()
    if " - " in entry:
        code, label = entry.split(" - ", 1)
        return code.strip(), entry
    return entry[:10], entry
