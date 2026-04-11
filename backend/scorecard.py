"""Hole-by-hole scorecard fetcher from ESPN."""

import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

SCORECARD_URL = (
    "https://sports.core.api.espn.com/v2/sports/golf/leagues/pga"
    "/events/401811941/competitions/401811941/competitors/{player_id}/linescores"
)


@dataclass
class HoleScore:
    hole: int
    par: int
    strokes: Optional[int]
    score_type: Optional[str]  # "EAGLE", "BIRDIE", "PAR", "BOGEY", "DOUBLE_BOGEY", "TRIPLE_BOGEY", "WORSE"


@dataclass
class RoundScore:
    round: int
    holes: list[HoleScore]
    out: Optional[int]           # sum of strokes holes 1-9 (None if front 9 incomplete)
    in_: Optional[int]           # sum of strokes holes 10-18 (None if back 9 incomplete)
    total: Optional[int]         # out + in_ (None if either incomplete)
    to_par_display: Optional[str]  # "-5", "E", "+2" — round-level to-par from ESPN
    started: bool


@dataclass
class ScorecardData:
    player_id: str
    rounds: list[RoundScore]
    current_round: int


async def fetch_scorecard(player_id: str) -> ScorecardData:
    """Fetch hole-by-hole data from ESPN for the given player."""
    url = SCORECARD_URL.format(player_id=player_id)
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    return _parse(player_id, resp.json())


def _parse(player_id: str, data: dict) -> ScorecardData:
    """Convert raw ESPN linescores response into ScorecardData."""
    items = data.get("items", [])
    rounds: list[RoundScore] = []
    current_round = 1

    for item in items:
        round_num = item.get("period", 0)
        raw_holes = item.get("linescores", [])
        # A round is started if it has holes OR if ESPN has already given it a to-par displayValue
        started = bool(raw_holes) or bool(item.get("displayValue"))

        if started:
            current_round = round_num

        holes: list[HoleScore] = []
        for h in raw_holes:
            try:
                raw_val = h.get("value")
                strokes = int(raw_val) if raw_val not in (None, "--", "") else None
            except (ValueError, TypeError):
                strokes = None
            score_type = h.get("scoreType", {}).get("name") if h.get("scoreType") else None
            if score_type is None and strokes is not None:
                score_type = _diff_to_type(strokes - h.get("par", 4))
            holes.append(HoleScore(
                hole=h.get("period", 0),
                par=h.get("par", 4),
                strokes=strokes,
                score_type=score_type,
            ))

        strokes_front = [h.strokes for h in holes if h.hole <= 9 and h.strokes is not None]
        strokes_back = [h.strokes for h in holes if h.hole >= 10 and h.strokes is not None]
        out = sum(strokes_front) if len(strokes_front) == 9 else None
        in_ = sum(strokes_back) if len(strokes_back) == 9 else None
        total = (out + in_) if (out is not None and in_ is not None) else None

        rounds.append(RoundScore(
            round=round_num,
            holes=holes,
            out=out,
            in_=in_,
            total=total,
            to_par_display=item.get("displayValue"),
            started=started,
        ))

    # Ensure all 4 rounds are present (unplayed ones as empty stubs)
    present = {r.round for r in rounds}
    for r in range(1, 5):
        if r not in present:
            rounds.append(RoundScore(
                round=r,
                holes=[],
                out=None,
                in_=None,
                total=None,
                to_par_display=None,
                started=False,
            ))
    rounds.sort(key=lambda r: r.round)

    return ScorecardData(player_id=player_id, rounds=rounds, current_round=current_round)


def _diff_to_type(diff: int) -> str:
    if diff <= -3:
        return "ALBATROSS"
    if diff == -2:
        return "EAGLE"
    if diff == -1:
        return "BIRDIE"
    if diff == 0:
        return "PAR"
    if diff == 1:
        return "BOGEY"
    if diff == 2:
        return "DOUBLE_BOGEY"
    if diff == 3:
        return "TRIPLE_BOGEY"
    return "WORSE"
