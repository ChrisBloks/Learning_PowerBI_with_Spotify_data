import json, time, requests
from pathlib import Path
import pandas as pd
import API_spotify as api_sp

CACHE_TRACKS = Path("track_cache.json")
tracks = json.loads(CACHE_TRACKS.read_text()) if CACHE_TRACKS.exists() else {}

df = pd.read_csv("./cleaned_data/streams_clean.csv")
track_ids = df["spotify_track_uri"].dropna().str.split(":").str[-1].unique()


    