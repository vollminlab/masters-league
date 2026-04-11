"""Masters League 2026 — FastAPI backend.

Serves:
  GET /api/leaderboard  — computed fantasy leaderboard (Redis-cached, 30s TTL)
  GET /api/health       — liveness probe
  GET /*                — React SPA static files
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from espn import fetch_players
from scoring import compute_leaderboard

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = int(os.getenv("CACHE_TTL", "30"))
STATIC_DIR = Path(__file__).parent / "static"
CACHE_KEY = "masters:leaderboard:v1"

_redis: aioredis.Redis | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _redis
    _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    logger.info("Redis connected: %s", REDIS_URL)
    yield
    await _redis.aclose()


app = FastAPI(title="Masters League 2026", lifespan=lifespan)


# ── API routes ────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/leaderboard")
async def get_leaderboard() -> JSONResponse:
    # Try cache first
    if _redis:
        try:
            cached = await _redis.get(CACHE_KEY)
            if cached:
                return JSONResponse(content=json.loads(cached))
        except Exception as exc:
            logger.warning("Redis read error: %s", exc)

    payload = await _build_payload()

    # Write to cache (best-effort)
    if _redis:
        try:
            await _redis.setex(CACHE_KEY, CACHE_TTL, json.dumps(payload))
        except Exception as exc:
            logger.warning("Redis write error: %s", exc)

    return JSONResponse(content=payload)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _build_payload() -> dict[str, Any]:
    try:
        players = await fetch_players()
    except Exception as exc:
        logger.error("ESPN fetch failed: %s", exc)
        players = {}

    teams = compute_leaderboard(players)

    teams_out = []
    for t in teams:
        teams_out.append({
            "name": t.name,
            "counting_score": t.counting_score,
            "counting_score_display": t.counting_score_display,
            "cut_count": t.cut_count,
            "active_count": t.active_count,
            "disqualified": t.disqualified,
            "position": t.position,
            "golfers": [
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
                for g in t.golfers
            ],
        })

    return {
        "teams": teams_out,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "cache_ttl": CACHE_TTL,
        "player_count": len(players),
    }


# ── SPA catch-all (must be last) ──────────────────────────────────────────────

if STATIC_DIR.exists():
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        target = STATIC_DIR / full_path
        if target.is_file():
            return FileResponse(target)
        return FileResponse(STATIC_DIR / "index.html")
