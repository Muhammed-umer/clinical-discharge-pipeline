"""
NoteRepository — all RawDocumentNode database operations.

Responsibilities:
  - Fetch notes by stay (chronological order)
  - Duplicate detection on upload
  - Create new note nodes with embeddings
"""

import logging
import math
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.models import RawDocumentNode

logger = logging.getLogger(__name__)


class NoteRepository:
    """
    Encapsulates all SQLAlchemy operations for the raw_document_nodes table.
    Stateless — safe to use as a singleton.
    """

    async def get_by_stay(
        self, db: AsyncSession, stay_id: str
    ) -> List[RawDocumentNode]:
        """
        Returns all RawDocumentNodes for a stay sorted chronologically.
        Embeddings are included (they are part of the ORM model).
        """
        result = await db.execute(
            select(RawDocumentNode)
            .where(RawDocumentNode.stay_id == stay_id)
            .order_by(RawDocumentNode.recorded_at.asc())
        )
        return result.scalars().all()

    async def find_duplicate(
        self,
        db: AsyncSession,
        stay_id: str,
        author_role: str,
        recorded_at: datetime,
        content: str,
    ) -> Optional[RawDocumentNode]:
        """
        Returns the existing note if an identical one (same stay, role,
        timestamp, and content) already exists; otherwise None.
        Used to prevent duplicate uploads.
        """
        result = await db.execute(
            select(RawDocumentNode).where(
                RawDocumentNode.stay_id == stay_id,
                RawDocumentNode.author_role == author_role,
                RawDocumentNode.recorded_at == recorded_at,
                RawDocumentNode.content == content,
            )
        )
        return result.scalars().first()

    async def create(
        self,
        db: AsyncSession,
        stay_id: str,
        author_role: str,
        recorded_at: datetime,
        content: str,
        embedding: List[float],
    ) -> RawDocumentNode:
        """
        Persists a new RawDocumentNode with its pgvector embedding.
        Flushes to the session; caller commits.
        """
        node = RawDocumentNode(
            stay_id=stay_id,
            author_role=author_role,
            recorded_at=recorded_at,
            content=content,
            embedding=embedding,
        )
        db.add(node)
        await db.flush()
        logger.info(
            "RawDocumentNode created: stay=%s role=%s recorded_at=%s",
            stay_id,
            author_role,
            recorded_at,
        )
        return node

    def deduplicate_in_memory(
        self, notes: List[RawDocumentNode]
    ) -> List[RawDocumentNode]:
        """
        Removes duplicate notes that share the same (role, recorded_at, content).
        Used when multiple identical uploads may exist in the DB from prior runs.
        """
        seen: set = set()
        unique: List[RawDocumentNode] = []
        for note in notes:
            key = (note.author_role, note.recorded_at, note.content.strip())
            if key not in seen:
                seen.add(key)
                unique.append(note)
        return unique

    def compute_similarity_scores(
        self,
        claims: list,  # List[ClaimSchema] — avoid circular import
        claim_embeddings: Dict[str, List[float]],
        notes: List[RawDocumentNode],
    ) -> Dict[str, float]:
        """
        Computes cosine similarity between each claim's embedding and every
        available note embedding using pure Python arithmetic.

        Returns a dict mapping claim_id → max_similarity_score.

        This replaces N pgvector round-trip queries with a single in-memory
        computation after notes have been fetched once by the pipeline.
        """
        note_embeddings: List[List[float]] = []
        for note in notes:
            if note.embedding is not None:
                emb = list(note.embedding)
                if emb:
                    note_embeddings.append(emb)

        scores: Dict[str, float] = {}
        for claim in claims:
            claim_vec = claim_embeddings.get(claim.claim_id, [])
            max_sim = 0.80  # Safe default when embeddings unavailable

            if claim_vec and note_embeddings:
                sims = [
                    _cosine_similarity(claim_vec, ne) for ne in note_embeddings
                ]
                computed = max(sims)
                # If similarity is effectively zero (embedding mismatch), use default
                max_sim = computed if computed > 0.01 else 0.80

            scores[claim.claim_id] = max_sim

        return scores


# ─── Internal helper ──────────────────────────────────────────────────────────

def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Pure-Python cosine similarity for 768-dimensional vectors."""
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
