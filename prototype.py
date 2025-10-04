import requests, json

# Key, secret, etc. DO NOT EDIT
api_key = "Y2fZMA59MyAHI10MOxJlyGgfPohdvzAf"
api_secret = "G9PNgG384nNHbhLS"
token_url = "https://test.api.amadeus.com/v1/security/oauth2/token"

def get_access_token():
    token_headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": api_key,
        "client_secret": api_secret
    }

    token_response = requests.post(token_url, headers=token_headers, data=data)
    access_token = token_response.json().get("access_token")
    return access_token

def choose_api() -> tuple[str, dict]:
    print("Available APIs:")
    for i, api_name in enumerate(api_configs.keys(), 1):
        print(f"{i}.{api_name}")
    choice = int(input("Choose API: ")) - 1
    api_name = list(api_configs.keys())[choice]
    api_info = api_configs[api_name]
    return api_name, api_info

def choose_parameters(params) -> dict:
    for key in list(params.keys()):
        if not params[key]:
            params[key] = input(f"{key}: ")
    while True:
        others = input("Other Parameters: ")
        if not others:
            break
        param = input("Value: ")
        params.update({others: param})
    return params

def call_api(access_token, params, url):
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers, params=params)
    print(response.status_code)
    if response.status_code == 200:
        with open("output.txt", 'w') as txtfile:
            json.dump(response.json(), txtfile, indent=4)
        print("Response saved to output.txt")

if __name__ == "__main__":
    access_token = get_access_token()
    with open("params.json", "r") as file_params:
        api_configs = json.load(file_params)
    api_name, api_info = choose_api()
    url = api_info["url"]
    params = api_info["params"]
    choose_parameters(params)
    call_api(access_token, params, url)
