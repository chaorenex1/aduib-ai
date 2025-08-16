from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

def test_add_model():
    response = client.post(
        "v1/models/add",
        json={
        "model_name": "Qwen3-30B-A3B-Instruct-2507-FP8",
        "provider_name": "aduib_ai_test",
        "model_type": "llm",
        "max_tokens": 16384,
        "model_configs": {"temperature": 0.7, "top_k": 20, "top_p": 0.9, "frequency_penalty": 0.0, "presence_penalty": 0.0},
        "model_feature": ["tool", "vision"],
        "input_price": 0.01,
        "output_price": 0.02
    }
    )
    assert response.status_code == 200


def test_add_provider():
    response = client.post(
        "v1/providers/add",
        json={
            "provider_name": "aduib_ai",
            "supported_model_types": ["llm", "tts", "asr", "embedding", "ranker"],
            "provider_type": "OpenAI",
            "provider_config": {"api_key": "testkey", "api_base": "http://10.0.0.96:8000"}
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["msg"] == "模型提供者创建成功"


def test_get_models():
    """
    Test to get the list of models add Header api_key: testkey
    """
    response = client.get(
        "v1/models",
        headers={"X-API-Key": "$2b$12$ynT6V44Pz9kwSq6nwgbqxOdTPl/GGpc2YkRaJkHn0ps5kvQo6uyF6"}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    for model in data:
        print(model)