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


def test_create_qa_rag():
    response = client.get("/v1/knowledge/rag/qa", headers={
        "Authorization": "Bearer $2b$12$ynT6V44Pz9kwSq6nwgbqxOdTPl/GGpc2YkRaJkHn0ps5kvQo6uyF6"
    })
    assert response.status_code == 200
    data = response.json()
    print(data)
