"""Publishes a reel through Instagram's official Graph API (resumable upload).

Needs an Instagram professional account, its numeric ID and an access token with
content-publishing permission. Set them in .env. No password is used anywhere.

    python post_instagram.py --check              # confirm the token and account work
    python post_instagram.py reel.mp4 "caption"   # post one file
"""
import os
import sys
import time
from pathlib import Path

import requests

import config


class InstagramError(RuntimeError):
    pass


def _base() -> str:
    return f"{config.IG_GRAPH_HOST.rstrip('/')}/{config.IG_API_VERSION}"


def _require_credentials() -> None:
    if not config.IG_USER_ID or not config.IG_ACCESS_TOKEN:
        raise InstagramError("IG_USER_ID and IG_ACCESS_TOKEN must be set in the .env file.")


def _json(response) -> dict:
    try:
        data = response.json()
    except ValueError:
        raise InstagramError(f"Unexpected reply (HTTP {response.status_code}): {response.text[:300]}")
    if "error" in data:
        err = data["error"]
        message = err.get("message", err) if isinstance(err, dict) else err
        raise InstagramError(f"Instagram API error: {message}")
    return data


def check_account() -> dict:
    _require_credentials()
    r = requests.get(
        f"{_base()}/{config.IG_USER_ID}",
        params={"fields": "username", "access_token": config.IG_ACCESS_TOKEN},
        timeout=30,
    )
    return _json(r)


def post_reel(video_path: Path, caption: str, poll_seconds: int = 10, max_wait: int = 600,
              thumb_offset_ms=None) -> str:
    """Uploads and publishes the reel. Returns the published media ID."""
    _require_credentials()
    video_path = Path(video_path)
    if not video_path.exists():
        raise InstagramError(f"Video not found: {video_path}")

    # 1. Create an upload container.
    data = {
        "media_type": "REELS",
        "upload_type": "resumable",
        "caption": caption,
        "share_to_feed": "true",
        "access_token": config.IG_ACCESS_TOKEN,
    }
    if thumb_offset_ms is not None:
        data["thumb_offset"] = str(int(thumb_offset_ms))
    r = requests.post(
        f"{_base()}/{config.IG_USER_ID}/media",
        data=data,
        timeout=60,
    )
    container = _json(r)
    container_id = container.get("id")
    upload_uri = container.get("uri")
    if not container_id or not upload_uri:
        raise InstagramError(f"No upload address returned: {container}")

    # 2. Send the video bytes.
    size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        r = requests.post(
            upload_uri,
            headers={
                "Authorization": f"OAuth {config.IG_ACCESS_TOKEN}",
                "offset": "0",
                "file_size": str(size),
            },
            data=f,
            timeout=600,
        )
    _json(r)

    # 3. Wait for Instagram to finish processing.
    waited = 0
    while True:
        r = requests.get(
            f"{_base()}/{container_id}",
            params={"fields": "status_code,status", "access_token": config.IG_ACCESS_TOKEN},
            timeout=30,
        )
        status = _json(r)
        code = status.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise InstagramError(f"Instagram could not process the video: {status}")
        if waited >= max_wait:
            raise InstagramError("Timed out waiting for Instagram to process the video.")
        time.sleep(poll_seconds)
        waited += poll_seconds

    # 4. Publish.
    r = requests.post(
        f"{_base()}/{config.IG_USER_ID}/media_publish",
        data={"creation_id": container_id, "access_token": config.IG_ACCESS_TOKEN},
        timeout=60,
    )
    return _json(r)["id"]


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--check":
        print("Connected to Instagram account:", check_account().get("username"))
    elif len(sys.argv) == 3:
        print("Published media ID:", post_reel(Path(sys.argv[1]), sys.argv[2]))
    else:
        print(__doc__)
