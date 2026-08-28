import pytest
from agentic_memory_rag.vector_adapters import BaseVectorAdapter, InMemoryVectorAdapter

def test_in_memory_vector_adapter():
    adapter = InMemoryVectorAdapter()
    adapter.upsert("v1", [1.0, 0.0, 0.0], {"concept": "helios"})
    adapter.upsert("v2", [0.0, 1.0, 0.0], {"concept": "apollo"})
    
    results = adapter.query([1.0, 0.0, 0.0], top_k=1)
    assert len(results) == 1
    assert results[0][0] == "v1"
    assert results[0][1] == pytest.approx(1.0)
    assert results[0][2]["concept"] == "helios"

    # Metadata filtering test
    filtered = adapter.query([1.0, 0.0, 0.0], top_k=5, filter_metadata={"concept": "apollo"})
    assert len(filtered) == 1
    assert filtered[0][0] == "v2"

    adapter.delete("v1")
    post_delete = adapter.query([1.0, 0.0, 0.0], top_k=5)
    assert len(post_delete) == 1
    assert post_delete[0][0] == "v2"
