import json

from starlette.testclient import TestClient

from app import app

client = TestClient(app)


def test_add_mcp_server():
    response = client.post(
        "/v1/mcp_server/servers",
        json={
            "server_url": "http://10.0.0.96:5002",
            "name": "Aduib MCP Server",
            "description": "this is a Aduib MCP server",
            "status": "active",
            "configs": json.dumps({
                "client_type": "streamable",
                "authed": "false",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0"
            })
        },
        headers={"Authorization": "Bearer test_token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0


def test_update_mcp_server():
    response = client.put(
        "/v1/mcp_server/servers/4347034a-ef20-4637-a951-8b67ee146b00",
        json={
            "server_url": "http://10.0.0.124:5002",
            "name": "Aduib MCP Server",
            "description": "this is a Aduib MCP server",
            "status": "active",
            "configs": json.dumps({
                "client_type": "streamable",
                "authed": "true",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
                "credential_type": "api_key",
                "api_key": "Bearer $2b$12$WB2YoxB5CQtPbqN35UDso.of2n7BmDvvQpxmIUdKe2VHO.MAY1u26",
                "in": "header",
                "name": "Authorization"
            }),
            "credentials": "api_key"
        },
        headers={"Authorization": "Bearer test_token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0

def test_init_tools():
    response = client.get(
        "/v1/mcp_server/init_tools/P9Q5NHTdFd8hbeAd")
    data = response.json()
    print(data)
    assert response.status_code == 200
    assert data["code"] == 0

def test_mcp():
    response = client.post(
        "/v1/mcp/test_server_code",
        json={
            "jsonrpc": "2.0",
            "method": "testMethod",
            "params": {"param1": "value1"},
            "id": 1
        },
        headers={"X-API-Key": "$2b$12$ynT6V44Pz9kwSq6nwgbqxOdTPl/GGpc2YkRaJkHn0ps5kvQo6uyF6"}
    )
    assert response.status_code == 200
    data = response.json()
    print(data)