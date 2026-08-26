SignalGraph

    Evidence-first investor intelligence for trustworthy agent retrieval.

SignalGraph is a provenance-first operational knowledge graph for companies, investor firms, people, funds, funding rounds, documents, and communications. It creates a governed data spine that AI agents and product workflows can use to identify credible investor matches, retrieve relationship context, and explain why a fact is trustworthy.

It is intentionally not an analytics warehouse, a generic RAG chatbot, or a web-scraping demo. SignalGraph is a product-oriented data platform built around a harder question:

    Can an agent retrieve the correct fact about a company, investor, funding event, or prior conversation—and show the evidence, source authority, freshness, entity identity, and uncertainty behind it?

Why SignalGraph

Founder–investor matching, outreach, and relationship management depend on data that is fragmented and difficult to trust:

    One company can have a legal name, operating name, previous name, multiple vendor IDs, and several domains.

    Investor data can disagree across official websites, registries, news, vendor feeds, and historical documents.

    Funding announcements, portfolio pages, investor theses, emails, and call transcripts contain useful context but are rarely linked to the right canonical entities.

    A false entity merge can attach a funding round, portfolio relationship, or warm-introduction context to the wrong company or person.

    A vector search can find semantically similar text without proving a factual claim.

    A discovered news event is not the same as verified evidence.

SignalGraph treats data trust as a product feature. Every agent-visible fact should be traceable to its evidence and governed by explicit source, freshness, identity, and access-control policies.
What it does

SignalGraph provides six core capabilities:

    Ingests and preserves source data — stores raw records/documents, retrieval metadata, content hashes, and ingestion-run history before destructive transformation.

    Validates and quarantines bad data — schema validation, quality gates, source policy checks, and clear quarantine reasons prevent bad records from entering the graph.

    Resolves entities conservatively — links companies and people across sources through explainable, versioned, and reversible match decisions.

    Models an operational knowledge graph — represents companies, investors, people, funds, funding rounds, documents, and relationships as Postgres entities and edges.

    Stores facts as evidence-backed claims — preserves conflicting, stale, candidate, rejected, and superseded assertions rather than silently overwriting attributes.

    Supports hybrid agent retrieval — combines structured SQL filters, graph traversal, PostgreSQL full-text search, and pgvector semantic search to return evidence-first results.

Core product principle

text
Discovery is not evidence.
Evidence is not truth without policy.
Truth is not useful unless an agent can retrieve it safely.

For example:

text
GDELT finds an article saying: “GridFlow raises €4m seed round.”

GDELT event
  → creates a discovery event only
  → original publisher/press release is fetched
  → source document is stored and validated
  → funding claims are extracted with text spans
  → source policy decides whether claims can be accepted
  → accepted claims become eligible for agent retrieval

A discovery source never bypasses source validation and becomes a canonical fact on its own.
Architecture

text
                         ┌──────────────────────────┐
                         │      Source registry     │
                         │ authority • freshness    │
                         │ permissions • policy     │
                         └────────────┬─────────────┘
                                      │
       ┌──────────────────────────────┼──────────────────────────────┐
       │                              │                              │
       ▼                              ▼                              ▼
┌───────────────┐             ┌───────────────┐              ┌───────────────┐
│ Registries    │             │ First-party   │              │ Discovery /   │
│ Companies     │             │ websites and  │              │ enrichment    │
│ House / SEC   │             │ press releases│              │ GDELT, etc.   │
└──────┬────────┘             └──────┬────────┘              └──────┬────────┘
       │                              │                              │
       └──────────────────────┬───────┴───────────┬──────────────────┘
                              ▼                   ▼
                   ┌────────────────────┐  ┌───────────────────┐
                   │ Raw records/docs   │  │ Source events     │
                   │ hashes • metadata  │  │ discovered/fetched│
                   └─────────┬──────────┘  └─────────┬─────────┘
                             │                       │
                             ▼                       ▼
                   ┌──────────────────────────────────────────┐
                   │ Validation, quarantine, and source policy │
                   │ Pydantic • quality gates • dbt tests      │
                   └───────────────────┬──────────────────────┘
                                       │
                                       ▼
                   ┌──────────────────────────────────────────┐
                   │ Canonical knowledge graph                 │
                   │ entities • identifiers • relationships    │
                   │ funding rounds • entity-resolution map    │
                   └───────────────────┬──────────────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
          ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
          │ Claims +        │ │ Documents +     │ │ Restricted      │
          │ provenance      │ │ chunks + search │ │ communications  │
          │ evidence/status │ │ FTS + pgvector  │ │ permission-aware│
          └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
                   └───────────────────┴───────────────────┘
                                       │
                                       ▼
                   ┌──────────────────────────────────────────┐
                   │ Agent retrieval layer                     │
                   │ SQL filters • graph traversal • hybrid    │
                   │ evidence • freshness • caveats            │
                   └──────────────────────────────────────────┘

