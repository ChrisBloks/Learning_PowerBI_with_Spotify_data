import json
from pathlib import Path

import pandas as pd

import API_spotify as api_sp

BASE_DIR = Path(__file__).resolve().parent
CACHE_TRACKS = BASE_DIR / "track_cache.json"
STREAMS_FILE = BASE_DIR / "cleaned_data" / "streams_clean.csv"
BATCH_SIZE = 50


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
        if not has_runtime(track_lengths.get(track_id)):
            track_lengths[track_id] = -1

    save_track_cache(track_lengths)
    pending_ids = [
        track_id for track_id in track_ids if not has_runtime(track_lengths[track_id])
    ]
    unavailable_ids: list[str] = []

    while pending_ids:
        batch = pending_ids[:BATCH_SIZE]
        pending_ids = pending_ids[BATCH_SIZE:]
        response = api_sp.API_request_tracks(batch)

        if not isinstance(response, dict) or not isinstance(response.get("tracks"), list):
            raise RuntimeError("Spotify returned an unexpected tracks response.")

        tracks = response["tracks"]
        if len(tracks) != len(batch):
            raise RuntimeError(
                f"Spotify returned {len(tracks)} tracks for a batch of {len(batch)} IDs."
            )

        for requested_id, track in zip(batch, tracks):
            if track is None:
                unavailable_ids.append(requested_id)
                continue
            if not isinstance(track, dict) or track.get("id") != requested_id:
                raise RuntimeError(
                    f"Spotify returned an invalid response for track {requested_id}."
                )

            duration_ms = track.get("duration_ms")
            if not has_runtime(duration_ms):
                raise RuntimeError(
                    f"Spotify returned an invalid duration for track {requested_id}."
                )
            track_lengths[requested_id] = duration_ms

        save_track_cache(track_lengths)

    if unavailable_ids:
        missing = ", ".join(unavailable_ids)
        raise RuntimeError(
            "Spotify did not return track details for these IDs; their cache values "
            f"remain -1: {missing}"
        )

    return track_lengths


if __name__ == "__main__":
    get_track_lengths()
