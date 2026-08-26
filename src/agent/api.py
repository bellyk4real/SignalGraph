"""Thin FastAPI wrapper exposing the three agent tools as typed endpoints.

Usage: uv run uvicorn src.agent.api:app --reload
"""

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from src.agent import tools
from src.agent.schemas import (
    EvidenceReference,
    InvestorCandidateRequest,
    InvestorCandidateResponse,
    InvestorEvidenceRequest,
    RelationshipMemoryRequest,
    RelationshipMemoryResponse,
)
from src.db import get_session

app = FastAPI(title="SignalGraph Agent Tools")


@app.post("/tools/find_investor_candidates", response_model=InvestorCandidateResponse)
def find_investor_candidates(
    request: InvestorCandidateRequest, session: Session = Depends(get_session)
) -> InvestorCandidateResponse:
    return tools.find_investor_candidates(session, request)


@app.post("/tools/get_investor_evidence", response_model=list[EvidenceReference])
def get_investor_evidence(
    request: InvestorEvidenceRequest, session: Session = Depends(get_session)
) -> list[EvidenceReference]:
    return tools.get_investor_evidence(session, request)


@app.post("/tools/search_relationship_memory", response_model=RelationshipMemoryResponse)
def search_relationship_memory(
    request: RelationshipMemoryRequest, session: Session = Depends(get_session)
) -> RelationshipMemoryResponse:
    return tools.search_relationship_memory(session, request)
