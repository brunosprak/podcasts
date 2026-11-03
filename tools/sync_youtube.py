#!/usr/bin/env python3
"""Synchronize a YouTube channel into a rolling five-episode podcast feed."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data.json"
MEDIA_DIR = ROOT / "podcasts" / "academic-agent" / "media"
CHANNEL_URL = "https://www.youtube.com/@academicagent/videos"
EPISODE_LIMIT = 5
ROTATED_SUFFIXES = {".mp3", ".jpg", ".webm", ".webp"}


def yt_dlp(*args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "yt_dlp", *args]
    return subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=capture,
    )


def latest_entries() -> list[dict]:
    result = yt_dlp(
        "--quiet",
        "--ignore-errors",
        "--playlist-end",
        str(EPISODE_LIMIT),
        "--dump-json",
        CHANNEL_URL,
        capture=True,
    )
    entries = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    if len(entries) != EPISODE_LIMIT:
        raise RuntimeError(f"Expected {EPISODE_LIMIT} videos, received {len(entries)}")
    return entries


def summary(description: str | None, title: str) -> str:
    if not description:
        return title
    first_paragraph = description.strip().split("\n\n", 1)[0].replace("\n", " ")
    return first_paragraph[:800]


def published_at(entry: dict) -> str:
    date = entry.get("upload_date")
    if date:
        parsed = datetime.strptime(date, "%Y%m%d").replace(tzinfo=timezone.utc)
    else:
        parsed = datetime.fromtimestamp(entry["timestamp"], tz=timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z")


def ensure_media(entry: dict) -> None:
    video_id = entry["id"]
    audio = MEDIA_DIR / f"{video_id}.mp3"
    image = MEDIA_DIR / f"{video_id}.jpg"
    if audio.exists() and image.exists():
        return
    yt_dlp(
        "--no-playlist",
        "--extract-audio",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",
        "--embed-metadata",
        "--write-thumbnail",
        "--convert-thumbnails",
        "jpg",
        "--output",
        str(MEDIA_DIR / "%(id)s.%(ext)s"),
        entry["webpage_url"],
    )


def rotate_media(allowed_ids: set[str]) -> list[str]:
    removed = []
    for path in MEDIA_DIR.iterdir():
        if path.suffix.lower() not in ROTATED_SUFFIXES or path.name == "artwork.png":
            continue
        if path.stem not in allowed_ids:
            path.unlink()
            removed.append(path.name)
    return removed


def update_catalog(entries: list[dict]) -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    podcast = next(item for item in data["podcasts"] if item["slug"] == "academic-agent")
    podcast["episodes"] = [
        {
            "id": entry["id"],
            "title": entry["title"],
            "description": summary(entry.get("description"), entry["title"]),
            "published": published_at(entry),
            "duration_seconds": round(entry["duration"]),
            "audio": f"podcasts/academic-agent/media/{entry['id']}.mp3",
            "image": f"podcasts/academic-agent/media/{entry['id']}.jpg",
            "source_url": entry["webpage_url"],
        }
        for entry in entries
    ]
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    entries = latest_entries()
    for entry in entries:
        ensure_media(entry)
    allowed_ids = {entry["id"] for entry in entries}
    removed = rotate_media(allowed_ids)
    update_catalog(entries)
    subprocess.run([sys.executable, "tools/build_site.py"], cwd=ROOT, check=True)
    print(f"Synchronized {len(entries)} episodes.")
    if removed:
        print("Removed rotated media: " + ", ".join(removed))


if __name__ == "__main__":
    main()
