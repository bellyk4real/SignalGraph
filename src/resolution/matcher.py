"""Conservative entity resolution over validated vendor-investor records.

Every source identity gets its own Entity row — resolution never physically
merges rows, it only records an explainable, reversible decision about
whether one entity is canonical for another. See README "Entity resolution":
"Retain all original source identities" and "Prefer an unresolved duplicate
to a harmful false merge."

Usage: uv run python -m src.resolution.matcher
"""

from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db import get_session_factory
from src.graph.models import Entity, EntityIdentifier, EntityResolutionDecision, EntityType, ResolutionDecisionType
from src.ingestion.models import RawRecord

RULE_VERSION = "vendor_investor_matcher_v1"
NAME_SIMILARITY_REVIEW_THRESHOLD = 0.85


@dataclass
class ResolutionSummary:
    entities_created: int = 0
    matched: int = 0
    needs_review: int = 0
    no_match: int = 0


def normalize_domain(domain: str) -> str:
    return domain.strip().lower()


def name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def resolve_vendor_investors(session: Session) -> ResolutionSummary:
    summary = ResolutionSummary()

    # created_at is transaction-scoped (Postgres now() is stable within a
    # transaction), so rows written by the same ingestion run can tie on it.
    # Order on the vendor's own ID instead for a deterministic processing
    # order that doesn't depend on insertion timing.
    records = session.scalars(
        select(RawRecord)
        .where(RawRecord.record_type == "vendor_investor", RawRecord.validation_status == "valid")
        .order_by(RawRecord.raw_payload["vendor_investor_id"].astext)
    ).all()

    already_resolved_vendor_ids = {
        identifier.identifier_value
        for identifier in session.scalars(
            select(EntityIdentifier).where(EntityIdentifier.identifier_type == "vendor_investor_id")
        ).all()
    }

    # Seed `resolved` with every previously-created investor entity (not just
    # ones from this call) so a rerun still compares new records against the
    # full existing population instead of only its own batch.
    resolved: list[tuple[Entity, dict]] = []
    for entity in session.scalars(select(Entity).where(Entity.entity_type == EntityType.INVESTOR_FIRM)).all():
        identifiers = {
            i.identifier_type: i.identifier_value
            for i in session.scalars(
                select(EntityIdentifier).where(EntityIdentifier.entity_id == entity.id)
            ).all()
        }
        if "domain" in identifiers:
            resolved.append(
                (entity, {"investor_name": entity.canonical_name, "domain": identifiers["domain"], "country": identifiers.get("country")})
            )

    for record in records:
        payload = record.raw_payload
        if payload["vendor_investor_id"] in already_resolved_vendor_ids:
            continue

        name = payload["investor_name"]
        domain = normalize_domain(payload["domain"])
        country = payload["country"]

        entity = Entity(entity_type=EntityType.INVESTOR_FIRM, canonical_name=name)
        session.add(entity)
        session.flush()
        summary.entities_created += 1

        session.add(
            EntityIdentifier(
                entity_id=entity.id,
                identifier_type="domain",
                identifier_value=domain,
                source_id=record.source_id,
                verified=True,
            )
        )
        session.add(
            EntityIdentifier(
                entity_id=entity.id,
                identifier_type="vendor_investor_id",
                identifier_value=payload["vendor_investor_id"],
                source_id=record.source_id,
                verified=True,
            )
        )
        session.add(
            EntityIdentifier(
                entity_id=entity.id,
                identifier_type="country",
                identifier_value=country,
                source_id=record.source_id,
                verified=True,
            )
        )

        if resolved:
            scored = [
                (other, domain == normalize_domain(other_payload["domain"]),
                 name_similarity(name, other_payload["investor_name"]),
                 country == other_payload["country"])
                for other, other_payload in resolved
            ]
            domain_matches = [s for s in scored if s[1]]
            if domain_matches:
                other, domain_match, sim, geo_match = domain_matches[0]
                decision, score, matched_entity_id = ResolutionDecisionType.MATCH, 1.0, other.id
                summary.matched += 1
            else:
                other, domain_match, sim, geo_match = max(scored, key=lambda s: s[2])
                if sim >= NAME_SIMILARITY_REVIEW_THRESHOLD and geo_match:
                    decision, score, matched_entity_id = ResolutionDecisionType.NEEDS_REVIEW, sim, None
                    summary.needs_review += 1
                else:
                    decision, score, matched_entity_id = ResolutionDecisionType.NO_MATCH, sim, None
                    summary.no_match += 1

            session.add(
                EntityResolutionDecision(
                    subject_entity_id=entity.id,
                    matched_entity_id=matched_entity_id,
                    decision=decision,
                    match_score=round(score, 4),
                    features={
                        "compared_against_entity_id": str(other.id),
                        "domain_match": domain_match,
                        "name_similarity": round(sim, 4),
                        "geography_match": geo_match,
                    },
                    rule_version=RULE_VERSION,
                    reviewer="system",
                )
            )

        resolved.append((entity, payload))

    session.commit()
    return summary


def reverse_resolution_decision(session: Session, decision: EntityResolutionDecision, reason: str) -> None:
    """Marks a decision reversed. The subject/matched entity rows and their
    identifiers are untouched — resolution never destroys source data, so
    reversal only needs to stop downstream consumers from treating the
    decision as active (they must filter on reversed_at IS NULL).
    """
    from datetime import UTC, datetime

    decision.reversed_at = datetime.now(UTC)
    decision.reversal_reason = reason
    session.flush()


def main() -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = resolve_vendor_investors(session)
    print(
        f"resolved {summary.entities_created} investor entities: "
        f"{summary.matched} matched, {summary.needs_review} needs_review, {summary.no_match} no_match"
    )


if __name__ == "__main__":
    main()
