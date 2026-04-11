# Hole-by-Hole Scorecard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Click any golfer row to expand an inline scorecard showing hole-by-hole scores with traditional golf symbols (circles/squares), round tabs, and a real front-9/back-9 scorecard layout.

**Architecture:** New `/api/scorecard/{player_id}` endpoint fetches ESPN's per-hole linescores on demand and caches at 60s TTL in Redis. The frontend `ScorecardPanel` component manages its own fetch lifecycle and renders inline below the clicked golfer row inside `TeamCard`.

**Tech Stack:** Python/FastAPI/httpx/Redis (backend), React/TypeScript/Tailwind CSS (frontend)

---

## ESPN API Reference

Hole-by-hole endpoint:
```
GET https://sports.core.api.espn.com/v2/sports/golf/leagues/pga/events/401811941/competitions/401811941/competitors/{player_id}/linescores
```

Response shape (confirmed against live data):
```json
{
  "items": [
    {
      "period": 1,
      "value": 67.0,
      "displayValue": "-5",
      "linescores": [
        { "period": 1, "value": 4.0, "par": 4, "scoreType": { "name": "PAR" } },
        { "period": 2, "value": 4.0, "par": 5, "scoreType": { "name": "BIRDIE" } }
      ]
    },
    {
      "period": 3,
      "teeTime": "2026-04-11T18:50Z"
    }
  ]
}
```

`period` at the item level = round number (1-4).
`period` inside `linescores` = hole number (1-18).
Rounds not yet started have no `linescores` key.
Player ID = `comp["id"]` from leaderboard competitors array (e.g. Rory = `"3470"`).

---

## File Map

| File | Change |
|---|---|
| `backend/espn.py` | Add `player_id: str` to `ESPNPlayer`; capture from `comp.get("id", "")` |
| `backend/scoring.py` | Add `player_id: str = ""` to `GolferResult`; thread through `_compute_team` |
| `backend/scorecard.py` | **NEW** — fetch + parse ESPN hole-by-hole data |
| `backend/main.py` | Add `player_id` to leaderboard serialization; add `/api/scorecard/{player_id}` endpoint |
| `backend/tests/test_scorecard.py` | **NEW** — unit tests for `_parse` logic |
| `frontend/src/types.ts` | Add `player_id` to `GolferResult`; add `HoleData`, `RoundData`, `ScorecardData` |
| `frontend/src/components/ScorecardPanel.tsx` | **NEW** — inline scorecard panel |
| `frontend/src/components/TeamCard.tsx` | Add expand state; render `ScorecardPanel` inline |

---

## Task 1: Thread player_id through the backend data pipeline

**Files:**
- Modify: `backend/espn.py`
- Modify: `backend/scoring.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Add `player_id` to `ESPNPlayer` in `espn.py`**

In `backend/espn.py`, add the field to the dataclass and capture it in `_parse_competitor`:

```python
# In ESPNPlayer dataclass — add after is_withdrawn field:
player_id: str = ""
```

In `_parse_competitor`, capture it right after extracting the name:

```python
def _parse_competitor(comp: dict) -> Optional[ESPNPlayer]:
    try:
        name = comp.get("athlete", {}).get("displayName", "").strip()
        if not name:
            return None

        player_id = str(comp.get("id", ""))
        # ... rest of existing code unchanged ...
```

And pass it to the `ESPNPlayer` constructor at the bottom of `_parse_competitor`:

```python
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
            player_id=player_id,
        )
```

- [ ] **Step 2: Add `player_id` to `GolferResult` in `scoring.py`**

```python
# In GolferResult dataclass — add after is_withdrawn field:
player_id: str = ""
```

In `_compute_team`, pass it through from `espn`:

```python
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
                player_id=espn.player_id,
            ))
```

- [ ] **Step 3: Serialize `player_id` in `main.py`**

In `_build_payload`, inside the golfer dict comprehension, add:

```python
                {
                    "name": g.name,
                    "score": g.score,
                    "score_display": g.score_display,
                    "position": g.position,
                    "thru": g.thru,
                    "is_cut": g.is_cut,
                    "is_withdrawn": g.is_withdrawn,
                    "is_counting": g.is_counting,
                    "round_scores_display": g.round_scores_display,
                    "player_id": g.player_id,
                }
