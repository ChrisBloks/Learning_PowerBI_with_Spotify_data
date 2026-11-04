import API_spotify as api_sp

token = api_sp.get_access_token()

response = api_sp.get_json

print(response)