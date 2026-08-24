"""Deterministic, transparent compliance scoring.

This module is the ONLY place scores are computed. The API serves these
numbers to the frontend; the frontend never recalculates them.
"""

VERDICT_SCORES: dict[str, float] = {
    "PASS": 100.0,
    "REVIEW": 60.0,
    "FAIL": 0.0,
    "MISSING": 0.0,
}

VERDICTS = ("PASS", "REVIEW", "FAIL", "MISSING")

RISK_BANDS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def score_for_verdict(verdict: str) -> float:
    """Score contributed by a single requirement verdict."""
    return VERDICT_SCORES[verdict]


def compute_summary(outcomes: list) -> dict:
    """Aggregate per-requirement outcomes into the overall compliance picture.

    `outcomes` is any list of objects exposing `.verdict`, `.score` and
    `.obligation` — both EvaluationOutcome dataclasses and ORM rows work.

    Overall score = sum(requirement scores) / number of requirements.
    """
    total = len(outcomes)
    counts = {v: 0 for v in VERDICTS}
    for o in outcomes:
        counts[o.verdict] = counts.get(o.verdict, 0) + 1

    if total == 0:
        overall = 0.0
    else:
        overall = sum(o.score for o in outcomes) / total

    # A bid is non-responsive if any MANDATORY requirement is FAIL or MISSING.
    blocking = [
        o
        for o in outcomes
        if getattr(o, "obligation", "MANDATORY") == "MANDATORY"
        and o.verdict in ("FAIL", "MISSING")
    ]
    gate_status = "NON_RESPONSIVE" if blocking else "RESPONSIVE"

    risk_score = min(
        100.0,
        counts["FAIL"] * 25.0 + counts["MISSING"] * 20.0 + counts["REVIEW"] * 8.0,
    )
    if risk_score >= 75:
        risk_band = "CRITICAL"
    elif risk_score >= 50:
        risk_band = "HIGH"
    elif risk_score >= 25:
        risk_band = "MEDIUM"
    else:
        risk_band = "LOW"

    return {
        "total_requirements": total,
        "passed": counts["PASS"],
        "review": counts["REVIEW"],
        "failed": counts["FAIL"],
        "missing": counts["MISSING"],
        "overall_compliance": round(overall, 1),
        "risk_score": round(risk_score, 1),
        "risk_band": risk_band,
        "gate_status": gate_status,
        "blocking_requirements": len(blocking),
    }
