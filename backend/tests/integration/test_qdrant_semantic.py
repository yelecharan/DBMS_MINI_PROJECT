import os
import uuid

import pytest

from app.services.vector_service import vector_service


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("QDRANT_URL"),
        reason="Set QDRANT_URL to run real Qdrant semantic integration tests.",
    ),
]


def test_real_model_semantic_search_and_qdrant_crud():
    assert vector_service.is_embedding_available(), vector_service.embedding_error
    collection = vector_service.client.get_collection(vector_service.collection_name)
    assert collection.config.params.vectors.size == 384
    assert collection.config.params.vectors.distance.value == "Cosine"

    incident_id = str(uuid.uuid4())
    summary = (
        "An employee entered through Gate 2 while another person followed "
        "without presenting an access badge."
    )
    metadata = {
        "gate_name": "Gate 2",
        "site_name": "Integration Test Site",
        "incident_type": "TAILGATING",
        "severity": "HIGH",
        "status": "NEW",
        "risk_score": 68.5,
    }

    try:
        embedding = vector_service.generate_embedding(summary)
        assert len(embedding) == 384
        assert sum(value * value for value in embedding) == pytest.approx(1.0, abs=1e-3)
        assert vector_service.upsert_incident_vector(incident_id, summary, metadata)

        point = vector_service.get_incident_vector(incident_id)
        assert point is not None
        assert point["payload"]["summary"] == summary
        assert len(point["vector"]) == 384

        assert vector_service.update_incident_payload(
            incident_id, {"status": "UNDER_INVESTIGATION"}
        )
        updated = vector_service.get_incident_vector(incident_id)
        assert updated["payload"]["status"] == "UNDER_INVESTIGATION"

        results = vector_service.search_similar_incidents(
            "People entering without scanning their employee cards.",
            limit=10,
            score_threshold=0.15,
            severity="HIGH",
            status="UNDER_INVESTIGATION",
            raise_errors=True,
        )
        assert any(result["incident_id"] == incident_id for result in results)
    finally:
        vector_service.delete_incident_vector(incident_id)

    assert vector_service.get_incident_vector(incident_id) is None
