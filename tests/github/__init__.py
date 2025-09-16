import json

import requests


def main():
    """
    Test to get the list of models add Header api_key: testkey
    """
    GITHUB_COPILOT_API_BASE = "https://api.githubcopilot.com"
    from runtime.transformation.github.Authenticator import Authenticator, GetAPIKeyError

    authenticator = Authenticator()
    # dynamic_api_base = (
    #         authenticator.get_api_base() or GITHUB_COPILOT_API_BASE
    # )
    # try:
    #     dynamic_api_key = authenticator.get_api_key()
    # except GetAPIKeyError as e:
    #     raise e
    #
    # response = requests.get(
    #     dynamic_api_base+"/models",
    #     headers=authenticator.get_copilot_headers())
    # print(response)
    # assert response.status_code == 200
    # data = response.json()
    # print(json.dumps(data, indent=2))
    print(authenticator.get_models())


if __name__ == "__main__":
    main()
