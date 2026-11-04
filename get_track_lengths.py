import json
from pathlib import Path

import pandas as pd

import API_spotify as api_sp

NOT_FOUND = -2       # track no longer exists on Spotify; don't retry it every run
SAVE_EVERY = 100

BASE_DIR = Path(__file__).resolve().parent
CACHE_TRACKS = BASE_DIR / "track_cache.json"
STREAMS_FILE = BASE_DIR / "cleaned_data" / "streams_clean.csv"


def load_track_ids() -> list[str]:
    df = pd.read_csv(STREAMS_FILE)
    track_ids = (
        df["spotify_track_uri"]
        .dropna()
        .astype(str)
        .str.split(":")
        .str[-1]
        .str.strip()
    )
    return list(dict.fromkeys(track_id for track_id in track_ids if track_id))


def load_track_cache() -> dict[str, int]:
    if not CACHE_TRACKS.exists():
        return {}

    cache = json.loads(CACHE_TRACKS.read_text(encoding="utf-8"))
    if not isinstance(cache, dict):
        raise ValueError(f"{CACHE_TRACKS} must contain a JSON object.")

    return cache


def save_track_cache(track_lengths: dict[str, int]) -> None:
    CACHE_TRACKS.write_text(
        json.dumps(track_lengths, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )


def has_runtime(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def get_track_lengths() -> dict[str, int]:
    track_lengths = load_track_cache()
    track_ids = load_track_ids()

    for track_id in track_ids:
        if track_id not in track_lengths:
            track_lengths[track_id] = -1       # -1 = pending
    save_track_cache(track_lengths)

    pending_ids = [
        t for t in track_ids
        if not has_runtime(track_lengths[t]) and track_lengths[t] != NOT_FOUND
    ]

    try:
        for n, track_id in enumerate(pending_ids, start=1):
            try:
                track = api_sp.API_request_tracks(track_id)
            except api_sp.TrackNotFound:
                track_lengths[track_id] = NOT_FOUND
                continue

            if not isinstance(track, dict) or track.get("id") != track_id:
                raise RuntimeError(
                    f"Spotify returned an invalid response for track {track_id}."
                )

            duration_ms = track.get("duration_ms")
            if not has_runtime(duration_ms):
                raise RuntimeError(
                    f"Spotify returned an invalid duration for track {track_id}."
                )
            track_lengths[track_id] = duration_ms

            if n % SAVE_EVERY == 0:
                save_track_cache(track_lengths)
                print(f"{n}/{len(pending_ids)} done")
    except api_sp.QuotaExceeded as e:
        print(f"{e}. Progress saved; rerun later.")
    finally:
        save_track_cache(track_lengths)        # always keep what you have

    return track_lengths


if __name__ == "__main__":
    get_track_lengths()