```

- [ ] **Step 4: Verify manually**

Restart the backend and hit the leaderboard:

```bash
cd backend && uvicorn main:app --reload --port 8000
curl -s http://localhost:8000/api/leaderboard | python3 -m json.tool | grep player_id | head -5
```

Expected: lines like `"player_id": "3470"` for each golfer (some may be `""` if ESPN name matching hasn't fired yet — that's fine).

- [ ] **Step 5: Commit**

```bash
git add backend/espn.py backend/scoring.py backend/main.py
git commit -m "feat: thread ESPN player_id through leaderboard pipeline"
```

---

## Task 2: Backend scorecard module

**Files:**
- Create: `backend/scorecard.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_scorecard.py`

- [ ] **Step 1: Write failing tests for `_parse`**

Create `backend/tests/__init__.py` (empty):

```python
```

Create `backend/tests/test_scorecard.py`:

```python
"""Tests for scorecard._parse — covers the ESPN response → ScorecardData conversion."""
import pytest
from scorecard import ScorecardData, RoundScore, HoleScore, _parse


ESPN_TWO_ROUNDS = {
    "items": [
        {
            "period": 1,
            "value": 67.0,
            "displayValue": "-5",
            "linescores": [
                {"period": 1, "value": 4.0, "par": 4, "scoreType": {"name": "PAR"}},
                {"period": 2, "value": 4.0, "par": 5, "scoreType": {"name": "BIRDIE"}},
                {"period": 3, "value": 3.0, "par": 4, "scoreType": {"name": "BIRDIE"}},
                {"period": 4, "value": 2.0, "par": 3, "scoreType": {"name": "BIRDIE"}},
                {"period": 5, "value": 4.0, "par": 4, "scoreType": {"name": "PAR"}},
                {"period": 6, "value": 3.0, "par": 3, "scoreType": {"name": "PAR"}},
                {"period": 7, "value": 5.0, "par": 4, "scoreType": {"name": "BOGEY"}},
                {"period": 8, "value": 5.0, "par": 5, "scoreType": {"name": "PAR"}},
                {"period": 9, "value": 4.0, "par": 4, "scoreType": {"name": "PAR"}},
                {"period": 10, "value": 4.0, "par": 4, "scoreType": {"name": "PAR"}},
                {"period": 11, "value": 3.0, "par": 3, "scoreType": {"name": "PAR"}},
                {"period": 12, "value": 3.0, "par": 3, "scoreType": {"name": "PAR"}},
                {"period": 13, "value": 4.0, "par": 5, "scoreType": {"name": "BIRDIE"}},
                {"period": 14, "value": 4.0, "par": 4, "scoreType": {"name": "PAR"}},
                {"period": 15, "value": 4.0, "par": 5, "scoreType": {"name": "BIRDIE"}},
                {"period": 16, "value": 3.0, "par": 3, "scoreType": {"name": "PAR"}},
                {"period": 17, "value": 4.0, "par": 4, "scoreType": {"name": "PAR"}},
                {"period": 18, "value": 4.0, "par": 4, "scoreType": {"name": "PAR"}},
            ],
        },
        {
            "period": 2,
            "value": 65.0,
            "displayValue": "-7",
            "linescores": [
                {"period": 1, "value": 4.0, "par": 4, "scoreType": {"name": "PAR"}},
                {"period": 2, "value": 3.0, "par": 5, "scoreType": {"name": "BIRDIE"}},
                {"period": 3, "value": 4.0, "par": 4, "scoreType": {"name": "PAR"}},
                {"period": 4, "value": 2.0, "par": 3, "scoreType": {"name": "BIRDIE"}},
                {"period": 5, "value": 4.0, "par": 4, "scoreType": {"name": "PAR"}},
                {"period": 6, "value": 2.0, "par": 3, "scoreType": {"name": "BIRDIE"}},
                {"period": 7, "value": 4.0, "par": 4, "scoreType": {"name": "PAR"}},
                {"period": 8, "value": 5.0, "par": 5, "scoreType": {"name": "PAR"}},
                {"period": 9, "value": 4.0, "par": 4, "scoreType": {"name": "PAR"}},
                {"period": 10, "value": 4.0, "par": 4, "scoreType": {"name": "PAR"}},
                {"period": 11, "value": 3.0, "par": 3, "scoreType": {"name": "PAR"}},
                {"period": 12, "value": 3.0, "par": 3, "scoreType": {"name": "PAR"}},
                {"period": 13, "value": 4.0, "par": 5, "scoreType": {"name": "BIRDIE"}},
                {"period": 14, "value": 4.0, "par": 4, "scoreType": {"name": "PAR"}},
                {"period": 15, "value": 3.0, "par": 5, "scoreType": {"name": "EAGLE"}},
                {"period": 16, "value": 3.0, "par": 3, "scoreType": {"name": "PAR"}},
                {"period": 17, "value": 4.0, "par": 4, "scoreType": {"name": "PAR"}},
                {"period": 18, "value": 4.0, "par": 4, "scoreType": {"name": "PAR"}},
            ],
        },
        {"period": 3, "teeTime": "2026-04-11T18:50Z"},
    ]
}


