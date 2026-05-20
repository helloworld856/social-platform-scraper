from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


_LINE_BREAK_RE = re.compile(r"[\r\n\u2028\u2029]+")


def sanitize_csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    return _LINE_BREAK_RE.sub(" ", value).strip()


def sanitize_csv_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: sanitize_csv_cell(value) for key, value in row.items()}


def sanitize_csv_rows(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [sanitize_csv_row(row) for row in rows]
