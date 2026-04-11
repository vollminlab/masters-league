"""Fantasy scoring logic.

Rules:
- Each team has 5 golfers.
- Counting score = sum of the 3 lowest (best) to-par scores among active players.
- CUT / WD players are excluded from the best-3 calculation.
- A team is Disqualified if fewer than 3 players survived the cut.
- Lower counting score = better.  Ties are ranked equally.
"""

from dataclasses import dataclass, field
from typing import Optional

from draft import DRAFT
from espn import ESPNPlayer, normalize_name


@dataclass
class GolferResult:
    name: str
    score: Optional[int]
    score_display: str
    position: str
    thru: str
    is_cut: bool
    is_withdrawn: bool
    is_counting: bool = False
    round_scores_display: list[str] = field(default_factory=list)


@dataclass
class TeamResult:
    name: str
    golfers: list[GolferResult]
    counting_score: Optional[int]
    counting_score_display: str
    cut_count: int
    active_count: int
    disqualified: bool
    position: Optional[int] = None


def _fmt(score: Optional[int]) -> str:
    if score is None:
        return "E"
    if score < 0:
        return str(score)
    if score > 0:
        return f"+{score}"
    return "E"


def compute_leaderboard(players: dict[str, ESPNPlayer]) -> list[TeamResult]:
    teams = [_compute_team(name, picks, players) for name, picks in DRAFT.items()]

    active = sorted(
        [t for t in teams if not t.disqualified],
        key=lambda t: t.counting_score if t.counting_score is not None else 9999,
    )
    dq = sorted([t for t in teams if t.disqualified], key=lambda t: t.name)

    # Assign positions with tie handling
    for i, team in enumerate(active):
        if i == 0 or active[i - 1].counting_score != team.counting_score:
            team.position = i + 1
        else:
            team.position = active[i - 1].position  # tied

    return active + dq


def _compute_team(
    team_name: str,
    golfer_names: list[str],
    players: dict[str, ESPNPlayer],
) -> TeamResult:
    golfers: list[GolferResult] = []

    for name in golfer_names:
        espn = players.get(normalize_name(name))
        if espn:
            golfers.append(GolferResult(
                name=espn.name,
                score=espn.score,
                score_display=espn.score_display,
                position=espn.position,
                thru=espn.thru,
                is_cut=espn.is_cut,
                is_withdrawn=espn.is_withdrawn,
                round_scores_display=espn.round_scores_display,
            ))
        else:
            # Player not yet in ESPN feed (pre-tournament or name mismatch)
            golfers.append(GolferResult(
                name=name,
                score=None,
                score_display="-",
                position="-",
                thru="-",
                is_cut=False,
                is_withdrawn=False,
            ))

    cut_count = sum(1 for g in golfers if g.is_cut)
    active = [g for g in golfers if not g.is_cut and not g.is_withdrawn]

    if len(active) < 3:
        return TeamResult(
            name=team_name,
            golfers=golfers,
            counting_score=None,
            counting_score_display="DQ",
            cut_count=cut_count,
            active_count=len(active),
            disqualified=True,
        )

    # Best 3 active players by score (treat None/missing as 0)
    sorted_active = sorted(active, key=lambda g: g.score if g.score is not None else 0)
    counting_three = sorted_active[:3]
    counting_keys = {normalize_name(g.name) for g in counting_three}

    for g in golfers:
        g.is_counting = normalize_name(g.name) in counting_keys

    counting_score = sum(g.score for g in counting_three if g.score is not None)

    return TeamResult(
        name=team_name,
        golfers=golfers,
        counting_score=counting_score,
        counting_score_display=_fmt(counting_score),
        cut_count=cut_count,
        active_count=len(active),
        disqualified=False,
    )