Source policy

SignalGraph uses a source registry as a first-class control plane. Every ingestion source has an explicit authority tier, allowed claim types, freshness expectation, privacy classification, and agent-retrieval policy.
Source class	Example	Intended use	Can create accepted claims?
Government/company registry	UK Companies House, SEC EDGAR	Legal identity, status, officers, filings	Yes, only within source scope
First-party website	Company/investor sites	Thesis, portfolio, team, official descriptions	Yes, with retained evidence
First-party announcement	Company/investor press release	Funding rounds, participation, milestones	Yes, when explicitly stated
Discovery feed	GDELT	News discovery and refresh triggers	No; must fetch and validate original source
Reference graph	Wikidata, OpenAlex	Aliases, cross-IDs, research context	No; requires corroboration
Vendor enrichment	Vendor/API export	Candidate facts and match candidates	No; validate/corroborate first
Screening source	OpenSanctions	Possible-match screening	Review only; never automatic conclusion
Communications	Synthetic email/call corpus	Permission-aware relationship memory	Restricted by access policy
Example source registry record

text
source_id: companies_house
source_name: UK Companies House
source_type: government_registry
authority_tier: 1
permitted_claim_types:
  - legal_name
  - company_status
  - incorporation_date
  - registered_office
  - officer_relationship
freshness_sla_hours: 168
pii_classification: public
allowed_for_agent_retrieval: true
requires_human_review: false

Data model

SignalGraph models a graph relationally in PostgreSQL. It intentionally uses Postgres node/edge tables instead of a separate graph database so that graph relationships, data contracts, document search, operational state, and transactional integrity live in one platform.

text
Company ── received_capital_in ── Funding Round
Investor ── participated_in ── Funding Round
Investor ── led ── Funding Round
Investor ── portfolio_company_of ── Company
Person ── partner_at ── Investor
Person ── founder_of ── Company
Person ── introduced_by ── Person
Document ── supports ── Claim
Claim ── describes ── Entity or relationship
Communication ── involves ── Person / Company / Investor

Canonical entities
Entity type	Examples
company	Startup, operating company, legal entity
investor_firm	Venture-capital firm, angel syndicate, corporate VC
person	Founder, investor, partner, advisor, contact
fund	Specific investment fund/vehicle
Core records
Model	Purpose
source_registry	Source authority, claim policy, freshness, sensitivity, and retrieval eligibility
ingestion_run	Pipeline-run metrics, status, and error context
raw_record	Immutable raw structured payloads and source metadata
source_event	Discovery/change events, including GDELT findings
entity	Canonical graph node
entity_identifier	Source IDs, domains, registry numbers, aliases, and verified identifiers
entity_resolution_decision	Explainable, versioned, reversible matching outcomes
funding_round	First-class funding event, not a flat investor/company field
entity_relationship	Effective-dated typed graph edge
claim	Candidate/accepted/disputed/superseded factual assertion
source_document	Raw/parsed document, content hash, source metadata, sensitivity
claim_evidence	Evidence document and text span supporting a claim
document_chunk	Full-text and vector-searchable document segment
communication	Restricted email/call memory representation
Funding rounds are first-class

A funding round is a separate entity/event because “invested in” is not precise enough for a live product:

text
GridFlow GmbH
  └── received capital in → GridFlow Seed Round 2026
                                ├── amount → €4,000,000
                                ├── announced on → 2026-05-15
                                ├── led by → Northstar Ventures
                                └── participated in → Example Capital

This preserves the difference between a portfolio relationship, one specific investment, a lead role, a follow-on round, and an unverified rumour.
Claim and provenance model

SignalGraph does not overwrite business facts directly onto an entity record. Instead, it stores each assertion as a claim, linked to evidence, source policy, status, confidence, and validity.

text
Claim:
  Northstar Ventures invests at Seed

Evidence:
  Official thesis page, retrieved 2026-08-20
  Exact source text span: “We lead Seed and Series A investments…”

