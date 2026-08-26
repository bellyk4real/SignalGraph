"""Versioned ranking configuration — README's "Ranking sketch": weights are
config evaluated against labelled fixtures, not hard-coded product truth.
"""

RANKING_CONFIG_VERSION = "v1"

RANKING_WEIGHTS: dict[str, float] = {
    "stage_fit": 0.25,
    "sector_fit": 0.20,
    "geography_fit": 0.15,
    "cheque_size_fit": 0.15,
    "portfolio_similarity": 0.10,
    "source_authority_score": 0.05,
    "evidence_quality": 0.05,
    "freshness_score": 0.05,
}

assert abs(sum(RANKING_WEIGHTS.values()) - 1.0) < 1e-9


def candidate_score(component_scores: dict[str, float]) -> float:
    return sum(RANKING_WEIGHTS[key] * component_scores.get(key, 0.0) for key in RANKING_WEIGHTS)
