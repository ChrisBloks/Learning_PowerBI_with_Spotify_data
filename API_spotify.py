import json
import os
import time
from pathlib import Path

import requests

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
    client_id = os.getenv("SPOTIFY_CLIENT_ID") or env_vars.get("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET") or env_vars.get("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing Spotify credentials. Add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET to your environment or to a .env file."
        )

    return client_id, client_secret


"""
Requests a new Spotify access token using the client credentials flow.
Returns a dict with keys like ["access_token", "token_type", "expires_in"],
plus generated_at and expires_at timestamps.
"""
def get_access_token() -> dict:
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
Check whether the stored access token is still valid.
"""
def is_valid_access_token() -> bool:
    if not TOKEN_FILE.exists():
        return False

    try:
        with TOKEN_FILE.open("r", encoding="utf-8") as file:
            token_dict = json.load(file)
    except (json.JSONDecodeError, OSError):
        return False

    expires_at = token_dict.get("expires_at")
    try:
        return float(expires_at) > time.time()
    except (TypeError, ValueError):
        return False