Policy:
  First-party investor site
  Authority tier 1
  Claim type permitted
  Agent-visible if accepted and within freshness policy

Claim status lifecycle

text
candidate
  → accepted
  → disputed
  → superseded
  → rejected

Only claims that are accepted, evidence-backed, permitted by source policy, non-expired, and authorised for the calling context are visible to agents by default.
Entity resolution

Entity resolution is a governed decision, not a destructive deduplication step.
Principles

    Retain all original source identities and raw data.

    Prefer an unresolved duplicate to a harmful false merge.

    Store the rule version, match score, features, evidence, reviewer, and timestamp for every decision.

    Make match/merge decisions reversible.

    Keep identity resolution separate from attribute survivorship.

    Do not allow low-authority sources to override legal or verified identifier evidence.

Match tiers
Evidence	Typical action
Exact Companies House number or SEC CIK	Deterministic company match
Exact verified company domain	Strong positive match feature
Exact known source-system mapping	Deterministic match
Similar company names with matching geography	Candidate only unless corroborated
Same person name with no stable identifier	Review/non-match by default
Same email address	Positive signal, but not always automatic merge evidence
Example: safe duplicate handling

text
V-001: Northstar Ventures     → northstar.vc → GB
V-002: North Star Ventures    → northstar.vc → GB
V-003: Northstar Venture      → northstarcapital.com → US

Expected outcome:

    V-001 and V-002 can match when verified domain and legal identity evidence agree.

    V-003 remains a separate entity despite name similarity.

Hybrid retrieval for agents

SignalGraph combines four retrieval methods:

    Structured SQL filters for hard constraints such as stage, sector, country, entity type, and claim status.

    Graph traversal for investor portfolios, partner affiliations, funding history, and relationship paths.

    PostgreSQL full-text search for exact terms, entities, and terminology.

    pgvector semantic search for relevant narrative evidence in theses, portfolio descriptions, news, and permitted communications.

Embeddings help discover evidence; they are not an authoritative fact store.
Investor matching flow

text
Target company profile
  → validate stage, sectors, geography, target raise
  → retrieve accepted investor thesis/focus claims
  → traverse portfolios and prior funding relationships
  → retrieve first-party evidence via lexical + vector search
  → apply authority, freshness, status, and permissions policy
  → rank candidates
  → return recommendations only with evidence and caveats

Ranking sketch

text
candidate_score =
    0.25 * stage_fit
  + 0.20 * sector_fit
  + 0.15 * geography_fit
  + 0.15 * cheque_size_fit
  + 0.10 * portfolio_similarity
  + 0.05 * source_authority_score
  + 0.05 * evidence_quality
  + 0.05 * freshness_score

These weights are versioned configuration, evaluated against labelled fixtures, and are not hard-coded product truth.
Agent tools

The initial agent interface is intentionally narrow and typed.
find_investor_candidates

Find evidence-supported investors for a company and fundraise profile.

python
class InvestorCandidateRequest(BaseModel):
    company_id: UUID | None
    company_name: str
    stage: str
    sectors: list[str]
    geographies: list[str]
    target_raise_eur: int | None
    max_results: int = 10
    allowed_sensitivity: str = "public"

get_investor_evidence

Retrieve the evidence behind an investor/company fit assessment.

python
class InvestorEvidenceRequest(BaseModel):
    investor_id: UUID
    company_id: UUID
    allowed_sensitivity: str

search_relationship_memory

Retrieve permission-filtered relationship and communication context.

python
class RelationshipMemoryRequest(BaseModel):
    entity_id: UUID
    query: str
    allowed_sensitivity: str
    max_results: int = 10

Agent response contract

Every result should contain evidence and uncertainty:

python
class EvidenceReference(BaseModel):
    claim_id: UUID | None
    document_id: UUID
    chunk_id: UUID | None
    source_id: str
    source_url: str | None
    excerpt: str
    authority_tier: int
    published_at: datetime | None
    retrieved_at: datetime
    confidence: float

class InvestorCandidate(BaseModel):
    investor_id: UUID
    investor_name: str
    fit_score: float
    rationale: list[str]
    caveats: list[str]
    evidence: list[EvidenceReference]
    data_freshness: datetime

If minimum evidence is not available, the agent returns:

json
{
  "candidates": [],
  "insufficient_evidence": true,
  "retrieval_notes": [
    "No accepted, sufficiently recent evidence supports a qualifying investor match."
  ]
}

