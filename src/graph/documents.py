"""Turns a fetched document into a source_document + embedded, searchable
document_chunk rows.
"""

import hashlib
import re
from datetime import datetime

from sqlalchemy.orm import Session

from src.enrichment.embeddings import get_embedding_provider
from src.graph.models import DocumentChunk, Sensitivity, SourceDocument

DEFAULT_CHUNK_WORDS = 80


def chunk_text(text: str, chunk_words: int = DEFAULT_CHUNK_WORDS) -> list[str]:
    words = re.findall(r"\S+", text)
    if not words:
        return []
    return [" ".join(words[i : i + chunk_words]) for i in range(0, len(words), chunk_words)]


def create_source_document(
    session: Session,
    *,
    source_id: str,
    full_text: str,
    raw_record_id=None,
    url: str | None = None,
    title: str | None = None,
    sensitivity: Sensitivity = Sensitivity.PUBLIC,
    published_at: datetime | None = None,
) -> SourceDocument:
    content_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
    document = SourceDocument(
        source_id=source_id,
        raw_record_id=raw_record_id,
        url=url,
        title=title,
        content_hash=content_hash,
        sensitivity=sensitivity,
        full_text=full_text,
        published_at=published_at,
    )
    session.add(document)
    session.flush()

    provider = get_embedding_provider()
    for index, chunk in enumerate(chunk_text(full_text)):
        session.add(
            DocumentChunk(
                source_document_id=document.id,
                chunk_index=index,
                chunk_text=chunk,
                embedding=provider.embed(chunk),
            )
        )
    session.flush()
    return document
