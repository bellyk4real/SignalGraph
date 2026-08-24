import os

import pytest
from sqlalchemy import select

pytest.importorskip("psycopg")

from src.db import get_engine, get_session_factory  # noqa: E402
from src.graph.models import Entity, EntityResolutionDecision, ResolutionDecisionType  # noqa: E402
from src.ingestion import synthetic_vendor  # noqa: E402
from src.resolution.matcher import RULE_VERSION, resolve_vendor_investors, reverse_resolution_decision  # noqa: E402
from src.validation.quality_gates import validate_pending_raw_records  # noqa: E402


@pytest.fixture
def db_session():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set; skipping DB-dependent test")
    try:
        get_engine().connect().close()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres not reachable: {exc}")

    session_factory = get_session_factory()
    with session_factory() as session:
        yield session
        session.rollback()


@pytest.fixture
def resolved_investors(db_session):
    synthetic_vendor.main()
    validate_pending_raw_records(db_session)
    resolve_vendor_investors(db_session)

    entities = {
        e.canonical_name: e
        for e in db_session.scalars(select(Entity)).all()
        if e.canonical_name in {"Northstar Ventures", "North Star Ventures", "Northstar Venture"}
    }
    decisions = db_session.scalars(select(EntityResolutionDecision)).all()
    return entities, decisions


def test_v001_and_v002_match_on_shared_domain(resolved_investors):
    entities, decisions = resolved_investors
    v001, v002 = entities["Northstar Ventures"], entities["North Star Ventures"]

    match = next(d for d in decisions if d.subject_entity_id == v002.id)
    assert match.decision == ResolutionDecisionType.MATCH
    assert match.matched_entity_id == v001.id
    assert match.match_score == 1.0
    assert match.features["domain_match"] is True
    assert match.rule_version == RULE_VERSION


def test_v003_stays_separate_despite_name_similarity(resolved_investors):
    entities, decisions = resolved_investors
    v003 = entities["Northstar Venture"]

    decision = next(d for d in decisions if d.subject_entity_id == v003.id)
    assert decision.decision != ResolutionDecisionType.MATCH
    assert decision.matched_entity_id is None
    assert decision.features["domain_match"] is False
    assert decision.features["geography_match"] is False
    # every V-00x entity remains a distinct row -- no destructive merge
    assert len({e.id for e in entities.values()}) == 3


def test_decision_has_score_reason_and_rule_version(resolved_investors):
    _, decisions = resolved_investors
    for decision in decisions:
        assert decision.match_score is not None
        assert decision.rule_version == RULE_VERSION
        assert decision.features


def test_reversal_path(db_session, resolved_investors):
    _, decisions = resolved_investors
    match_decision = next(d for d in decisions if d.decision == ResolutionDecisionType.MATCH)
    assert match_decision.reversed_at is None

    reverse_resolution_decision(db_session, match_decision, reason="manual correction in review")

    assert match_decision.reversed_at is not None
    assert match_decision.reversal_reason == "manual correction in review"
