"""
Beginner exercise: clean Spotify streaming history for Power BI.

Folder layout:
    spotify_project/
        raw/        <- put all your Streaming_History_*.json files here
        output/     <- the script writes the clean CSV here
        preprocess_spotify.py

Install once:  pip install pandas
Run:           python preprocess_spotify.py
"""

from pathlib import Path
import pandas as pd

RAW_DIR = Path("../my_spotify_data")
OUT_DIR = Path("./cleaned_data")
OUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------
# 1. LOAD: read every JSON file and stack them into one table
# ---------------------------------------------------------------
frames = []
for file in sorted(RAW_DIR.glob("*.json")):
    frames.append(pd.read_json(file))
    print(f"Loaded {file.name}")

df = pd.concat(frames, ignore_index=True)
print(f"\nRaw rows: {len(df):,}")

# ---------------------------------------------------------------
# 2. EXPLORE: always look at your data before cleaning it
# ---------------------------------------------------------------
print(df.info())
print(df.isna().sum())

# ---------------------------------------------------------------
# 3. CLEAN
# ---------------------------------------------------------------
# Keep music only (podcast rows have no track name)
df = df[df["master_metadata_track_name"].notna()].copy()

# Drop columns we don't need (ip_addr is also personal data)
df = df.drop(columns=[
    "ip_addr", "offline_timestamp",
    "episode_name", "episode_show_name", "spotify_episode_uri",
    "audiobook_title", "audiobook_uri", "audiobook_chapter_uri", "audiobook_chapter_title"
])

# Friendlier column names
df = df.rename(columns={
    "master_metadata_track_name": "track",
    "master_metadata_album_artist_name": "artist",
    "master_metadata_album_name": "album",
})

# Remove accidental duplicates
df = df.drop_duplicates(subset=["ts", "spotify_track_uri"])

# ---------------------------------------------------------------
# 4. TRANSFORM: create columns that make charts easy
# ---------------------------------------------------------------
df["ts"] = pd.to_datetime(df["ts"], utc=True)

df["date"] = df["ts"].dt.date
df["year"] = df["ts"].dt.year
df["month"] = df["ts"].dt.month
df["weekday"] = df["ts"].dt.day_name()
df["hour"] = df["ts"].dt.hour

df["minutes_played"] = (df["ms_played"] / 60000).round(2)

# Ignore very short plays (under 30 seconds) = likely skips, not real listens
df["is_real_listen"] = df["ms_played"] >= 30_000

# Power BI handles timezone-aware timestamps awkwardly, so drop the timezone
df["ts"] = df["ts"].dt.tz_localize(None)

# ---------------------------------------------------------------
# 5. EXPORT
# ---------------------------------------------------------------
out_file = OUT_DIR / "streams_clean.csv"
df.to_csv(out_file, index=False)
print(f"\nClean rows: {len(df):,}")
print(f"Saved to {out_file}")