Data quality and safety
Core quality gates
Rule	Action
Unregistered source tries to ingest data	Reject ingestion
Invalid date, currency, URL, or record type	Quarantine record with field-level error
Negative funding amount	Quarantine record
Accepted claim has no evidence	Prevent agent visibility
Claim source cannot support claim type	Retain as candidate or reject per policy
GDELT discovery creates an accepted claim without original source	Block publication
Identity match score below threshold	Send to review; do not merge
Restricted communication requested without permission	Deny and audit access event
Source freshness exceeds SLA	Flag claim as stale and disclose caveat
Example faulty feed

text
vendor_round_id,company_name,round_type,amount,currency,announced_on
R-001,GridFlow GmbH,seed,4000000,EUR,2026-05-15
R-002,GridFlow GmbH,series_a,3000000,EUR,2026-15-48
R-003,Unknown Corp,seed,-250000,EUR,2026-06-01
R-004,GridFlow GmbH,seed,4000000,EURO,2026-05-15

Record	Expected result
R-001	Valid candidate funding round
R-002	Quarantine: invalid date
R-003	Quarantine: negative funding amount
R-004	Quarantine: invalid ISO currency
Security and communications

The MVP uses synthetic emails and call transcripts only. It still models real operational privacy boundaries.

    Every document has a sensitivity level: public, internal, or restricted.

    Raw communications are separated from redacted/searchable representations.

    Permission filtering occurs before retrieval and ranking.

    Restricted data is not available through generic search.

    Denied/successful sensitive retrievals are auditable.

    Screening results are review-only and excluded from general agent retrieval.

Example communication constraint

text
We spoke with Northstar Ventures last quarter. Jane Doe was interested in
GridFlow’s grid-flexibility work, but asked us to reconnect after our first
commercial deployment. Please do not treat this as a warm introduction
without asking me first.

The correct system behaviour is to preserve that context as a restricted, time-bound constraint. It must not infer an active warm introduction or generate outreach without further authorisation.
Technology stack
Layer	Technology	Purpose
Operational database	PostgreSQL / Supabase	Graph, claims, evidence, source control, transactional state
Vector search	pgvector	Semantic retrieval over document chunks
Lexical search	PostgreSQL full-text search	Exact terms, entity names, and keyword search
Ingestion	Python	Connectors, parsing, hashes, source events, incremental loads
Validation	Pydantic	Typed source contracts and agent tool contracts
Transformation/testing	dbt	Derived views, lineage, data tests, documentation
API	FastAPI, optional	Typed retrieval and agent-tool endpoints
Agent integration	Pydantic AI / Claude Agent SDK compatible	Structured tool calls and evidence-first output
Local environment	Docker Compose	Reproducible development and demo setup
Testing	pytest + dbt tests	Unit, integration, policy, quality, and retrieval evaluation tests

Container image

On every push to main that passes its own test/migration gate, .github/workflows/cd.yml builds
and publishes the agent-tools API (src/agent/api.py) as a Docker image to GitHub Container
Registry:

bash
docker pull ghcr.io/bellyk4real/signalgraph:latest
docker run -p 8000:8000 -e DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db \
    ghcr.io/bellyk4real/signalgraph:latest

The image only contains the FastAPI app, its runtime dependencies, and enough of the repo
(src/, demo/, data/, infra/migrations/) to also run `uv run alembic upgrade head` or the demo
script inside the container. It expects an already-running Postgres/pgvector instance — it does
not bundle one. Tags: `latest` and the full commit SHA.

Repository structure

The tree below is the actual, current layout (not aspirational) — one file/dir per pipeline stage:

text
signalgraph/
├── README.md
├── pyproject.toml, uv.lock, alembic.ini
├── architecture/
│   ├── architecture.md, data-model.md, source-policy.md, threat-model.md
│   ├── adr-001-postgres-graph.md
│   ├── adr-002-provenance-first-claims.md
│   └── adr-004-source-registry.md
├── infra/
│   ├── docker-compose.yml
│   └── migrations/            # Alembic; 8 migrations, env.py wired to src.db.Base.metadata
├── src/
│   ├── db.py                  # engine/session factory, UUIDPKMixin/TimestampMixin
│   ├── settings.py            # pydantic-settings, reads .env
│   ├── ingestion/
│   │   ├── base.py            # content-hashing + idempotent raw_record/source_event/ingestion_run writes
│   │   ├── models.py          # SourceRegistry, IngestionRun, RawRecord, SourceEvent
│   │   ├── schemas.py, load_source_registry.py
│   │   ├── synthetic_vendor.py, synthetic_communications.py, official_documents.py
│   │   ├── gdelt_discovery.py     # discovery-only, never creates a raw_record/claim
│   │   └── companies_house.py     # typed connector, not wired into the demo pipeline
│   ├── validation/
│   │   ├── schemas.py, models.py (Quarantine), quality_gates.py
│   ├── graph/                  # canonical knowledge graph (entity/claim/evidence/etc.) + claim lifecycle
│   │   ├── models.py, claims.py, documents.py, build_claims.py, build_communications.py
│   ├── resolution/
│   │   └── matcher.py          # conservative entity resolution, reversible decisions
│   ├── enrichment/
│   │   └── embeddings.py       # pluggable EmbeddingProvider (deterministic offline default)
│   ├── retrieval/
│   │   ├── ranking.py, hybrid.py
│   └── agent/
│       ├── schemas.py, tools.py, api.py (FastAPI), models.py + audit.py (audit_log)
├── dbt/
│   ├── dbt_project.yml, profiles.yml
│   ├── models/staging/, models/marts/ (mart_current_accepted_claims)
│   └── tests/
├── data/
│   ├── synthetic/               # vendor feed (incl. the faulty rows), communications, official documents
│   └── source_registry.yml      # all 8 source classes from the Source policy table
├── tests/
│   ├── conftest.py               # shared db_session fixture
│   ├── test_ingestion_quality.py, test_source_policy.py, test_entity_resolution.py
│   ├── test_provenance.py, test_permissions.py, test_retrieval_evals.py
└── demo/
    ├── run_investor_matching.py  # runs the 14-step walkthrough below end to end
    ├── walkthrough.md
    └── example_outputs/

Quick start

    Implemented and runnable end to end — this is not aspirational. The commands below
    are exactly what CI/the demo/the test suite run; see "Project status" for what's
    built versus still on the roadmap.

Prerequisites

    Docker and Docker Compose

    Python 3.12+

    uv or pip

    PostgreSQL client tools, optional

1. Clone and configure

bash
git clone https://github.com/<your-github-username>/signalgraph.git
cd signalgraph
cp .env.example .env

2. Start local services

bash
docker compose -f infra/docker-compose.yml up -d postgres

3. Install application dependencies

bash
uv sync --extra dev
# or: pip install -e '.[dev]'

4. Apply migrations and load source policies

bash
uv run alembic upgrade head
uv run python -m src.ingestion.load_source_registry

5. Load synthetic data and curated source fixtures

bash
uv run python -m src.ingestion.synthetic_vendor
uv run python -m src.ingestion.synthetic_communications
uv run python -m src.ingestion.official_documents

6. Build transformations and run tests

bash
cd dbt && DBT_PROFILES_DIR=. uv run dbt build && cd ..
uv run pytest

7. Run the demo workflow

bash
uv run python -m demo.run_investor_matching

Demo walkthrough

`uv run python -m demo.run_investor_matching` (see `demo/walkthrough.md`) runs this end to end
against the synthetic fixtures and prints every step below as it happens. Sample output from
steps 10 and 11 is captured in `demo/example_outputs/`. Every step is implemented and runs
against real data except the last, which is intentionally not — see the note below.

    Start PostgreSQL/pgvector and load the source registry.

    Ingest registry fixtures, synthetic vendor records, and curated official documents.

    Inspect raw payload preservation, content hashes, ingestion metrics, and source metadata.

    Show malformed funding data routed to quarantine with an explicit reason.

    Resolve Northstar Ventures and North Star Ventures through legal/domain evidence.

    Keep similarly named people separate because identity evidence is insufficient.

    Ingest a GDELT-style discovery event and show it creates only a validation task.

    Validate a first-party announcement and accept an evidence-backed funding-round claim.

    Traverse the graph: investor → partner → portfolio company → funding round.

    Run investor matching and inspect structured recommendations, source authority, evidence excerpts, freshness, and caveats.

    Submit an unsupported question and confirm the agent returns insufficient_evidence.

    Retrieve a permitted communication and show a “not a warm introduction” constraint.

    Repeat under insufficient permission and show deny/redaction behaviour.

    Update a source document and show targeted downstream refresh of claims/chunks/embeddings.
    Not yet implemented — incremental document refresh is a near-term roadmap item (see Roadmap below);
    the demo script says so explicitly rather than faking the step.

