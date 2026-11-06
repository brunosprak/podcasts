#!/usr/bin/env python3
"""Synchronize configured YouTube channels into rolling podcast feeds."""

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
DEFAULT_EPISODE_LIMIT = 10
TARGET_AUDIO_BITRATE = "128k"
MAX_STORED_BITRATE = 140_000
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


def latest_entries(channel_id: str, episode_limit: int) -> list[dict]:
    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    request = Request(feed_url, headers={"User-Agent": "podcast-feed-sync/1.0"})
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
            if len(entries) == episode_limit:
                break
    if len(entries) != episode_limit:
        raise RuntimeError(
            f"Expected {episode_limit} RSS entries for {channel_id}, received {len(entries)}"
        )
    return entries


def summary(description: str, title: str) -> str:
    first_paragraph = description.strip().split("\n\n", 1)[0].replace("\n", " ")
    return (first_paragraph or title)[:800]


def ensure_media(entry: dict, media_dir: Path) -> None:
    video_id = entry["id"]
    audio = media_dir / f"{video_id}.mp3"
    image = media_dir / f"{video_id}.jpg"
    if audio.exists() and image.exists():
        return
    yt_dlp(
        "--no-playlist",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", TARGET_AUDIO_BITRATE,
        "--embed-metadata",
        "--write-thumbnail",
        "--convert-thumbnails", "jpg",
        "--output", str(media_dir / "%(id)s.%(ext)s"),
        entry["webpage_url"],
    )


def audio_bitrate(audio: Path) -> int:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=bit_rate",
            "-of", "default=noprint_wrappers=1:nokey=1", str(audio),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return round(float(result.stdout.strip()))


def normalize_audio(audio: Path) -> bool:
    if audio_bitrate(audio) <= MAX_STORED_BITRATE:
        return False
    temporary = audio.with_name(f"{audio.stem}.normalized.mp3")
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(audio),
            "-map", "0:a:0", "-map_metadata", "0", "-c:a", "libmp3lame",
            "-b:a", TARGET_AUDIO_BITRATE, str(temporary),
        ],
        cwd=ROOT,
        check=True,
    )
    temporary.replace(audio)
    return True


def audio_duration(audio: Path) -> int:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(audio),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return round(float(result.stdout.strip()))


def rotate_media(media_dir: Path, allowed_ids: set[str]) -> list[str]:
    removed = []
    for path in media_dir.iterdir():
        if path.name.startswith("artwork.") or path.suffix.lower() not in ROTATED_SUFFIXES:
            continue
        if path.stem not in allowed_ids:
            path.unlink()
            removed.append(path.name)
    return removed


def sync_podcast(podcast: dict) -> tuple[int, int, list[str]]:
    channel_id = podcast["youtube_channel_id"]
    episode_limit = int(podcast.get("episode_limit", DEFAULT_EPISODE_LIMIT))
    media_dir = ROOT / "podcasts" / podcast["slug"] / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    entries = latest_entries(channel_id, episode_limit)
    normalized = 0
    for entry in entries:
        ensure_media(entry, media_dir)
        normalized += normalize_audio(media_dir / f"{entry['id']}.mp3")
    allowed_ids = {entry["id"] for entry in entries}
    removed = rotate_media(media_dir, allowed_ids)
    podcast["episodes"] = [
        {
            "id": entry["id"],
            "title": entry["title"],
            "description": summary(entry["description"], entry["title"]),
            "published": entry["published"],
            "duration_seconds": audio_duration(media_dir / f"{entry['id']}.mp3"),
            "audio": f"podcasts/{podcast['slug']}/media/{entry['id']}.mp3",
            "image": f"podcasts/{podcast['slug']}/media/{entry['id']}.jpg",
            "source_url": entry["webpage_url"],
        }
        for entry in entries
    ]
    return len(entries), normalized, removed


def main() -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    synchronized = 0
    for podcast in data["podcasts"]:
        if "youtube_channel_id" not in podcast:
            continue
        count, normalized, removed = sync_podcast(podcast)
        synchronized += 1
        print(f"{podcast['title']}: synchronized {count} episodes.")
        if normalized:
            print(f"{podcast['title']}: normalized {normalized} audio file(s).")
        if removed:
            print(f"{podcast['title']}: removed rotated media: " + ", ".join(removed))
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, "tools/build_site.py"], cwd=ROOT, check=True)
    print(f"Synchronized {synchronized} podcast(s).")


if __name__ == "__main__":
    main()
