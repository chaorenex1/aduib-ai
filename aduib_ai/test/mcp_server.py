from starlette.testclient import TestClient

from app import app

client = TestClient(app)


def test_add_mcp_server():
    response = client.post(
        "/v1/mcp_server/servers",
        json={
            "name": "Test add MCP Server",
            "description": "this is a test MCP server",
            "status": "active",
            "parameters": "{\"param1\": \"value1\", \"param2\": \"value2\"}"
        },
        headers={"Authorization": "Bearer test_token"}
    )
    assert response.status_code == 200
    data = response.json()
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