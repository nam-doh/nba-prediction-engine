"""NBA.com roster ingestion with stable IDs and immutable snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import sleep
from typing import Any, Callable, Iterable
from urllib.parse import urlencode

from .contracts import (
    PlayerDataError,
    ProviderError,
    ValidationError,
    require_positive_int,
    require_text,
    rows_as_dicts,
    utc_text,
)
from .snapshots import SnapshotStore


PROVIDER = "nba_stats"
DATASET = "team_rosters"
ENDPOINT = "https://stats.nba.com/stats/commonteamroster"


@dataclass(frozen=True)
class RosterTeamResult:
    team_id: int
    records: tuple[dict[str, Any], ...]
    snapshot_path: Path
    from_cache: bool


@dataclass(frozen=True)
class RosterBatchResult:
    teams: tuple[RosterTeamResult, ...]
    failures: dict[int, str]

    @property
    def record_count(self) -> int:
        return sum(len(team.records) for team in self.teams)


def _default_fetcher(team_id: int, season: str, timeout: int) -> dict[str, Any]:
    from nba_api.stats.endpoints.commonteamroster import CommonTeamRoster

    try:
        return CommonTeamRoster(
            team_id=team_id,
            season=season,
            league_id_nullable="00",
            timeout=timeout,
        ).get_dict()
    except Exception as exc:
        raise ProviderError(f"NBA roster request failed for team {team_id}: {exc}") from exc


class NbaRosterAdapter:
    def __init__(
        self,
        snapshot_store: SnapshotStore,
        *,
        fetcher: Callable[[int, str, int], dict[str, Any]] | None = None,
        timeout: int = 30,
        clock: Callable[[], datetime] | None = None,
    ):
        self.snapshot_store = snapshot_store
        self.fetcher = fetcher or _default_fetcher
        self.timeout = timeout
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def request(team_id: int, season: str) -> dict[str, Any]:
        return {
            "team_id": require_positive_int(team_id, "team_id"),
            "season": require_text(season, "season"),
            "league_id": "00",
        }

    @staticmethod
    def source_url(request: dict[str, Any]) -> str:
        return f"{ENDPOINT}?{urlencode({'TeamID': request['team_id'], 'Season': request['season'], 'LeagueID': request['league_id']})}"

    def normalize(
        self,
        payload: Any,
        *,
        request: dict[str, Any],
        retrieved_at: datetime,
    ) -> list[dict[str, Any]]:
        rows = rows_as_dicts(payload, "CommonTeamRoster")
        if not rows:
            raise ProviderError("NBA roster response contains no players")
        source_url = self.source_url(request)
        retrieved_text = utc_text(retrieved_at, "retrieved_at")
        records: list[dict[str, Any]] = []
        identities: set[tuple[str, int, int]] = set()
        for row in rows:
            player_id = require_positive_int(row.get("PLAYER_ID"), "PLAYER_ID")
            team_id = require_positive_int(row.get("TeamID"), "TeamID")
            if team_id != request["team_id"]:
                raise ValidationError(
                    f"roster row team {team_id} does not match requested team {request['team_id']}"
                )
            identity = (request["season"], team_id, player_id)
            if identity in identities:
                raise ValidationError(f"duplicate roster identity {identity}")
            identities.add(identity)
            records.append(
                {
                    "season": request["season"],
                    "team_id": team_id,
                    "player_id": player_id,
                    "player_name": require_text(row.get("PLAYER"), "PLAYER"),
                    "player_slug": (
                        str(row["PLAYER_SLUG"]).strip()
                        if row.get("PLAYER_SLUG") not in (None, "")
                        else None
                    ),
                    "position": (
                        str(row["POSITION"]).strip()
                        if row.get("POSITION") not in (None, "")
                        else None
                    ),
                    "jersey_number": (
                        str(row["NUM"]).strip()
                        if row.get("NUM") not in (None, "")
                        else None
                    ),
                    "source_url": source_url,
                    "retrieved_at": retrieved_text,
                }
            )
        records.sort(key=lambda record: (record["team_id"], record["player_id"]))
        return records

    def refresh_team(
        self,
        team_id: int,
        season: str,
        *,
        max_cache_age: timedelta | None = timedelta(hours=1),
    ) -> RosterTeamResult:
        request = self.request(team_id, season)
        now = self.clock()
        utc_text(now, "retrieved_at")
        cached = self.snapshot_store.latest(
            provider=PROVIDER, dataset=DATASET, request=request
        )
        if cached and max_cache_age is not None:
            path, document = cached
            cached_at = datetime.fromisoformat(
                document["retrieved_at"].replace("Z", "+00:00")
            )
            age = now.astimezone(timezone.utc) - cached_at
            if timedelta(0) <= age <= max_cache_age:
                return RosterTeamResult(
                    team_id=request["team_id"],
                    records=tuple(document["records"]),
                    snapshot_path=path,
                    from_cache=True,
                )
        try:
            payload = self.fetcher(request["team_id"], request["season"], self.timeout)
        except PlayerDataError:
            raise
        except Exception as exc:
            raise ProviderError(
                f"NBA roster request failed for team {request['team_id']}: {exc}"
            ) from exc
        records = self.normalize(payload, request=request, retrieved_at=now)
        path = self.snapshot_store.write(
            provider=PROVIDER,
            dataset=DATASET,
            request=request,
            source_url=self.source_url(request),
            retrieved_at=now,
            records=records,
            raw_payload=payload,
        )
        return RosterTeamResult(
            team_id=request["team_id"],
            records=tuple(records),
            snapshot_path=path,
            from_cache=False,
        )

    def refresh_teams(
        self,
        team_ids: Iterable[int],
        season: str,
        *,
        delay_seconds: float = 3.0,
        max_cache_age: timedelta | None = timedelta(hours=1),
        sleeper: Callable[[float], None] = sleep,
    ) -> RosterBatchResult:
        if delay_seconds < 0:
            raise ValidationError("delay_seconds must be non-negative")
        normalized_ids = [require_positive_int(team_id, "team_id") for team_id in team_ids]
        if len(set(normalized_ids)) != len(normalized_ids):
            raise ValidationError("team_ids must not contain duplicates")
        teams: list[RosterTeamResult] = []
        failures: dict[int, str] = {}
        for index, team_id in enumerate(normalized_ids):
            try:
                result = self.refresh_team(
                    team_id, season, max_cache_age=max_cache_age
                )
                teams.append(result)
            except PlayerDataError as exc:
                failures[team_id] = str(exc)
                result = None
            if index < len(normalized_ids) - 1 and result is not None and not result.from_cache:
                sleeper(delay_seconds)
        return RosterBatchResult(tuple(teams), failures)
