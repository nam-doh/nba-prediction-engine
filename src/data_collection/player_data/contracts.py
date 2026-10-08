"""Shared validation and provenance helpers for player-data adapters."""

from __future__ import annotations

from datetime import date, datetime, timezone
from math import isfinite
from typing import Any


class PlayerDataError(RuntimeError):
    """Base exception for player-data ingestion."""


class ProviderError(PlayerDataError):
    """The upstream provider failed or returned an unusable response."""


class ValidationError(PlayerDataError):
    """Provider data violated the normalized contract."""


def utc_datetime(value: datetime, field: str = "timestamp") -> datetime:
    """Return a timezone-aware timestamp normalized to UTC."""
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValidationError(f"{field} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def utc_text(value: datetime, field: str = "timestamp") -> str:
    return utc_datetime(value, field).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def parse_utc_text(value: str, field: str = "timestamp") -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be a non-empty UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"{field} is not a valid timestamp: {value!r}") from exc
    return utc_datetime(parsed, field)


def require_text(value: Any, field: str) -> str:
    if value is None:
        raise ValidationError(f"{field} is required")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} is required")
    return normalized


def require_positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be a positive integer")
    try:
        normalized = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be a positive integer") from exc
    if normalized <= 0:
        raise ValidationError(f"{field} must be a positive integer")
    return normalized


def optional_number(value: Any, field: str) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be numeric or null")
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be numeric or null") from exc
    if not isfinite(normalized):
        raise ValidationError(f"{field} must be finite")
    return normalized


def require_nonnegative_number(value: Any, field: str) -> float:
    normalized = optional_number(value, field)
    if normalized is None or normalized < 0:
        raise ValidationError(f"{field} must be a non-negative number")
    return normalized


def require_date(value: Any, field: str) -> str:
    text = require_text(value, field)
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        pass
    for pattern in ("%Y-%m-%dT%H:%M:%S", "%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    raise ValidationError(f"{field} is not a recognized date: {text!r}")


def result_set(payload: Any, name: str) -> tuple[list[str], list[list[Any]]]:
    """Extract an NBA stats result set without depending on pandas."""
    if not isinstance(payload, dict):
        raise ProviderError("provider response must be a JSON object")
    result_sets = payload.get("resultSets", payload.get("resultSet"))
    if isinstance(result_sets, dict):
        result_sets = [result_sets]
    if not isinstance(result_sets, list):
        raise ProviderError("provider response has no result sets")
    for item in result_sets:
        if not isinstance(item, dict) or item.get("name") != name:
            continue
        headers = item.get("headers")
        rows = item.get("rowSet")
        if not isinstance(headers, list) or not all(
            isinstance(header, str) for header in headers
        ):
            raise ProviderError(f"{name} has invalid headers")
        if len(set(headers)) != len(headers):
            raise ProviderError(f"{name} has duplicate headers")
        if not isinstance(rows, list):
            raise ProviderError(f"{name} has invalid rows")
        for row in rows:
            if not isinstance(row, list) or len(row) != len(headers):
                raise ProviderError(f"{name} row width does not match its headers")
        return headers, rows
    raise ProviderError(f"provider response has no {name} result set")


def rows_as_dicts(payload: Any, name: str) -> list[dict[str, Any]]:
    headers, rows = result_set(payload, name)
    return [dict(zip(headers, row, strict=True)) for row in rows]
