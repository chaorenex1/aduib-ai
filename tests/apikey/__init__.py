from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_create_api_key(monkeypatch):
    # def mock_create_api_key(name, description):
    #     return ApiKey(id=1, name=name, description=description, api_key="testkey")
    # monkeypatch.setattr("service.api_key_service.ApiKeyService.create_api_key", mock_create_api_key)
    response = client.post("/v1/api_key/create_api_key", params={"name": "ai_service_key", "description": "ai_service_key"},headers={"X-API-Key": "$2b$12$ynT6V44Pz9kwSq6nwgbqxOdTPl/GGpc2YkRaJkHn0ps5kvQo6uyF6"},)
    assert response.status_code == 200
    data = response.json()
    print(data)
