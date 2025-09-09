from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

def test_add_model():
    response = client.post(
        "v1/models/add",
        json={
        "model_name": "Modelscope.cn/bartowski/Qwen_Qwen3-30B-A3B-Thinking-2507-GGUF:Q8_0",
        "provider_name": "ollama",
        "model_type": "llm",
        "max_tokens": 262144,
        "model_configs": {"temperature": 0.6, "top_k": 20, "top_p": 0.95, "presence_penalty ": 1.5, "miniP":0},
        "model_feature": ["tool"],
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
            "provider_name": "github",
            "supported_model_types": ["llm", "tts", "asr", "embedding", "ranker"],
            "provider_type": "github",
            "provider_config": {"api_key": "testkey", "api_base": "http://10.0.0.96:8000"}
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