def test_current_round_is_latest_with_linescores():
    result = _parse("3470", ESPN_TWO_ROUNDS)
    assert result.current_round == 2


def test_all_four_rounds_present():
    result = _parse("3470", ESPN_TWO_ROUNDS)
    assert len(result.rounds) == 4
    assert [r.round for r in result.rounds] == [1, 2, 3, 4]


def test_unstarted_rounds_have_started_false():
    result = _parse("3470", ESPN_TWO_ROUNDS)
    r3 = next(r for r in result.rounds if r.round == 3)
    r4 = next(r for r in result.rounds if r.round == 4)
    assert r3.started is False
    assert r4.started is False
    assert r3.holes == []
    assert r4.holes == []


def test_completed_round_out_in_total():
    result = _parse("3470", ESPN_TWO_ROUNDS)
    r1 = result.rounds[0]
    assert r1.out == 34   # holes 1-9: 4+4+3+2+4+3+5+5+4
    assert r1.in_ == 33   # holes 10-18: 4+3+3+4+4+4+3+4+4
    assert r1.total == 67


def test_hole_score_type_preserved():
    result = _parse("3470", ESPN_TWO_ROUNDS)
    r2 = result.rounds[1]
    hole15 = next(h for h in r2.holes if h.hole == 15)
    assert hole15.score_type == "EAGLE"
    assert hole15.strokes == 3
    assert hole15.par == 5


def test_score_type_computed_when_missing():
    """If scoreType is absent from ESPN data, compute from strokes - par."""
    data = {
        "items": [
            {
                "period": 1,
                "value": 70.0,
                "displayValue": "-2",
                "linescores": [
                    {"period": 1, "value": 3.0, "par": 4},   # no scoreType — BIRDIE
                    {"period": 2, "value": 6.0, "par": 4},   # no scoreType — DOUBLE_BOGEY
                ],
            }
        ]
    }
    result = _parse("999", data)
    holes = {h.hole: h for h in result.rounds[0].holes}
    assert holes[1].score_type == "BIRDIE"
    assert holes[2].score_type == "DOUBLE_BOGEY"
```

- [ ] **Step 2: Run tests to verify they fail (module not yet created)**

```bash
cd backend && pip install pytest --quiet && python -m pytest tests/test_scorecard.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'scorecard'`

- [ ] **Step 3: Create `backend/scorecard.py`**

```python
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
        started = bool(raw_holes)

        if started:
            current_round = round_num

        holes: list[HoleScore] = []
        for h in raw_holes:
            strokes = int(h["value"]) if h.get("value") is not None else None
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_scorecard.py -v
```

Expected output:
```
PASSED tests/test_scorecard.py::test_current_round_is_latest_with_linescores
PASSED tests/test_scorecard.py::test_all_four_rounds_present
PASSED tests/test_scorecard.py::test_unstarted_rounds_have_started_false
PASSED tests/test_scorecard.py::test_completed_round_out_in_total
PASSED tests/test_scorecard.py::test_hole_score_type_preserved
PASSED tests/test_scorecard.py::test_score_type_computed_when_missing
6 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/scorecard.py backend/tests/__init__.py backend/tests/test_scorecard.py
git commit -m "feat: add scorecard ESPN parser with unit tests"
```

---

## Task 3: Scorecard API endpoint

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add import and endpoint to `main.py`**

Add import at the top with the other imports:

```python
from scorecard import fetch_scorecard, ScorecardData
```

Add the endpoint after `get_leaderboard`, before the `_build_payload` helper:

```python
@app.get("/api/scorecard/{player_id}")
async def get_scorecard(player_id: str) -> JSONResponse:
    cache_key = f"masters:scorecard:{player_id}:v1"

    if _redis:
        try:
            cached = await _redis.get(cache_key)
            if cached:
                return JSONResponse(content=json.loads(cached))
        except Exception as exc:
            logger.warning("Redis read error: %s", exc)

    try:
        data = await fetch_scorecard(player_id)
    except Exception as exc:
        logger.error("Scorecard fetch failed for %s: %s", player_id, exc)
        return JSONResponse(status_code=503, content={"error": "Scorecard unavailable"})

    payload = _serialize_scorecard(data)

    if _redis:
        try:
            await _redis.setex(cache_key, 60, json.dumps(payload))
        except Exception as exc:
            logger.warning("Redis write error: %s", exc)

    return JSONResponse(content=payload)


