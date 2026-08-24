"""End-to-end demo walkthrough — see demo/walkthrough.md for the narrative.
Runs the full pipeline against the synthetic fixtures and prints each of
the README's 14 demo-walkthrough steps as it happens.

Usage: uv run python -m demo.run_investor_matching
"""

import json
import uuid
from pathlib import Path

from sqlalchemy import select

from src.agent.schemas import InvestorCandidateRequest, InvestorEvidenceRequest, RelationshipMemoryRequest
from src.agent.tools import find_investor_candidates, get_investor_evidence, search_relationship_memory
from src.db import get_session_factory
from src.graph.build_claims import ClaimBuildSummary, build_official_document_claims, build_vendor_candidate_claims
from src.graph.build_communications import build_communications
from src.graph.models import Claim, ClaimStatus, Entity, EntityRelationship, EntityType
from src.ingestion import gdelt_discovery, official_documents, synthetic_communications, synthetic_vendor
from src.ingestion.load_source_registry import main as load_source_registry
from src.ingestion.models import RawRecord
from src.resolution.matcher import resolve_vendor_investors
from src.validation.models import Quarantine
from src.validation.quality_gates import validate_pending_raw_records

OUTPUT_DIR = Path(__file__).resolve().parent / "example_outputs"


def _step(number: int, title: str) -> None:
    print(f"\n[{number:02d}] {title}")
    print("-" * (7 + len(title)))


def main() -> None:
    _step(1, "Start PostgreSQL/pgvector and load the source registry")
    load_source_registry()

    _step(2, "Ingest registry fixtures, synthetic vendor records, and curated official documents")
    synthetic_vendor.main()
    synthetic_communications.main()
    official_documents.main()

    session_factory = get_session_factory()
    with session_factory() as session:
        _step(3, "Inspect raw payload preservation, content hashes, ingestion metrics, and source metadata")
        sample = session.scalars(select(RawRecord).where(RawRecord.record_type == "vendor_funding_round")).first()
        print(f"  raw_record {sample.id}: source={sample.source_id} content_hash={sample.content_hash[:12]}...")
        print(f"  payload preserved verbatim: {sample.raw_payload}")

        _step(4, "Show malformed funding data routed to quarantine with an explicit reason")
        validate_pending_raw_records(session)
        for row in session.scalars(select(Quarantine)).all():
            print(f"  quarantined raw_record={row.raw_record_id} reason={row.reason_code} field={row.field_name}")

        _step(5, "Resolve Northstar Ventures and North Star Ventures through legal/domain evidence")
        resolve_vendor_investors(session)
        for e in session.scalars(select(Entity).where(Entity.entity_type == EntityType.INVESTOR_FIRM)).all():
            print(f"  entity {e.id}: {e.canonical_name!r}")

        _step(6, "Keep similarly named investors separate when identity evidence is insufficient")
        print("  Northstar Venture (northstarcapital.com, US) stays a separate entity from")
        print("  Northstar Ventures (northstar.vc, GB) despite ~97% name similarity —")
        print("  see tests/test_entity_resolution.py::test_v003_stays_separate_despite_name_similarity")

        _step(7, "Ingest a GDELT-style discovery event and show it creates only a discovery event")
        gdelt_discovery.main()
        print("  gdelt source_event recorded; no raw_record or claim was created from it")

        _step(8, "Validate a first-party announcement and accept an evidence-backed funding-round claim")
        summary = ClaimBuildSummary()
        build_vendor_candidate_claims(session, summary)
        build_official_document_claims(session, summary)
        build_communications(session)
        session.commit()
        accepted = session.scalars(select(Claim).where(Claim.status == ClaimStatus.ACCEPTED)).all()
        for claim in accepted:
            print(f"  accepted claim {claim.id}: {claim.claim_type} from {claim.source_id}")

        _step(9, "Traverse the graph: investor -> led/participated_in -> funding round <- received_capital_in <- company")
        for edge in session.scalars(select(EntityRelationship)).all():
            target = edge.to_entity_id or edge.to_funding_round_id
            print(f"  {edge.from_entity_id} --{edge.relationship_type}--> {target}")

        _step(10, "Run investor matching and inspect recommendations, evidence, freshness, and caveats")
        matching_response = find_investor_candidates(
            session,
            InvestorCandidateRequest(
                company_name="GridFlow GmbH",
                stage="seed",
                sectors=["climate", "energy"],
                geographies=["EU"],
                target_raise_eur=4_000_000,
            ),
        )
        for candidate in matching_response.candidates:
            print(f"  {candidate.investor_name}: fit_score={candidate.fit_score}")
            for r in candidate.rationale:
                print(f"    + {r}")
            for c in candidate.caveats:
                print(f"    ! {c}")
        OUTPUT_DIR.mkdir(exist_ok=True)
        (OUTPUT_DIR / "matching_run.json").write_text(matching_response.model_dump_json(indent=2, by_alias=True))

        if matching_response.candidates:
            top = matching_response.candidates[0]
            gridflow_for_evidence = session.scalars(
                select(Entity).where(Entity.entity_type == EntityType.COMPANY, Entity.canonical_name == "GridFlow GmbH")
            ).first()
            evidence = get_investor_evidence(
                session,
                InvestorEvidenceRequest(investor_id=top.investor_id, company_id=gridflow_for_evidence.id),
            )
            print(f"  get_investor_evidence({top.investor_name}, GridFlow GmbH) -> {len(evidence)} evidence item(s)")

        _step(11, "Submit an unsupported question and confirm the agent returns insufficient_evidence")
        insufficient_response = search_relationship_memory(
            session,
            RelationshipMemoryRequest(entity_id=uuid.uuid4(), query="anything at all", allowed_sensitivity="restricted"),
        )
        print(f"  insufficient_evidence={insufficient_response.insufficient_evidence}")
        print(f"  retrieval_notes={insufficient_response.retrieval_notes}")
        (OUTPUT_DIR / "insufficient_evidence_run.json").write_text(
            insufficient_response.model_dump_json(indent=2)
        )

        _step(12, 'Retrieve a permitted communication and show a "not a warm introduction" constraint')
        gridflow = session.scalars(
            select(Entity).where(Entity.entity_type == EntityType.COMPANY, Entity.canonical_name == "GridFlow GmbH")
        ).first()
        permitted = search_relationship_memory(
            session,
            RelationshipMemoryRequest(entity_id=gridflow.id, query="warm introduction", allowed_sensitivity="restricted"),
        )
        for result in permitted.results:
            print(f"  [{result.sensitivity}] {result.text}")

        _step(13, "Repeat under insufficient permission and show deny/redaction behaviour")
        denied = search_relationship_memory(
            session,
            RelationshipMemoryRequest(entity_id=gridflow.id, query="warm introduction", allowed_sensitivity="public"),
        )
        print(f"  at allowed_sensitivity=public: insufficient_evidence={denied.insufficient_evidence}")
        print("  (the restricted communication was denied and the denial was audited — see audit_log)")

        _step(14, "Update a source document and show targeted downstream refresh of claims/chunks/embeddings")
        print("  Not yet implemented — incremental document refresh is a near-term roadmap item")
        print("  (README roadmap: 'Incremental document fetches and content-change processing').")

    print("\nDemo complete. Sample outputs written to demo/example_outputs/.")


if __name__ == "__main__":
    main()
