# Hole-by-Hole Scorecard Design
Date: 2026-04-11

## Overview

Click any golfer row on the leaderboard to expand an inline scorecard showing hole-by-hole scores for that player. The scorecard mirrors a real Masters scorecard: front 9 / back 9 split with OUT/IN totals, color-coded hole scores with traditional golf symbols, and round selector tabs.

---

## Backend

### New endpoint

`GET /api/scorecard/{player_id}`

- Calls ESPN linescores: `https://sports.core.api.espn.com/v2/sports/golf/leagues/pga/events/401811941/competitions/401811941/competitors/{player_id}/linescores`
- Redis-cached at 60s TTL, key: `masters:scorecard:{player_id}:v1`
- On ESPN failure: returns HTTP 503 with `{ "error": "Scorecard unavailable" }`

### Response shape

```json
{
  "player_id": "3470",
  "rounds": [
    {
      "round": 1,
      "holes": [
        { "hole": 1, "par": 4, "strokes": 3, "score_type": "BIRDIE" },
        ...
      ],
      "out": 32,
      "in": 31,
      "total": 63
    }
  ],
  "current_round": 2
}
```

`score_type` values from ESPN: `EAGLE`, `BIRDIE`, `PAR`, `BOGEY`, `DOUBLE_BOGEY`, `TRIPLE_BOGEY`, or computed from strokes - par for anything worse.

Holes not yet played: `{ "hole": N, "par": 4, "strokes": null, "score_type": null }`

Rounds not yet started: included in `rounds` array with all null holes so the tab renders (dimmed).

### Leaderboard change

Add `player_id: string` to each golfer object in `GET /api/leaderboard`. This is the ESPN competitor ID already present in the fetch response — just needs to be threaded through `espn.py` → `scoring.py` → `main.py`.

---

## Frontend

### Expand behavior

- Clicking a golfer row toggles an inline scorecard panel directly below that row
- Only one golfer expanded at a time within a team card; clicking a second collapses the first
- Subtle slide-down animation on expand
- Clicking the same golfer again collapses the panel

### Round tabs

- R1 · R2 · R3 · R4 displayed at top of scorecard panel
- Defaults to `current_round` from the API response
- Completed rounds: fully clickable
- Round not started: tab dimmed, non-clickable
- Active tab highlighted

### Scorecard grid layout

Mirrors a real scorecard with three rows:

```
HOLE  | 1  2  3  4  5  6  7  8  9  | OUT | 10 11 12 13 14 15 16 17 18 | IN | TOT
PAR   | 4  5  4  3  4  3  4  5  4  | 36  |  4  3  6  5  4  5  3  4  4 | 38 | 74
SCORE | ◯3 4  ◻5 3  4  3  4  5  3  | 31  |  4  2  6  4  4  5  3  4  4 | 36 | 67
```

- OUT = strokes for holes 1–9
- IN = strokes for holes 10–18
- TOT = OUT + IN (raw stroke total, not to-par)
- Running to-par score displayed prominently above the grid

### Score symbols

| Score type | Symbol | Color |
|---|---|---|
| Eagle | Double circle around number | Gold (#FFD700) |
| Birdie | Single circle around number | Red (#ef4444) |
| Par | Plain number | White/gray |
| Bogey | Single square border around number | Blue (#3b82f6) |
| Double bogey | Double square border | Muted blue (#1d4ed8) |
| Triple bogey | Filled square, number in white | Dark red (#991b1b) |
| Quad bogey+ | Filled square, number in white, darker bg | Darker muted red (#7f1d1d) |
| Unplayed hole | Dash (–) | Gray |

Symbols implemented as CSS border/background on the hole cell — no images.

### Loading & error states

- **Loading:** subtle spinner or skeleton row within the expanded panel
- **ESPN 503 / fetch error:** inline message "Scorecard unavailable" inside the panel — leaderboard unaffected
- **Round not started:** all hole cells show `–`, tabs for future rounds dimmed

---

## Data flow

1. Page loads → leaderboard fetched (now includes `player_id` per golfer)
2. User clicks golfer row → `GET /api/scorecard/{player_id}` fired
3. Panel opens with loading state while fetch is in-flight
4. Response arrives → render scorecard, default to `current_round` tab
5. User clicks round tab → re-render same data, no new fetch needed (all rounds in one response)

---

## Out of scope

- Metrics / analytics
- Scorecard for WD/CUT players (will still be clickable but may return empty rounds — handled gracefully)
- Caching scorecard data client-side across leaderboard refreshes