def _serialize_scorecard(data: ScorecardData) -> dict:
    return {
        "player_id": data.player_id,
        "current_round": data.current_round,
        "rounds": [
            {
                "round": r.round,
                "started": r.started,
                "to_par_display": r.to_par_display,
                "out": r.out,
                "in": r.in_,
                "total": r.total,
                "holes": [
                    {
                        "hole": h.hole,
                        "par": h.par,
                        "strokes": h.strokes,
                        "score_type": h.score_type,
                    }
                    for h in r.holes
                ],
            }
            for r in data.rounds
        ],
    }
```

- [ ] **Step 2: Test the endpoint manually**

```bash
cd backend && uvicorn main:app --reload --port 8000
# In a second terminal:
curl -s http://localhost:8000/api/scorecard/3470 | python3 -m json.tool | head -40
```

Expected: JSON with `player_id`, `current_round`, and 4 `rounds` entries. First two rounds should have 18 holes each. Last two should have `"started": false` and empty `"holes": []`.

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: add /api/scorecard/{player_id} endpoint with Redis cache"
```

---

## Task 4: Frontend types

**Files:**
- Modify: `frontend/src/types.ts`

- [ ] **Step 1: Update `types.ts`**

Replace the entire file with:

```typescript
export interface GolferResult {
  name: string
  player_id: string             // ESPN competitor ID — empty string if unknown
  score: number | null
  score_display: string         // "-12", "E", "+3", "CUT", "WD", "-"
  position: string              // "T1", "2nd", "CUT", "-"
  thru: string                  // "F", "9", "-", "1:30 PM"
  is_cut: boolean
  is_withdrawn: boolean
  is_counting: boolean          // one of the best 3 active players
  round_scores_display: string[] // ["−5", "−7", "+1"] per completed round
}

export interface TeamResult {
  name: string
  golfers: GolferResult[]
  counting_score: number | null
  counting_score_display: string // "-17", "E", "+7", "DQ"
  cut_count: number
  active_count: number
  disqualified: boolean
  position: number | null
}

export interface LeaderboardData {
  teams: TeamResult[]
  last_updated: string   // ISO timestamp
  cache_ttl: number
  player_count: number
}

// ── Scorecard types ───────────────────────────────────────────────────────────

export interface HoleData {
  hole: number
  par: number
  strokes: number | null
  score_type: string | null  // "EAGLE", "BIRDIE", "PAR", "BOGEY", "DOUBLE_BOGEY",
                              // "TRIPLE_BOGEY", "ALBATROSS", "WORSE"
}

export interface RoundData {
  round: number
  started: boolean
  to_par_display: string | null  // "-5", "E", "+2"
  out: number | null             // strokes holes 1-9 (null if front 9 not complete)
  in: number | null              // strokes holes 10-18
  total: number | null
  holes: HoleData[]
}

export interface ScorecardData {
  player_id: string
  current_round: number
  rounds: RoundData[]
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1
```

Expected: no errors (or only pre-existing errors unrelated to these types).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types.ts
git commit -m "feat: add player_id to GolferResult and scorecard types"
```

---

## Task 5: ScorecardPanel component

**Files:**
- Create: `frontend/src/components/ScorecardPanel.tsx`

- [ ] **Step 1: Create `ScorecardPanel.tsx`**

```tsx
import { useState, useEffect } from 'react'
import type { ScorecardData, HoleData } from '../types'

const HOLES_FRONT = [1, 2, 3, 4, 5, 6, 7, 8, 9]
const HOLES_BACK = [10, 11, 12, 13, 14, 15, 16, 17, 18]

// Background color that matches the card body — used for double-ring shadow gap
const CARD_BG = '#111827'

// ── Symbol styles ─────────────────────────────────────────────────────────────

type SymbolStyle = { ring: string; text: string; bg?: string }

const SCORE_STYLES: Record<string, SymbolStyle> = {
  ALBATROSS: {
    // Triple circle — gold, use double ring + inner border
    ring: `border-2 border-yellow-300 rounded-full shadow-[0_0_0_2px_${CARD_BG},0_0_0_4px_#fde047,0_0_0_6px_${CARD_BG},0_0_0_8px_#fde047]`,
    text: 'text-yellow-200',
  },
  EAGLE: {
    ring: `border-2 border-yellow-400 rounded-full shadow-[0_0_0_2px_${CARD_BG},0_0_0_4px_#fbbf24]`,
    text: 'text-yellow-300',
  },
  BIRDIE: {
    ring: 'border-2 border-red-500 rounded-full',
    text: 'text-red-400',
  },
  PAR: {
    ring: '',
    text: 'text-gray-400',
  },
  BOGEY: {
    ring: 'border-2 border-blue-500',
    text: 'text-blue-400',
  },
  DOUBLE_BOGEY: {
    ring: `border-2 border-blue-700 shadow-[0_0_0_2px_${CARD_BG},0_0_0_4px_#1d4ed8]`,
    text: 'text-blue-300',
  },
  TRIPLE_BOGEY: {
    ring: 'bg-red-900',
    text: 'text-white',
  },
  WORSE: {
    ring: 'bg-red-950',
    text: 'text-white',
  },
}