Evaluation criteria
Area	Target
Ingestion idempotency	Rerunning a fixed input creates no duplicate records
Source-policy compliance	Every ingested record has a registered source; discovery/reference sources cannot silently publish accepted claims
Data quality	All deliberate invalid fixtures are quarantined with correct reason codes
Provenance	100% of agent-visible accepted claims have evidence
Entity resolution	All decisions have a score, reason codes, rule version, and reversal path
Evidence coverage	Every recommendation rationale includes supporting evidence
Unsupported claims	Zero unsupported factual assertions in curated evaluation prompts
Sensitive data	No restricted fixture leaks in permission-negative tests
Retrieval	Establish and document retrieval precision@5 against labelled fixtures

All rows above except Retrieval are exercised by `tests/` against the current fixture set (31
tests, `uv run pytest`) — see the row-to-test mapping in each test module's docstring/name.
Retrieval precision@5 against a labelled fixture set has not been built; `tests/test_retrieval_evals.py`
currently checks correctness of individual queries (evidence present, permission-filtered,
insufficient_evidence returned when appropriate), not precision/recall at scale. That remains
open — see "Richer retrieval evaluation dataset" in Roadmap.

Deliberate design decisions
PostgreSQL rather than a dedicated graph database

The project uses relational node/edge tables because the product needs graph traversal, transactional data integrity, document search, quality controls, and operational state in one place. Postgres is sufficient for the intended graph scale and aligns with a pragmatic product architecture.
pgvector rather than a standalone vector database

Embeddings remain next to documents, claims, identities, and source metadata. This simplifies hybrid retrieval and avoids a separate operational system for the MVP.
Claims instead of overwritten entity attributes

A company/investor fact can be stale, disputed, source-specific, or superseded. Claims make disagreement and correction explicit while preserving agent-safe current-state views.
Conservative identity resolution

A false merge can corrupt investment history, relationship context, and communications. The pipeline prefers human review and unresolved duplicates to unsafe automatic canonicalisation.
Synthetic communications only

The project demonstrates the engineering and security patterns for communication memory without processing private, confidential, or non-consented real-world content.
Roadmap
Near-term

    Manual-review interface for entity-resolution and claim decisions.

    Wire the existing typed Companies House connector (src/ingestion/companies_house.py, currently
    untested against the live API and not called by the demo pipeline) and other permitted public-source connectors into the ingestion pipeline.

    Incremental document fetches and content-change processing.

    Source-quality/corroboration scoring.

    Richer retrieval evaluation dataset.

    Monitoring, freshness alerting, and dbt state-aware execution.

Later

    Multi-hop graph retrieval with explainable relationship paths.

    Human-approved outreach/campaign integration.

    Per-user row-level access controls.

    Active-learning workflow for entity resolution.

    Source refresh prioritisation based on query demand and evidence decay.

    Feedback loops that improve investor-match ranking from GTM outcomes.

Project status

MVP implemented and verified end to end. All seven stages of the original implementation
sequence are built, tested, and runnable against a local Postgres/pgvector instance:

text
1. Local Postgres + pgvector environment      done — infra/docker-compose.yml, infra/migrations/ (8 migrations)
2. Source registry and migrations             done — data/source_registry.yml, src/ingestion/load_source_registry.py
3. Synthetic vendor/communications ingestion   done — src/ingestion/ (idempotent on rerun)
4. Validation and quarantine                   done — src/validation/ (quality gates, reason codes)
5. Entity resolution and canonical graph       done — src/resolution/, src/graph/ (conservative, reversible)
6. Claims/evidence/document search             done — src/graph/claims.py, dbt/ (FTS + pgvector)
7. Agent retrieval tools and evaluation suite   done — src/agent/, src/retrieval/, tests/

Run `uv run python -m demo.run_investor_matching` for the full walkthrough, or `uv run pytest`
for the test suite (31 tests, all passing as of this writing). See "Roadmap" above for what's
deliberately out of scope for the MVP — most notably incremental document/claim refresh and a
manual-review interface for entity-resolution and claim decisions.

Each stage above was built and merged as its own pull request, one per implementation sprint,
in the order listed.

License and data notice

This repository should contain only synthetic data, public metadata, or content that is explicitly permitted for the project’s intended use. Do not commit API credentials, private contact details, confidential communications, copyrighted source content outside permissible storage/use, or real customer/investor correspondence.

The project is an engineering portfolio demonstration. It does not provide investment advice, legal/compliance determinations, or automated outreach authority.
