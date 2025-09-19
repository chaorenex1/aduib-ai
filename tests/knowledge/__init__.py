import json

import requests
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_create_knowledge_base():
    response = client.post(
        "/v1/knowledge/bases",
        json={
            "name": "Default QA Knowledge Base",
            "rag_type": "qa",
            "default_base": 1,
        },
    )
    assert response.status_code == 200
    data = response.json()
    print(data)