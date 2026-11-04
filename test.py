import API_spotify as api_sp
import requests

token = api_sp.get_access_token()["access_token"]
r = requests.get("https://api.spotify.com/v1/tracks/4gC3PmUCFHX1DxuKBpSAfc",
                 headers={"Authorization": f"Bearer {token}"})
print(r.status_code, r.text)