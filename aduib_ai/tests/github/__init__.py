import json

import requests

def main():
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



if __name__ == "__main__":
    main()