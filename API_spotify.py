import json
import os
import time
from pathlib import Path

import requests

class QuotaExceeded(Exception):
    """Raised when Spotify says the quota is used up and the wait is too long."""
    def __init__(self, retry_after):
        super().__init__(f"Quota exhausted, retry after {retry_after:.0f}s")
        self.retry_after = retry_after

class TokenExpired(Exception):
    pass

class TrackNotFound(Exception):
    pass

BASE_DIR = Path(__file__).resolve().parent
TOKEN_FILE = BASE_DIR / "AccessToken.json"
ENV_FILE = BASE_DIR / ".env"


def load_env_file() -> dict[str, str]:
    env_vars: dict[str, str] = {}

    if not ENV_FILE.exists():
        return env_vars

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        env_vars[key.strip()] = value.strip().strip("\"'")

    return env_vars


def get_client_credentials() -> tuple[str, str]:
    env_vars = load_env_file()
    client_id = env_vars.get("SPOTIFY_CLIENT_ID")
    client_secret = env_vars.get("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing Spotify credentials. Add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET to your environment or to a .env file."
        )

    return client_id, client_secret


"""
Check if the current Access token is still valid. If it is valid return the access token,
 otherwise request an new one, store it, and return it.
"""
def get_access_token() -> dict:
    token = load_access_token()
    if token is not None and is_valid_access_token(token):
        return token

    token = request_new_access_token()
    store_access_token(token)
    return token

"""
Requests a new Spotify access token using the client credentials flow.
Returns a dict with keys like ["access_token", "token_type", "expires_in"],
plus generated_at and expires_at timestamps.
"""
def request_new_access_token() -> dict:
    client_id, client_secret = get_client_credentials()

    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        timeout=10,
    )
    response.raise_for_status()

    token = response.json()
    expires_in = token.get("expires_in")
    if expires_in is None:
        raise ValueError("Missing expires_in in Spotify token response")

    generated_at = time.time()
    token["generated_at"] = generated_at
    token["expires_at"] = generated_at + float(expires_in)
    return token


"""
Save the Spotify token payload to AccessToken.json.
"""
def store_access_token(token_dict: dict) -> None:
    TOKEN_FILE.write_text(json.dumps(token_dict, ensure_ascii=False, indent=4), encoding="utf-8")

"""
Load the spotify token from the AccessToken.json file
"""
def load_access_token() -> dict | None:
    try:
        with TOKEN_FILE.open("r", encoding="utf-8") as file:
            token = json.load(file)
    except (json.JSONDecodeError, OSError):
        return None

    return token if isinstance(token, dict) else None



"""
Check whether the stored access token is still valid.
"""
def is_valid_access_token(token: dict, refresh_before: int = 60) -> bool:
    access_token = token.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        return False

    try:
        expires_at = float(token["expires_at"])
    except (KeyError, TypeError, ValueError):
        return False

    return expires_at > time.time() + refresh_before

"""
Perform a generic GET-request and return the result as a JSON
"""
def get_json(url, headers, params=None, max_retries=5,
             base_delay=0.4, max_wait=300):
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
        except (requests.Timeout, requests.ConnectionError):
            if attempt == max_retries:
                raise
            time.sleep(2 ** attempt)          # 1, 2, 4, 8... seconds
            continue

        # Success: pause briefly to stay under the rate limit
        if response.ok:
            time.sleep(base_delay)            # ~2.5 requests/second
            return response.json()

        # Expired or invalid token: let the caller refresh it
        if response.status_code == 401:
            raise TokenExpired("Access token expired or invalid")

        if response.status_code == 404:
            raise TrackNotFound(url)
        
        # Rate limited
        if response.status_code == 429:
            try:
                delay = max(0, float(response.headers.get("Retry-After", "5")))
            except ValueError:
                delay = 5

            try:
                reason = response.json().get("error", {}).get("reason")
            except ValueError:
                reason = None

            # Long wait or quota exhausted: stop instead of sleeping for hours
            if delay > max_wait or reason == "QUOTA_EXCEEDED":
                raise QuotaExceeded(delay)

            if attempt == max_retries:
                response.raise_for_status()
            time.sleep(delay)
            continue

        # Temporary server errors: retry with backoff
        if response.status_code >= 500 and attempt < max_retries:
            time.sleep(2 ** attempt)
            continue

        # Anything else (403, 404, ...): fail immediately
        response.raise_for_status()

def API_request_tracks(track_id: str) -> dict:
    if not track_id:
        raise ValueError("track_id must not be empty")
    
    url = f"https://api.spotify.com/v1/tracks/{track_id}"
    try:
        token = get_access_token()
        return get_json(url, {"Authorization": f"Bearer {token}"})
    except TokenExpired:
        token = get_access_token()   # retry once with a fresh token
        return get_json(url, {"Authorization": f"Bearer {token}"})


