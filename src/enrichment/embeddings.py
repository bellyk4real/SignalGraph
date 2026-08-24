"""Pluggable embedding provider for document_chunk.embedding.

The default implementation is a deterministic, offline, dependency-free
hashing embedding — it lets pgvector columns be real and populated end to
end without a model download or API key in this environment. It is NOT
semantically meaningful beyond exact/near-duplicate text matching.

To use a real model, implement `EmbeddingProvider` (e.g. wrapping
sentence-transformers or an API client) and swap the instance returned by
`get_embedding_provider()` — no other code changes needed.
"""

import hashlib
import math
import re
from typing import Protocol

EMBEDDING_DIM = 128


class EmbeddingProvider(Protocol):
    dimension: int

    def embed(self, text: str) -> list[float]: ...


class DeterministicHashEmbeddingProvider:
    dimension = EMBEDDING_DIM

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign

        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


def get_embedding_provider() -> EmbeddingProvider:
    return DeterministicHashEmbeddingProvider()
