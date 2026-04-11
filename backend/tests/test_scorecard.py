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


def test_non_numeric_hole_value_does_not_crash():
    """ESPN returns '--' for holes not yet played in a partial round."""
    data = {
        "items": [
            {
                "period": 1,
                "displayValue": "-3",
                "linescores": [
                    {"period": 1, "value": 3.0, "par": 4, "scoreType": {"name": "BIRDIE"}},
                    {"period": 2, "value": "--", "par": 5},   # not yet played
                    {"period": 3, "value": None, "par": 4},   # also not yet played
                ],
            }
        ]
    }
    result = _parse("999", data)
    holes = {h.hole: h for h in result.rounds[0].holes}
    assert holes[1].strokes == 3
    assert holes[2].strokes is None
    assert holes[3].strokes is None