function getStyle(scoreType: string | null): SymbolStyle {
  if (!scoreType) return SCORE_STYLES.PAR
  return SCORE_STYLES[scoreType] ?? SCORE_STYLES.WORSE
}

// ── Individual hole cell ──────────────────────────────────────────────────────

function HoleCell({ hole }: { hole: HoleData | null }) {
  const baseCell = 'w-7 h-7 flex items-center justify-center text-xs font-mono tabular shrink-0'

  if (!hole || hole.strokes === null) {
    return (
      <div className={`${baseCell} text-gray-700`}>–</div>
    )
  }

  const style = getStyle(hole.score_type)
  return (
    <div className={`${baseCell} ${style.ring} ${style.text}`}>
      {hole.strokes}
    </div>
  )
}

// ── Scorecard grid ────────────────────────────────────────────────────────────

function ScorecardGrid({ round }: { round: import('../types').RoundData }) {
  const holeMap = new Map(round.holes.map(h => [h.hole, h]))

  // Compute partial front/back sums (show even if not all 9 holes played)
  const frontPlayed = HOLES_FRONT.map(n => holeMap.get(n)).filter(Boolean) as HoleData[]
  const backPlayed = HOLES_BACK.map(n => holeMap.get(n)).filter(Boolean) as HoleData[]

  const outStrokes = frontPlayed.reduce((s, h) => s + (h.strokes ?? 0), 0)
  const inStrokes = backPlayed.reduce((s, h) => s + (h.strokes ?? 0), 0)
  const totalStrokes = outStrokes + inStrokes

  const outPar = frontPlayed.reduce((s, h) => s + h.par, 0)
  const inPar = backPlayed.reduce((s, h) => s + h.par, 0)

  const showOut = frontPlayed.length > 0
  const showIn = backPlayed.length > 0

  const cellBase = 'w-7 shrink-0 text-center text-xs tabular'
  const totalCell = 'w-9 shrink-0 text-center text-xs tabular font-semibold'

  return (
    <div className="overflow-x-auto">
      <div className="min-w-max px-4 py-2 space-y-1">

        {/* HOLE row */}
        <div className="flex items-center gap-1 text-gray-600 text-xs uppercase">
          <div className="w-10 shrink-0 text-gray-700 font-semibold">HOLE</div>
          {HOLES_FRONT.map(n => (
            <div key={n} className={cellBase}>{n}</div>
          ))}
          <div className={`${totalCell} text-gray-600`}>OUT</div>
          {HOLES_BACK.map(n => (
            <div key={n} className={cellBase}>{n}</div>
          ))}
          <div className={`${totalCell} text-gray-600`}>IN</div>
          <div className={`${totalCell} text-gray-500`}>TOT</div>
        </div>

        {/* PAR row */}
        <div className="flex items-center gap-1 text-gray-600 text-xs">
          <div className="w-10 shrink-0 text-gray-700 font-semibold text-xs">PAR</div>
          {HOLES_FRONT.map(n => {
            const h = holeMap.get(n)
            return (
              <div key={n} className={cellBase}>{h ? h.par : '·'}</div>
            )
          })}
          <div className={`${totalCell} text-gray-600`}>{showOut ? outPar : '–'}</div>
          {HOLES_BACK.map(n => {
            const h = holeMap.get(n)
            return (
              <div key={n} className={cellBase}>{h ? h.par : '·'}</div>
            )
          })}
          <div className={`${totalCell} text-gray-600`}>{showIn ? inPar : '–'}</div>
          <div className={`${totalCell} text-gray-500`}>{showOut && showIn ? outPar + inPar : '–'}</div>
        </div>

        {/* SCORE row */}
        <div className="flex items-center gap-1">
          <div className="w-10 shrink-0 text-gray-700 font-semibold text-xs">SCORE</div>
          {HOLES_FRONT.map(n => (
            <HoleCell key={n} hole={holeMap.get(n) ?? null} />
          ))}
          <div className={`${totalCell} ${showOut ? 'text-white' : 'text-gray-700'}`}>
            {showOut ? outStrokes : '–'}
          </div>
          {HOLES_BACK.map(n => (
            <HoleCell key={n} hole={holeMap.get(n) ?? null} />
          ))}
          <div className={`${totalCell} ${showIn ? 'text-white' : 'text-gray-700'}`}>
            {showIn ? inStrokes : '–'}
          </div>
          <div className={`${totalCell} ${(showOut || showIn) ? 'text-white font-bold' : 'text-gray-700'}`}>
            {(showOut || showIn) ? totalStrokes : '–'}
          </div>
        </div>

      </div>
    </div>
  )
}

