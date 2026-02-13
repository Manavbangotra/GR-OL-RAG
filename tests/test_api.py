"""API tests for RAG chatbot"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "services" in data


def test_stats():
    """Test stats endpoint"""
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert "vector_store" in data


def test_query_without_documents():
    """Test query when no documents are uploaded"""
    response = client.post(
        "/query",
        json={
            "query": "What is dropshipping?",
            "thread_id": "test_thread"
        }
    )
    # Should still work but with low confidence
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "confidence" in data


def test_invalid_query():
    """Test query with invalid data"""
    response = client.post(
        "/query",
        json={
            "query": ""  # Empty query
        }
    )
    assert response.status_code == 422  # Validation error


def test_conversation_history():
    """Test conversation history retrieval"""
    thread_id = "test_history_thread"
    
    # First, make a query to create history
    client.post(
        "/query",
        json={
            "query": "Test query",
            "thread_id": thread_id
        }
    )
    
    # Get history
    response = client.get(f"/history/{thread_id}")
    assert response.status_code == 200
    data = response.json()
    assert "thread_id" in data
    assert "messages" in data


def test_delete_conversation():
    """Test conversation deletion"""
    thread_id = "test_delete_thread"
    
    # Create a conversation
    client.post(
        "/query",
        json={
            "query": "Test query",
            "thread_id": thread_id
        }
    )
    
    # Delete it
    response = client.delete(f"/history/{thread_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_upload_invalid_file_type():
    """Test upload with invalid file type"""
    response = client.post(
        "/upload",
        files={"file": ("test.exe", b"fake content", "application/x-msdownload")}
    )
    assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
