import json

import requests
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




def test_get_models_github_copilot():
    """
    Test to get the list of models add Header api_key: testkey
    """
    GITHUB_COPILOT_API_BASE = "https://api.githubcopilot.com"
    from runtime.transformation.github.Authenticator import Authenticator,GetAPIKeyError
    authenticator = Authenticator()
    dynamic_api_base = (
            authenticator.get_api_base() or GITHUB_COPILOT_API_BASE
    )
    try:
        dynamic_api_key = authenticator.get_api_key()
    except GetAPIKeyError as e:
        raise e

    response = requests.get(
        dynamic_api_base+"/models",
        headers={"X-API-Key": dynamic_api_key,"Authorization": f"Bearer {dynamic_api_key}","user-agent": "GithubCopilot/1.155.0","content-type": "application/json"})
    assert response.status_code == 200
    data = response.json()
    print(json.dumps(data, indent=2))
