from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_chat_completion_no_stream():
    response = client.post(
        "/v1/chat/completions",
        json={
    "model": "modelscope.cn/unsloth/Qwen3-30B-A3B-GGUF:latest",
    "messages": [
        {
            "role": "user",
            "content": "1+1=？"
        }
    ],
    "temperature": 1,
    "top_p": 1,
    "stream": "false",
    "stream_options": {
        "include_usage": "false"
    },
    "enable_thinking": "false"
},
        headers={"X-API-Key": "$2b$12$ynT6V44Pz9kwSq6nwgbqxOdTPl/GGpc2YkRaJkHn0ps5kvQo6uyF6"}
    )
    assert response.status_code == 200
    data = response.json()
    print(data)

def test_chat_completion_stream():
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "modelscope.cn/unsloth/Qwen3-30B-A3B-GGUF:latest",
            "messages": [
                {
                    "role": "user",
                    "content": "1+1=？"
                }
            ],
            "temperature": 1,
            "top_p": 1,
            "stream": "true",
            "stream_options": {
                "include_usage": "false"
            },
            "enable_thinking": "false"
        },
        headers={"X-API-Key": "$2b$12$ynT6V44Pz9kwSq6nwgbqxOdTPl/GGpc2YkRaJkHn0ps5kvQo6uyF6"}
    )
    assert response.status_code == 200
    print(response.text)



def test_completion_no_stream():
    response = client.post(
        "/v1/completions",
        json={
    "model": "modelscope.cn/unsloth/Qwen3-30B-A3B-GGUF:latest",
    "prompt": "1+1=？",
    "temperature": 1,
    "top_p": 1,
    "stream": "false",
    "stream_options": {
        "include_usage": "false"
    }
},
        headers={"X-API-Key": "$2b$12$ynT6V44Pz9kwSq6nwgbqxOdTPl/GGpc2YkRaJkHn0ps5kvQo6uyF6"}
    )
    assert response.status_code == 200
    data = response.json()
    print(data)



def test_completion_stream():
    response = client.post(
        "/v1/completions",
        json={
    "model": "modelscope.cn/unsloth/Qwen3-30B-A3B-GGUF:latest",
    "prompt": "1+1=？",
    "temperature": 1,
    "top_p": 1,
    "stream": "true",
    "stream_options": {
        "include_usage": "true"
    }
},
        headers={"X-API-Key": "$2b$12$ynT6V44Pz9kwSq6nwgbqxOdTPl/GGpc2YkRaJkHn0ps5kvQo6uyF6"}
    )
    assert response.status_code == 200
    data = response.text
    print(data)


def test_completion_json_object():
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "modelscope.cn/unsloth/Qwen3-30B-A3B-GGUF:latest",
            "messages": [
    {
      "role": "system",
      "content": "你是一个助手，请始终输出结构化 JSON 数据。"
    },
    {
      "role": "user",
      "content": "生成一个用户信息对象，包含姓名、年龄和技能。"
    }
  ],
            "temperature": 1,
            "top_p": 1,
            "stream": "false",
            "stream_options": {
                "include_usage": "false"
            },
            "response_format": {
                "type": "json_object",
                # "properties": {
                #     "name": {"type": "string"},
                #     "age": {"type": "integer"},
                #     "skills": {"type": "array", "items": {"type": "string"}}
                # }
            },
        },
        headers={"X-API-Key": "$2b$12$ynT6V44Pz9kwSq6nwgbqxOdTPl/GGpc2YkRaJkHn0ps5kvQo6uyF6"}
    )
    assert response.status_code == 200
    data = response.json()
    print(data)


def test_completion_json_schema():
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "modelscope.cn/unsloth/Qwen3-30B-A3B-GGUF:latest",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个助手，请始终输出结构化 JSON 数据。"
                },
                {
                    "role": "user",
                    "content": "生成一个用户信息对象，包含姓名、年龄和技能。"
                }
            ],
            "temperature": 1,
            "top_p": 1,
            "stream": "false",
            "stream_options": {
                "include_usage": "false"
            },
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "UserInfo",
                    "description": "用户信息对象",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "integer"},
                            "skills": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["name", "age", "skills"]
                    },
                }
            },
        },
        headers={"X-API-Key": "$2b$12$ynT6V44Pz9kwSq6nwgbqxOdTPl/GGpc2YkRaJkHn0ps5kvQo6uyF6"}
    )
    assert response.status_code == 200
    data = response.json()
    print(data)