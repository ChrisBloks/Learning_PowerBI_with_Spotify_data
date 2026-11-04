import json, time, requests
from pathlib import Path
import pandas as pd

CACHE_TRACKS = Path("track_cache.json")
CACHE_ARTISTS = Path("artist_cache.json")
tracks = json.loads(CACHE_TRACKS.read_text()) if CACHE_TRACKS.exists() else {}
artists = json.loads(CACHE_ARTISTS.read_text()) if CACHE_ARTISTS.exists() else {}

track_ids = df["spotify_track_uri"].dropna().str.split(":").str[-1].unique()

# 2. Tracks: duration + primary artist
for n, tid in enumerate(track_ids):
    if tid in tracks:
        continue
    t = get_json(f"https://api.spotify.com/v1/tracks/{tid}", headers)
    tracks[tid] = {
        "duration_ms": t["duration_ms"],
        "artist_id": t["artists"][0]["id"],
    }
    if n % 200 == 0:
        CACHE_TRACKS.write_text(json.dumps(tracks))
CACHE_TRACKS.write_text(json.dumps(tracks))

# 3. Artists: genres (one call per unique artist)
for aid in {v["artist_id"] for v in tracks.values()}:
    if aid in artists:
        continue
    a = get_json(f"https://api.spotify.com/v1/artists/{aid}", headers)
    artists[aid] = a.get("genres", [])
CACHE_ARTISTS.write_text(json.dumps(artists))