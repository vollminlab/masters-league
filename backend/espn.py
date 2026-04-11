"""ESPN golf leaderboard client."""

import logging
import os
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

ESPN_URL = os.getenv(
    "ESPN_URL",
    "https://site.api.espn.com/apis/site/v2/sports/golf/leaderboard?league=pga",
)


@dataclass
class ESPNPlayer:
    name: str
    score: Optional[int]      # cumulative to-par (negative = under par)
    score_display: str         # "-12", "E", "+3", "CUT", "WD"
    position: str              # "T1", "2nd", "CUT", etc.
    thru: str                  # "F", "9", "-"
    is_cut: bool
    is_withdrawn: bool
    round_scores: list[Optional[int]] = field(default_factory=list)
    round_scores_display: list[str] = field(default_factory=list)  # "-5", "E", "+2" per round


def normalize_name(name: str) -> str:
    """Lowercase + strip diacritics for fuzzy name matching."""
    nfd = unicodedata.normalize("NFD", name.lower())
    return "".join(c for c in nfd if not unicodedata.combining(c)).strip()


async def fetch_players() -> dict[str, "ESPNPlayer"]:
    """Return dict of normalized_name -> ESPNPlayer for current tournament."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(ESPN_URL)
        resp.raise_for_status()
        data = resp.json()

    players: dict[str, ESPNPlayer] = {}
    events = data.get("events", [])
    if not events:
        logger.warning("ESPN returned no events")
        return players

    # Use the first event (current/most recent tournament)
    event = events[0]
    logger.info("ESPN event: %s", event.get("name", "unknown"))

    competitions = event.get("competitions", [])
    if not competitions:
        return players

    for comp in competitions[0].get("competitors", []):
        player = _parse_competitor(comp)
        if player:
            key = normalize_name(player.name)
            players[key] = player

    logger.info("Parsed %d players from ESPN", len(players))
    return players


def _parse_competitor(comp: dict) -> Optional[ESPNPlayer]:
    try:
        name = comp.get("athlete", {}).get("displayName", "").strip()
        if not name:
            return None

        status = comp.get("status", {})
        stype = status.get("type", {})

        status_name = stype.get("name", "").upper()
        status_desc = stype.get("description", "").lower()
        is_cut = "CUT" in status_name or "cut" in status_desc
        is_wd = "WD" in status_name or "withdraw" in status_desc or "did not" in status_desc

        # Cumulative to-par score — lives in statistics[name=scoreToPar], not status
        score_int: Optional[int] = None
        for stat in comp.get("statistics", []):
            if stat.get("name") == "scoreToPar":
                try:
                    score_int = int(round(float(stat["value"])))
                except (KeyError, ValueError, TypeError):
                    pass
                break

        # Human-readable score
        if is_cut:
            score_display = "CUT"
        elif is_wd:
            score_display = "WD"
        elif score_int is None:
            score_display = "E"
        elif score_int < 0:
            score_display = str(score_int)
        elif score_int > 0:
            score_display = f"+{score_int}"
        else:
            score_display = "E"

        # Position
        if is_cut:
            position = "CUT"
        elif is_wd:
            position = "WD"
        else:
            pos_obj = status.get("position", {})
            position = pos_obj.get("displayName") or pos_obj.get("abbreviation") or "-"

        # Thru (holes completed in current round)
        thru_raw = status.get("thru") or 0
        state = stype.get("state", "")
        if is_cut or is_wd:
            thru = "CUT" if is_cut else "WD"
        elif state == "post" or int(thru_raw) == 18:
            thru = "F"
        elif int(thru_raw) > 0:
            thru = str(int(thru_raw))
        else:
            # ESPN already formats the tee time in status.detail e.g. "2:50 PM ET"
            thru = status.get("detail") or "-"

        # Per-round scores from linescores
        round_scores: list[Optional[int]] = []
        round_scores_display: list[str] = []
        for ls in comp.get("linescores", []):
            dv = ls.get("displayValue", "")
            # Only include rounds that have a real to-par display value
            if dv and (dv == "E" or dv.lstrip("+-").isdigit()):
                try:
                    round_scores.append(int(round(float(ls["value"]))))
                except (KeyError, ValueError, TypeError):
                    round_scores.append(None)
                round_scores_display.append(dv)

        return ESPNPlayer(
            name=name,
            score=score_int,
            score_display=score_display,
            position=position,
            thru=thru,
            is_cut=is_cut,
            is_withdrawn=is_wd,
            round_scores=round_scores,
            round_scores_display=round_scores_display,
        )
    except Exception:
        logger.exception("Failed to parse competitor: %s", comp.get("athlete", {}).get("displayName"))
        return None
