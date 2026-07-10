import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_product_endpoint_accepts_post_for_barcode_lookup():
    response = client.post('/api/product/8901030895489', json={'preferences': {}})
    assert response.status_code in {200, 404}

def test_health_endpoint():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_news_endpoint():
    response = client.get('/api/news?product_name=Maggi')
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_chat_endpoint():
    response = client.post('/api/chat', json={"message": "hello"})
    assert response.status_code == 200
    assert "response" in response.json()

