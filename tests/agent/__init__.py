import json

import requests
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_create_agent2():
    response = client.post(
        "/v1/agents",
        json={
            "name": "Code Generator Assistant Agent",
            "description": "An AI agent that helps users generate code snippets based on their requirements.",
            "model_id": "15",
            "tools": [],
            "prompt_template": """You are an AI assistant skilled in helping developers with code completion. Your task is to automatically complete missing parts of the code based on the user-provided code snippet, including language, variable names, function definitions, etc. You should ensure the code is syntactically correct, consistent in style, and logically clear.You can handle multiple programming languages (e.g., Python, JavaScript, Java, C++), and you can infer the language from the code snippet if not explicitly stated.""",
            "agent_parameters": {"temperature": 0.01},
        },
        headers={"Authorization": "Bearer $2b$12$ynT6V44Pz9kwSq6nwgbqxOdTPl/GGpc2YkRaJkHn0ps5kvQo6uyF6"},
    )
    assert response.status_code == 200
    data = response.json()
    print(data)


def test_create_agent():
    response = client.post(
        "/v1/agents",
        json={
            "name": "Helpful Assistant Agent",
            "description": "An AI agent that assists users with various tasks and provides helpful information.",
            "model_id": "15",
            "tools": [],
            "prompt_template": """You are a compassionate, professional, and helpful AI assistant. You are capable of identifying the language used by the user and responding in that language. You focus on understanding the user's actual needs and providing assistance in a clear, concise, and friendly manner.""",
            "agent_parameters": {"temperature": 1.0},
        },
        headers={"Authorization": "Bearer $2b$12$ynT6V44Pz9kwSq6nwgbqxOdTPl/GGpc2YkRaJkHn0ps5kvQo6uyF6"},
    )
    assert response.status_code == 200
    data = response.json()
    print(data)
