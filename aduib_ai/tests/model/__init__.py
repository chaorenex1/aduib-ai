from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

def test_add_model():
    response = client.post(
        "v1/models/add",
        json={
        "model_name": "Qwen/Qwen3-Embedding-0.6B",
        "provider_name": "transformer",
        "model_type": "embedding",
        "max_tokens": 8192,
        "model_configs": {},
        "model_feature": [],
        "input_price": 0.00,
        "output_price": 0.00
    }
    )
    assert response.status_code == 200



def test_add_emb_model():
    response = client.post(
        "v1/models/add",
        json={
        "model_name": "modelscope.cn/Qwen/Qwen3-Embedding-8B-GGUF:Q8_0",
        "provider_name": "ollama",
        "model_type": "embedding",
        "max_tokens": 262144,
        "model_configs": {"max_embedding_tokens": 4096},
        "model_feature": [],
        "input_price": 0.00,
        "output_price": 0.00
    }
    )
    assert response.status_code == 200


def test_add_provider():
    response = client.post(
        "v1/providers/add",
        json={
            "provider_name": "transformer",
            "supported_model_types": ["llm", "tts", "asr", "embedding", "reranker"],
            "provider_type": "transformer",
            "provider_config": {"models_path": "/models"}
        }
    )
    assert response.status_code == 200
    data = response.json()
    print(data)


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
    assert len(data) > 0
    for model in data:
        print(model)