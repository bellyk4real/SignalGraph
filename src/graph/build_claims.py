"""Turns validated raw_record rows into the canonical graph: claims, evidence,
source documents/chunks, funding rounds, and relationship edges.

Demonstrates the exact contrast from README's "Core product principle":
- the vendor-sourced funding round becomes only a candidate claim (vendor
  sources cannot create accepted claims — corroboration required);
- the first-party announcement becomes an accepted, evidence-backed claim,
  and materializes the funding_round + entity_relationship graph edges.

Usage: uv run python -m src.graph.build_claims
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db import get_session_factory
from src.graph.claims import ClaimPolicyError, accept_claim, attach_evidence, submit_claim
from src.graph.documents import create_source_document
from src.graph.models import Claim, EntityRelationship, EntityType, FundingRound, Sensitivity
from src.ingestion.models import RawRecord
from src.resolution.matcher import get_or_create_entity


@dataclass
class ClaimBuildSummary:
    candidate_claims: int = 0
    accepted_claims: int = 0


def _valid_unclaimed_records(session: Session, record_type: str) -> list[RawRecord]:
    """Valid raw_records of this type that don't already have a claim —
    keeps this stage idempotent across reruns, same as every ingestion
    connector.
    """
    already_claimed = set(session.scalars(select(Claim.raw_record_id).where(Claim.raw_record_id.is_not(None))).all())
    records = session.scalars(
        select(RawRecord).where(RawRecord.record_type == record_type, RawRecord.validation_status == "valid")
    ).all()
    return [r for r in records if r.id not in already_claimed]


def build_vendor_candidate_claims(session: Session, summary: ClaimBuildSummary) -> None:
    """Vendor funding-round rows become candidate-only claims: vendor_enrichment
    is not authorized to create accepted claims (see data/source_registry.yml),
    so accept_claim() would reject them until corroborated by a first-party
    source. See README's "Claim source cannot support claim type" gate.
    """
    for record in _valid_unclaimed_records(session, "vendor_funding_round"):
        payload = record.raw_payload
        company = get_or_create_entity(session, entity_type=EntityType.COMPANY, canonical_name=payload["company_name"])
        claim = submit_claim(
            session,
            subject_entity_id=company.id,
            claim_type="funding_round",
            claim_value=payload,
            source_id=record.source_id,
            confidence=0.3,
            raw_record_id=record.id,
        )
        summary.candidate_claims += 1

        try:
            accept_claim(session, claim)
        except ClaimPolicyError:
            pass  # expected: vendor_enrichment cannot create accepted claims


def build_official_document_claims(session: Session, summary: ClaimBuildSummary) -> None:
    for record in _valid_unclaimed_records(session, "official_document"):
        payload = record.raw_payload
        document = create_source_document(
            session,
            source_id=record.source_id,
            raw_record_id=record.id,
            full_text=payload["full_text"],
            url=payload.get("url"),
            title=payload.get("title"),
            sensitivity=Sensitivity.PUBLIC,
            published_at=payload.get("published_at"),
        )

        if record.source_id == "first_party_website":
            _build_thesis_claim(session, payload, document, record.id, summary)
        elif record.source_id == "first_party_announcement":
            _build_funding_round_claim(session, payload, document, record.id, summary)


def _build_thesis_claim(session: Session, payload: dict, document, raw_record_id, summary: ClaimBuildSummary) -> None:
    northstar = get_or_create_entity(session, entity_type=EntityType.INVESTOR_FIRM, canonical_name="Northstar Ventures")
    claim = submit_claim(
        session,
        subject_entity_id=northstar.id,
        claim_type="thesis",
        claim_value={"text": payload["claim_span"]},
        source_id="first_party_website",
        confidence=0.9,
        raw_record_id=raw_record_id,
    )
    attach_evidence(session, claim, source_document=document, text_span=payload["claim_span"])
    accept_claim(session, claim)
    summary.candidate_claims += 1
    summary.accepted_claims += 1


def _build_funding_round_claim(
    session: Session, payload: dict, document, raw_record_id, summary: ClaimBuildSummary
) -> None:
    gridflow = get_or_create_entity(session, entity_type=EntityType.COMPANY, canonical_name="GridFlow GmbH")
    northstar = get_or_create_entity(session, entity_type=EntityType.INVESTOR_FIRM, canonical_name="Northstar Ventures")
    example_capital = get_or_create_entity(session, entity_type=EntityType.INVESTOR_FIRM, canonical_name="Example Capital")

    claim = submit_claim(
        session,
        subject_entity_id=gridflow.id,
        claim_type="funding_round",
        claim_value={
            "round_type": "seed",
            "amount": "4000000",
            "currency": "EUR",
            "announced_on": "2026-05-15",
            "led_by": "Northstar Ventures",
            "participants": ["Example Capital"],
        },
        source_id="first_party_announcement",
        confidence=0.95,
        raw_record_id=raw_record_id,
    )
    attach_evidence(session, claim, source_document=document, text_span=payload["claim_span"])
    accept_claim(session, claim)
    summary.candidate_claims += 1
    summary.accepted_claims += 1

    funding_round = FundingRound(
        company_entity_id=gridflow.id,
        round_type="seed",
        amount=4_000_000,
        currency="EUR",
        announced_on=date(2026, 5, 15),
    )
    session.add(funding_round)
    session.flush()

    session.add_all(
        [
            EntityRelationship(
                from_entity_id=gridflow.id, relationship_type="received_capital_in", to_funding_round_id=funding_round.id
            ),
            EntityRelationship(
                from_entity_id=northstar.id, relationship_type="led", to_funding_round_id=funding_round.id
            ),
            EntityRelationship(
                from_entity_id=example_capital.id, relationship_type="participated_in", to_funding_round_id=funding_round.id
            ),
            EntityRelationship(
                from_entity_id=northstar.id, relationship_type="portfolio_company_of", to_entity_id=gridflow.id
            ),
        ]
    )
    session.flush()


def main() -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = ClaimBuildSummary()
        build_vendor_candidate_claims(session, summary)
        build_official_document_claims(session, summary)
        session.commit()
    print(f"claims: {summary.candidate_claims} submitted as candidate, {summary.accepted_claims} accepted")


if __name__ == "__main__":
    main()
