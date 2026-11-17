import logging
import math
import os
import uuid
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import settings

logger = logging.getLogger("gatesentry.vector")


class EmbeddingUnavailableError(RuntimeError):
    """Raised when genuine Sentence Transformers embeddings cannot be generated."""


class VectorService:
    def __init__(self):
        self.collection_name = settings.QDRANT_COLLECTION
        self.dim = settings.EMBEDDING_DIMENSION
        self.client = self._init_client()
        self.transformer_model = None
        self._model_loaded = False
        self._embedding_error: Optional[str] = None
        self._init_transformer()
        self._ensure_collection()

    def _init_client(self) -> QdrantClient:
        """Initialize Qdrant client either from URL or local embedded storage."""
        if settings.QDRANT_URL:
            logger.info(f"Connecting to Qdrant at {settings.QDRANT_URL}")
            return QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY,
            )
        os.makedirs(settings.QDRANT_STORAGE_PATH, exist_ok=True)
        logger.info(f"Initializing embedded Qdrant at {settings.QDRANT_STORAGE_PATH}")
        return QdrantClient(path=settings.QDRANT_STORAGE_PATH)

    def _init_transformer(self):
        """Load the declared sentence-transformers model used for real semantic search."""
        try:
            # sentence-transformers itself can fail to import on Windows when torch/torchaudio
            # is incompatible; avoid crashing the app by surfacing the exact limitation.
            import sentence_transformers  # noqa: F401
            from sentence_transformers import SentenceTransformer

            self.transformer_model = SentenceTransformer(
                "all-MiniLM-L6-v2",
                device="cpu",
            )
            dimension = self.transformer_model.get_sentence_embedding_dimension()
            if dimension != self.dim:
                raise ValueError(
                    f"all-MiniLM-L6-v2 returned dimension {dimension}; expected {self.dim}"
                )
            self._model_loaded = True
            self._embedding_error = None
            logger.info(
                "Loaded sentence-transformers/all-MiniLM-L6-v2 on CPU "
                "with %s-dimensional embeddings",
                dimension,
            )
            return self.transformer_model
        except Exception as exc:  # pragma: no cover - environment dependent
            self._model_loaded = True
            self.transformer_model = None
            self._embedding_error = (
                "Semantic embeddings are unavailable because sentence-transformers/all-MiniLM-L6-v2 "
                f"could not be loaded: {type(exc).__name__}: {exc}"
            )
            logger.exception(self._embedding_error)
            return None

    @property
    def embedding_error(self) -> Optional[str]:
        return self._embedding_error

    def is_embedding_available(self) -> bool:
        return self.transformer_model is not None and self._embedding_error is None

    def _get_transformer(self):
        if self._model_loaded:
            return self.transformer_model
        return self._init_transformer()

    def _ensure_collection(self):
        """Create Qdrant collection if not exists with COSINE distance."""
        try:
            collections = self.client.get_collections().collections
            names = [c.name for c in collections]
            if self.collection_name not in names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=self.dim,
                        distance=qmodels.Distance.COSINE,
                    ),
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Error checking/creating Qdrant collection: {e}")

    def generate_embedding(self, text: str) -> List[float]:
        """Generate a 384-dimensional sentence-transformer embedding for semantic similarity."""
        if self._embedding_error is not None:
            raise EmbeddingUnavailableError(self._embedding_error)

        model = self._get_transformer()
        if model is None:
            raise EmbeddingUnavailableError(
                "Embedding generation is unavailable because the semantic model could not be loaded. "
                "No hash-based fallback is used."
            )

        try:
            emb = model.encode(text, normalize_embeddings=True)
            vector = emb.tolist() if hasattr(emb, "tolist") else list(emb)
            if len(vector) != self.dim:
                raise ValueError(
                    f"Expected {self.dim}-dimensional embedding but received {len(vector)} dimensions."
                )
            if not all(math.isfinite(float(value)) for value in vector):
                raise ValueError("The embedding contains non-finite values.")
            norm = math.sqrt(sum(float(value) ** 2 for value in vector))
            if not math.isclose(norm, 1.0, rel_tol=1e-3, abs_tol=1e-3):
                raise ValueError(f"Expected a normalized embedding, received L2 norm {norm:.6f}.")
            return vector
        except Exception as exc:
            raise EmbeddingUnavailableError(
                f"SentenceTransformer embedding generation failed for query: {text!r}. {exc}"
            ) from exc

    def _normalize_point_id(self, id_val: str) -> str:
        """Ensure point ID is a valid UUID format acceptable by Qdrant."""
        try:
            return str(uuid.UUID(str(id_val)))
        except Exception:
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(id_val)))

    # -------------------------------------------------------------
    # 1. CREATE: Insert or Upsert Incident Vector
    # -------------------------------------------------------------
    def upsert_incident_vector(
        self,
        incident_id: str,
        text_summary: str,
        metadata: Dict[str, Any],
        raise_errors: bool = False,
    ) -> bool:
        """Insert or update an incident vector and metadata payload in Qdrant."""
        try:
            vector = self.generate_embedding(text_summary)
            payload = {
                "incident_id": incident_id,
                "summary": text_summary,
                **metadata
            }
            
            point_id = self._normalize_point_id(incident_id)
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    qmodels.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            logger.info(f"Upserted incident vector {incident_id} to Qdrant")
            return True
        except Exception as e:
            logger.error(f"Failed to upsert incident vector {incident_id}: {e}")
            if raise_errors:
                raise
            return False

    # -------------------------------------------------------------
    # 2. READ: Retrieve Vector by Incident ID
    # -------------------------------------------------------------
    def get_incident_vector(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an incident vector point and payload by ID."""
        try:
            pid = self._normalize_point_id(incident_id)
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[pid],
                with_payload=True,
                with_vectors=True
            )
            if points:
                p = points[0]
                return {
                    "id": p.id,
                    "payload": p.payload,
                    "vector": p.vector
                }
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve vector {incident_id}: {e}")
            return None

    # -------------------------------------------------------------
    # 3. UPDATE: Update Payload or Embedding
    # -------------------------------------------------------------
    def update_incident_payload(self, incident_id: str, updated_metadata: Dict[str, Any]) -> bool:
        """Update metadata payload in Qdrant without regenerating vector."""
        try:
            pid = self._normalize_point_id(incident_id)
            self.client.set_payload(
                collection_name=self.collection_name,
                payload=updated_metadata,
                points=[pid]
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update payload for {incident_id}: {e}")
            return False

    # -------------------------------------------------------------
    # 4. DELETE: Remove Incident Vector
    # -------------------------------------------------------------
    def delete_incident_vector(self, incident_id: str) -> bool:
        """Delete an incident point from Qdrant by ID."""
        try:
            pid = self._normalize_point_id(incident_id)
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=qmodels.PointIdsList(points=[pid])
            )
            logger.info(f"Deleted vector {incident_id} from Qdrant")
            return True
        except Exception as e:
            logger.error(f"Failed to delete vector {incident_id}: {e}")
            return False

    # -------------------------------------------------------------
    # 5. SEARCH: Semantic Similarity Query
    # -------------------------------------------------------------
    def search_similar_incidents(
        self,
        query_text: str,
        limit: int = 5,
        score_threshold: float = 0.20,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        raise_errors: bool = False,
    ) -> List[Dict[str, Any]]:
        """Semantic search against incident descriptions using vector cosine distance."""
        try:
            query_vector = self.generate_embedding(query_text)
            
            filter_conditions = []
            if severity:
                filter_conditions.append(
                    qmodels.FieldCondition(
                        key="severity",
                        match=qmodels.MatchValue(value=severity)
                    )
                )
            if status:
                filter_conditions.append(
                    qmodels.FieldCondition(
                        key="status",
                        match=qmodels.MatchValue(value=status)
                    )
                )
                
            query_filter = None
            if filter_conditions:
                query_filter = qmodels.Filter(must=filter_conditions)

            # Query Qdrant
            # Support both client.query_points and search for compatibility across versions
            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=self.collection_name,
                    query=query_vector,
                    query_filter=query_filter,
                    limit=limit,
                    score_threshold=score_threshold
                )
                search_results = response.points
            else:
                search_results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_vector,
                    query_filter=query_filter,
                    limit=limit,
                    score_threshold=score_threshold
                )

            results = []
            for hit in search_results:
                payload = hit.payload or {}
                results.append({
                    "incident_id": payload.get("incident_id", str(hit.id)),
                    "similarity_score": round(float(hit.score), 4),
                    "gate_name": payload.get("gate_name"),
                    "site_name": payload.get("site_name"),
                    "incident_type": payload.get("incident_type", "TAILGATING"),
                    "severity": payload.get("severity", "MEDIUM"),
                    "status": payload.get("status", "NEW"),
                    "risk_score": float(payload.get("risk_score", 0.0)),
                    "created_at": payload.get("created_at"),
                    "summary": payload.get("summary", "")
                })
            return results
        except Exception as e:
            logger.error(f"Semantic search query failed: {e}")
            if raise_errors:
                raise
            return []

vector_service = VectorService()
