"""NBA.com season player-game-log ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

from .contracts import (
    PlayerDataError,
    ProviderError,
    ValidationError,
    optional_number,
    require_date,
    require_nonnegative_number,
    require_positive_int,
    require_text,
    rows_as_dicts,
    utc_text,
)
from .snapshots import SnapshotStore


PROVIDER = "nba_stats"
DATASET = "player_game_logs"
ENDPOINT = "https://stats.nba.com/stats/playergamelogs"
_OPTIONAL_STATS = {
    "field_goals_made": "FGM",
    "field_goals_attempted": "FGA",
    "three_pointers_made": "FG3M",
    "three_pointers_attempted": "FG3A",
    "free_throws_made": "FTM",
    "free_throws_attempted": "FTA",
    "offensive_rebounds": "OREB",
    "defensive_rebounds": "DREB",
    "rebounds": "REB",
    "assists": "AST",
    "turnovers": "TOV",
    "steals": "STL",
    "blocks": "BLK",
    "personal_fouls": "PF",
    "points": "PTS",
    "plus_minus": "PLUS_MINUS",
}


@dataclass(frozen=True)
class PlayerStatsResult:
    records: tuple[dict[str, Any], ...]
    snapshot_path: Path
    from_cache: bool


def _default_fetcher(season: str, season_type: str, timeout: int) -> dict[str, Any]:
    from nba_api.stats.endpoints.playergamelogs import PlayerGameLogs

    try:
        return PlayerGameLogs(
            season_nullable=season,
            season_type_nullable=season_type,
            league_id_nullable="00",
            timeout=timeout,
        ).get_dict()
    except Exception as exc:
        raise ProviderError(f"NBA player game-log request failed: {exc}") from exc


class NbaPlayerStatsAdapter:
    def __init__(
        self,
        snapshot_store: SnapshotStore,
        *,
        fetcher: Callable[[str, str, int], dict[str, Any]] | None = None,
        timeout: int = 30,
        clock: Callable[[], datetime] | None = None,
    ):
        self.snapshot_store = snapshot_store
        self.fetcher = fetcher or _default_fetcher
        self.timeout = timeout
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def request(season: str, season_type: str) -> dict[str, Any]:
        return {
            "season": require_text(season, "season"),
            "season_type": require_text(season_type, "season_type"),
            "league_id": "00",
        }

    @staticmethod
    def source_url(request: dict[str, Any]) -> str:
        query = urlencode(
            {
                "Season": request["season"],
                "SeasonType": request["season_type"],
                "LeagueID": request["league_id"],
            }
        )
        return f"{ENDPOINT}?{query}"

    def normalize(
        self,
        payload: Any,
        *,
        request: dict[str, Any],
        retrieved_at: datetime,
    ) -> list[dict[str, Any]]:
        rows = rows_as_dicts(payload, "PlayerGameLogs")
        source_url = self.source_url(request)
        retrieved_text = utc_text(retrieved_at, "retrieved_at")
        records: list[dict[str, Any]] = []
        identities: set[tuple[str, int]] = set()
        for row in rows:
            season = require_text(row.get("SEASON_YEAR"), "SEASON_YEAR")
            if season != request["season"]:
                raise ValidationError(
                    f"game-log season {season!r} does not match requested {request['season']!r}"
                )
            game_id = require_text(row.get("GAME_ID"), "GAME_ID")
            player_id = require_positive_int(row.get("PLAYER_ID"), "PLAYER_ID")
            team_id = require_positive_int(row.get("TEAM_ID"), "TEAM_ID")
            identity = (game_id, player_id)
            if identity in identities:
                raise ValidationError(f"duplicate player-game identity {identity}")
            identities.add(identity)
            win_loss = row.get("WL")
            if win_loss not in (None, "", "W", "L"):
                raise ValidationError(f"WL must be W, L, or null; got {win_loss!r}")
            record: dict[str, Any] = {
                "season": season,
                "season_type": request["season_type"],
                "game_id": game_id,
                "game_date": require_date(row.get("GAME_DATE"), "GAME_DATE"),
                "player_id": player_id,
                "player_name": require_text(row.get("PLAYER_NAME"), "PLAYER_NAME"),
                "team_id": team_id,
                "team_abbreviation": require_text(
                    row.get("TEAM_ABBREVIATION"), "TEAM_ABBREVIATION"
                ),
                "team_name": require_text(row.get("TEAM_NAME"), "TEAM_NAME"),
                "matchup": require_text(row.get("MATCHUP"), "MATCHUP"),
                "win_loss": win_loss or None,
                "minutes": require_nonnegative_number(row.get("MIN"), "MIN"),
                "source_url": source_url,
                "retrieved_at": retrieved_text,
            }
            for normalized_name, provider_name in _OPTIONAL_STATS.items():
                record[normalized_name] = optional_number(
                    row.get(provider_name), provider_name
                )
            records.append(record)
        records.sort(
            key=lambda record: (
                record["game_date"],
                record["game_id"],
                record["player_id"],
            )
        )
        return records

    def refresh(
        self,
        season: str,
        season_type: str = "Regular Season",
        *,
        max_cache_age: timedelta | None = timedelta(hours=6),
    ) -> PlayerStatsResult:
        request = self.request(season, season_type)
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
                return PlayerStatsResult(
                    records=tuple(document["records"]),
                    snapshot_path=path,
                    from_cache=True,
                )
        try:
            payload = self.fetcher(
                request["season"], request["season_type"], self.timeout
            )
        except PlayerDataError:
            raise
        except Exception as exc:
            raise ProviderError(f"NBA player game-log request failed: {exc}") from exc
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
        return PlayerStatsResult(tuple(records), path, False)