// ── Main panel ────────────────────────────────────────────────────────────────

export default function ScorecardPanel({ playerId }: { playerId: string }) {
  const [data, setData] = useState<ScorecardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeRound, setActiveRound] = useState<number>(1)

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetch(`/api/scorecard/${playerId}`)
      .then(r => r.ok ? r.json() : Promise.reject(`Error ${r.status}`))
      .then((d: ScorecardData) => {
        setData(d)
        setActiveRound(d.current_round)
        setLoading(false)
      })
      .catch((e: unknown) => {
        setError(typeof e === 'string' ? e : 'Scorecard unavailable')
        setLoading(false)
      })
  }, [playerId])

  const currentRound = data?.rounds.find(r => r.round === activeRound)

  return (
    <div className="border-t border-gray-800/60" style={{ background: '#0d1520' }}>

      {/* Round tabs */}
      <div className="flex gap-1 px-4 pt-3 pb-1">
        {[1, 2, 3, 4].map(n => {
          const round = data?.rounds.find(r => r.round === n)
          const started = round?.started ?? false
          const isActive = n === activeRound

          return (
            <button
              key={n}
              onClick={() => started && setActiveRound(n)}
              className={`
                px-3 py-1 rounded text-xs font-semibold transition-colors
                ${isActive
                  ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/40'
                  : started
                  ? 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50 border border-transparent'
                  : 'text-gray-700 border border-transparent cursor-default'
                }
              `}
              disabled={!started}
            >
              R{n}
              {started && round?.to_par_display && (
                <span className={`ml-1 ${
                  round.to_par_display.startsWith('-') ? 'text-green-500' :
                  round.to_par_display.startsWith('+') ? 'text-red-500' : 'text-gray-500'
                }`}>
                  {round.to_par_display}
                </span>
              )}
            </button>
          )
        })}

        {/* Running to-par for active round */}
        {data && currentRound?.to_par_display && (
          <div className={`ml-auto text-sm font-bold font-mono tabular self-center ${
            currentRound.to_par_display.startsWith('-') ? 'text-green-400' :
            currentRound.to_par_display.startsWith('+') ? 'text-red-400' : 'text-white'
          }`}>
            {currentRound.to_par_display}
          </div>
        )}
      </div>

      {/* Content */}
      {loading && (
        <div className="px-4 py-4 text-gray-600 text-xs animate-pulse">Loading scorecard…</div>
      )}

      {error && (
        <div className="px-4 py-3 text-red-600 text-xs">{error}</div>
      )}

      {!loading && !error && currentRound && (
        currentRound.started
          ? <ScorecardGrid round={currentRound} />
          : <div className="px-4 py-4 text-gray-700 text-xs">Round not yet started</div>
      )}

      <div className="h-2" />
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1
```

Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ScorecardPanel.tsx
git commit -m "feat: add ScorecardPanel component with hole symbols and round tabs"
```

---

## Task 6: Wire expand state into TeamCard

**Files:**
- Modify: `frontend/src/components/TeamCard.tsx`

- [ ] **Step 1: Update `TeamCard.tsx`**

Replace the entire file:

```tsx
import { useState } from 'react'
import type { GolferResult, TeamResult } from '../types'
import ScorecardPanel from './ScorecardPanel'

const TOTAL_ROUNDS = 4

// ── Score formatting ──────────────────────────────────────────────────────────

function scoreColor(display: string): string {
  if (display.startsWith('-')) return 'text-green-400'
  if (display.startsWith('+')) return 'text-red-400'
  if (display === 'E') return 'text-white'
  return 'text-gray-500'
}

function roundScoreColor(display: string): string {
  if (display.startsWith('-')) return 'text-green-500'
  if (display.startsWith('+')) return 'text-red-500'
  if (display === 'E') return 'text-gray-300'
  return 'text-gray-600'
}

function rankColor(pos: number | null, dq: boolean): string {
  if (dq) return 'text-gray-700'
  if (pos === 1) return 'text-yellow-400'
  if (pos === 2) return 'text-gray-300'
  if (pos === 3) return 'text-amber-600'
  return 'text-gray-500'
}

// ── Team card ─────────────────────────────────────────────────────────────────

export default function TeamCard({ team, isTied = false }: { team: TeamResult; isTied?: boolean }) {
  const { counting_score_display: scoreDisplay, disqualified, position } = team
  const isLeader = position === 1 && !disqualified
  const [expandedGolfer, setExpandedGolfer] = useState<string | null>(null)

  const posDisplay = disqualified
    ? 'DQ'
    : isTied && position
    ? `T${position}`
    : (position ?? '–')

  function toggleGolfer(name: string) {
    setExpandedGolfer(prev => prev === name ? null : name)
  }

  return (
    <div
      className={`rounded-xl overflow-hidden border transition-all ${
        isLeader
          ? 'border-yellow-500/60 shadow-[0_0_24px_rgba(234,179,8,0.12)]'
          : disqualified
          ? 'border-gray-800/60'
          : 'border-gray-700/80'
      }`}
      style={{ background: '#111827' }}
    >
      {/* ── Card header ── */}
      <div
        className="px-4 py-3 flex items-center justify-between"
        style={{
          background: isLeader ? '#1e2c1a' : disqualified ? '#1a1f2e' : '#1e2538',
        }}
      >
        {/* Rank + name */}
        <div className="flex items-center gap-3 min-w-0">
          <span
            className={`text-2xl font-bold tabular w-10 shrink-0 text-center ${rankColor(position, disqualified)}`}
          >
            {posDisplay}
          </span>

          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2
                className={`font-bold text-base leading-tight ${
                  disqualified ? 'text-gray-500' : 'text-white'
                }`}
              >
                {team.name}
              </h2>
              {disqualified && (
                <span className="text-xs bg-red-950 text-red-500 border border-red-900 px-1.5 py-0.5 rounded font-semibold">
                  DISQUALIFIED
                </span>
              )}
            </div>
            <p className="text-xs text-gray-600 mt-0.5">
              {team.active_count} active
              {team.cut_count > 0 && (
                <span className="text-red-600 ml-1.5">· {team.cut_count} cut</span>
              )}
            </p>
          </div>
        </div>

        {/* Counting score */}
        <div className="text-right shrink-0 ml-3">
          <div className={`text-3xl font-bold font-mono tabular ${scoreColor(scoreDisplay)}`}>
            {scoreDisplay}
          </div>
          <div className="text-xs text-gray-700 mt-0.5">best 3</div>
        </div>
      </div>

      {/* ── Column headers ── */}
      <div className="px-4 pt-2 pb-1 flex items-center text-xs text-gray-600 uppercase tracking-wider select-none gap-1">
        <div className="w-4 shrink-0" />
        <div className="flex-1 min-w-0">Golfer</div>
        {Array.from({ length: TOTAL_ROUNDS }, (_, i) => (
          <div key={i} className="hidden sm:block w-7 text-right shrink-0">
            R{i + 1}
          </div>
        ))}
        <div className="w-10 text-right shrink-0">Score</div>
        <div className="w-8 text-right shrink-0">Pos</div>
        <div className="w-16 text-right shrink-0">Thru</div>
      </div>

      {/* ── Golfer rows ── */}
      <div className="divide-y divide-gray-800/40 pb-1">
        {team.golfers.map(g => (
          <div key={g.name}>
            <GolferRow
              golfer={g}
              isExpanded={expandedGolfer === g.name}
              onToggle={() => toggleGolfer(g.name)}
            />
            {expandedGolfer === g.name && g.player_id && (
              <ScorecardPanel playerId={g.player_id} />
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Golfer row ────────────────────────────────────────────────────────────────

function GolferRow({
  golfer,
  isExpanded,
  onToggle,
}: {
  golfer: GolferResult
  isExpanded: boolean
  onToggle: () => void
}) {
  const inactive = golfer.is_cut || golfer.is_withdrawn
  const rounds = golfer.round_scores_display ?? []
  const paddedRounds = [...rounds, ...Array(Math.max(0, TOTAL_ROUNDS - rounds.length)).fill('')]
  const clickable = Boolean(golfer.player_id) && !inactive

  return (
    <div
      onClick={clickable ? onToggle : undefined}
      className={`px-4 py-2 flex items-center text-sm gap-1 transition-opacity ${
        inactive ? 'opacity-35' : ''
      } ${clickable ? 'cursor-pointer hover:bg-white/[0.03]' : ''} ${
        isExpanded ? 'bg-white/[0.04]' : ''
      }`}
    >
      {/* Counting dot / status icon */}
      <div className="w-4 shrink-0 flex items-center justify-center">
        {golfer.is_counting && !inactive && (
          <div
            className="w-2 h-2 rounded-full shrink-0"
            style={{ background: '#FFD700' }}
            title="Counting toward team score"
          />
        )}
        {golfer.is_cut && (
          <span className="text-red-700 text-xs leading-none">✗</span>
        )}
        {golfer.is_withdrawn && (
          <span className="text-gray-700 text-xs leading-none">–</span>
        )}
      </div>

      {/* Name */}
      <div
        className={`flex-1 min-w-0 font-medium truncate ${
          inactive
            ? 'text-gray-600 line-through decoration-gray-700'
            : golfer.is_counting
            ? 'text-white'
            : 'text-gray-400'
        }`}
      >
        {golfer.name}
        {clickable && (
          <span className={`ml-1 text-gray-700 text-xs transition-transform inline-block ${isExpanded ? 'rotate-180' : ''}`}>
            ▾
          </span>
        )}
      </div>

      {/* Round scores */}
      {paddedRounds.map((r, i) => (
        <div
          key={i}
          className={`hidden sm:block w-7 text-right font-mono text-xs tabular shrink-0 ${
            r ? roundScoreColor(r) : 'text-gray-800'
          }`}
        >
          {r || '·'}
        </div>
      ))}

      {/* Total score */}
      <div className={`w-10 text-right font-mono font-semibold tabular shrink-0 ${scoreColor(golfer.score_display)}`}>
        {golfer.score_display}
      </div>

      {/* Position */}
      <div className="w-8 text-right text-gray-600 text-xs tabular shrink-0">
        {golfer.position}
      </div>

      {/* Thru */}
      <div
        className={`w-16 text-right text-xs tabular shrink-0 ${
          golfer.thru === 'F' ? 'text-green-700' : 'text-gray-600'
        }`}
      >
        {golfer.thru}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1
```

Expected: no errors.

- [ ] **Step 3: Build and check for Vite errors**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: successful build, no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/TeamCard.tsx
git commit -m "feat: expand golfer row inline to show hole-by-hole scorecard"
```

---

## Task 7: Container image and deploy

**Files:**
- `backend/requirements.txt` (no change needed — httpx already present)
- Harbor registry + k8s GitOps

- [ ] **Step 1: Build and push container image**

```bash
cd /home/vollmin/repos/vollminlab/masters-league
docker build -t harbor.vollminlab.com/homelab/masters-league:v1.1.0 .
docker push harbor.vollminlab.com/homelab/masters-league:v1.1.0
```

- [ ] **Step 2: Update image tag in k8s deployment**

In `k8s-vollminlab-cluster/clusters/vollminlab-cluster/dmz/masters-league/app/deployment.yaml`, change:

```yaml
image: harbor.vollminlab.com/homelab/masters-league:v1.0.0
```

to:

```yaml
image: harbor.vollminlab.com/homelab/masters-league:v1.1.0
```

- [ ] **Step 3: Commit and push k8s change**

```bash
cd /home/vollmin/repos/vollminlab/k8s-vollminlab-cluster
git add clusters/vollminlab-cluster/dmz/masters-league/app/deployment.yaml
git commit -m "chore: bump masters-league to v1.1.0 (scorecard feature)"
git push
```

Flux will pick up the change and roll out the new image within ~1 minute.

- [ ] **Step 4: Verify rollout**

```bash
kubectl rollout status deployment/masters-league -n dmz
kubectl logs -n dmz deployment/masters-league --tail=20
```

Expected: `deployment "masters-league" successfully rolled out`, logs show Redis connected and no errors.

---

## Self-review notes

- `_diff_to_type` handles `diff <= -3` as ALBATROSS — covers holes-in-one on par-4s. Style defined in `SCORE_STYLES`.
- `player_id` is `""` (empty string) for players not matched in ESPN feed. `GolferRow` checks `Boolean(golfer.player_id)` before making the row clickable — graceful fallback.
- CUT/WD players: row is non-clickable (`!inactive` guard) even if `player_id` is present. Their scorecard data would be incomplete anyway.
- Redis cache TTL for scorecards is 60s (vs 30s for leaderboard) — hole data changes less frequently during a round.
- OUT/IN/TOT in the grid are always computed client-side from the holeMap so partial rounds show partial sums (e.g. if a player is through hole 12, OUT shows the completed front 9 total, IN shows holes 10-12 sum).
