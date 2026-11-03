#!/usr/bin/env python3
"""Synchronize a YouTube channel into a rolling five-episode podcast feed."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data.json"
MEDIA_DIR = ROOT / "podcasts" / "academic-agent" / "media"
CHANNEL_ID = "UCyawG3aTE7RmNQcFQskDWcw"
FEED_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
EPISODE_LIMIT = 5
ROTATED_SUFFIXES = {".mp3", ".jpg", ".webm", ".webp"}
NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}


def yt_dlp_base() -> list[str]:
    command = [sys.executable, "-m", "yt_dlp", "--js-runtimes", "node"]
    cookies_file = os.environ.get("YOUTUBE_COOKIES_FILE")
    if cookies_file and Path(cookies_file).is_file() and Path(cookies_file).stat().st_size:
        command.extend(["--cookies", cookies_file])
    return command


def yt_dlp(*args: str) -> None:
    subprocess.run([*yt_dlp_base(), *args], cwd=ROOT, check=True)


def is_finalized(video_id: str) -> bool:
    result = subprocess.run(
        [
            *yt_dlp_base(), "--quiet", "--skip-download",
            "--print", "%(live_status)s",
            f"https://www.youtube.com/watch?v={video_id}",
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"Could not inspect YouTube video {video_id}")
    statuses = result.stdout.strip().splitlines()
    return bool(statuses) and statuses[-1] in {"not_live", "was_live"}


def latest_entries() -> list[dict]:
    request = Request(FEED_URL, headers={"User-Agent": "podcast-feed-sync/1.0"})
    with urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())
    entries = []
    for item in root.findall("atom:entry", NAMESPACES):
        video_id = item.findtext("yt:videoId", namespaces=NAMESPACES)
        title = item.findtext("atom:title", namespaces=NAMESPACES)
        published = item.findtext("atom:published", namespaces=NAMESPACES)
        description = item.findtext("media:group/media:description", namespaces=NAMESPACES)
        if video_id and title and published and is_finalized(video_id):
            entries.append({
                "id": video_id,
                "title": title,
                "published": published,
                "description": description or title,
                "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
            })
            if len(entries) == EPISODE_LIMIT:
                break
    if len(entries) != EPISODE_LIMIT:
        raise RuntimeError(f"Expected {EPISODE_LIMIT} RSS entries, received {len(entries)}")
    return entries


def summary(description: str, title: str) -> str:
    first_paragraph = description.strip().split("\n\n", 1)[0].replace("\n", " ")
    return (first_paragraph or title)[:800]


def ensure_media(entry: dict) -> None:
    video_id = entry["id"]
    audio = MEDIA_DIR / f"{video_id}.mp3"
    image = MEDIA_DIR / f"{video_id}.jpg"
    if audio.exists() and image.exists():
        return
    yt_dlp(
        "--no-playlist",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--embed-metadata",
        "--write-thumbnail",
        "--convert-thumbnails", "jpg",
        "--output", str(MEDIA_DIR / "%(id)s.%(ext)s"),
        entry["webpage_url"],
    )


def audio_duration(video_id: str) -> int:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(MEDIA_DIR / f"{video_id}.mp3"),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return round(float(result.stdout.strip()))


def rotate_media(allowed_ids: set[str]) -> list[str]:
    removed = []
    for path in MEDIA_DIR.iterdir():
        if path.suffix.lower() not in ROTATED_SUFFIXES:
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
            "description": summary(entry["description"], entry["title"]),
            "published": entry["published"],
            "duration_seconds": audio_duration(entry["id"]),
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
