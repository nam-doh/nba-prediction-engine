"""Immutable, timestamped JSON snapshots for player-data responses."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .contracts import ValidationError, parse_utc_text, require_text, utc_text


SCHEMA_VERSION = 1
_SECRET_QUERY_KEYS = {
    "access_token",
    "api-key",
    "api_key",
    "apikey",
    "key",
    "subscription-key",
    "token",
    "x-api-key",
}


class SnapshotError(RuntimeError):
    """A snapshot could not be written or verified safely."""


def _safe_component(value: str, field: str) -> str:
    normalized = require_text(value, field)
    if normalized in {".", ".."} or any(
        character in normalized for character in ("/", "\\", "\x00")
    ):
        raise SnapshotError(f"{field} is not a safe path component")
    if not all(character.isalnum() or character in "-_." for character in normalized):
        raise SnapshotError(f"{field} contains unsupported path characters")
    return normalized


def redact_source_url(url: str) -> str:
    normalized = require_text(url, "source_url")
    parts = urlsplit(normalized)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValidationError("source_url must be an absolute HTTP(S) URL")
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        query.append((key, "REDACTED" if key.lower() in _SECRET_QUERY_KEYS else value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def _canonical_bytes(document: Mapping[str, Any]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _pretty_bytes(document: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


class SnapshotStore:
    """Write and retrieve immutable provider snapshots beneath one root."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def write(
        self,
        *,
        provider: str,
        dataset: str,
        request: Mapping[str, Any],
        source_url: str,
        retrieved_at: datetime,
        records: Sequence[Mapping[str, Any]],
        raw_payload: Any,
        source_as_of: datetime | None = None,
    ) -> Path:
        provider = _safe_component(provider, "provider")
        dataset = _safe_component(dataset, "dataset")
        retrieved_text = utc_text(retrieved_at, "retrieved_at")
        if not isinstance(request, Mapping):
            raise SnapshotError("request must be a mapping")
        if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
            raise SnapshotError("records must be a sequence")

        body: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "provider": provider,
            "dataset": dataset,
            "request": dict(request),
            "source_url": redact_source_url(source_url),
            "retrieved_at": retrieved_text,
            "source_as_of": (
                utc_text(source_as_of, "source_as_of") if source_as_of else None
            ),
            "record_count": len(records),
            "records": [dict(record) for record in records],
            "raw_payload": raw_payload,
        }
        try:
            digest = hashlib.sha256(_canonical_bytes(body)).hexdigest()
        except (TypeError, ValueError) as exc:
            raise SnapshotError("snapshot content must be finite JSON data") from exc
        document = {**body, "content_sha256": digest}
        payload = _pretty_bytes(document)

        timestamp = parse_utc_text(retrieved_text).strftime("%Y%m%dT%H%M%S%fZ")
        moment = parse_utc_text(retrieved_text)
        directory = self.root / provider / dataset / moment.strftime("%Y/%m/%d")
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{timestamp}_{digest[:16]}.json"

        handle, temporary_name = tempfile.mkstemp(prefix=".snapshot-", dir=directory)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if destination.read_bytes() != payload:
                    raise SnapshotError(f"refusing to overwrite snapshot {destination}")
            return destination
        finally:
            temporary.unlink(missing_ok=True)

    def read(self, path: str | Path) -> dict[str, Any]:
        candidate = Path(path).resolve()
        if not candidate.is_relative_to(self.root):
            raise SnapshotError("snapshot path is outside the store")
        try:
            document = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SnapshotError(f"cannot read snapshot {candidate}") from exc
        if not isinstance(document, dict):
            raise SnapshotError("snapshot root must be an object")
        expected = document.get("content_sha256")
        body = {key: value for key, value in document.items() if key != "content_sha256"}
        actual = hashlib.sha256(_canonical_bytes(body)).hexdigest()
        if expected != actual:
            raise SnapshotError("snapshot content hash does not match")
        if document.get("schema_version") != SCHEMA_VERSION:
            raise SnapshotError("unsupported snapshot schema version")
        parse_utc_text(document.get("retrieved_at"), "retrieved_at")
        return document

    def latest(
        self,
        *,
        provider: str,
        dataset: str,
        request: Mapping[str, Any] | None = None,
    ) -> tuple[Path, dict[str, Any]] | None:
        provider = _safe_component(provider, "provider")
        dataset = _safe_component(dataset, "dataset")
        directory = self.root / provider / dataset
        if not directory.exists():
            return None
        matches: list[tuple[datetime, Path, dict[str, Any]]] = []
        for path in directory.glob("*/*/*/*.json"):
            document = self.read(path)
            if request is not None and document.get("request") != dict(request):
                continue
            matches.append((parse_utc_text(document["retrieved_at"]), path, document))
        if not matches:
            return None
        _, path, document = max(matches, key=lambda item: (item[0], str(item[1])))
        return path, document
