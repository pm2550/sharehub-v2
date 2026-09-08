"""One-shot script: generate thumbnails for posts that don't have one.

For each image without a thumbnail: download from PM Drive → generate_thumbnails → update DB.
For each video without a thumbnail: download from PM Drive → ffmpeg extract frame → generate_thumbnails → update DB.
Files (.zip/.exe) are skipped (no preview possible).

Run on server:
  cd /data/sharehub && .venv/bin/python backfill_thumbnails.py
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Load .env into os.environ so pmdrive picks up creds
ENV_FILE = Path("/data/sharehub/.env")
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

sys.path.insert(0, "/data/sharehub")

import httpx  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.services import pmdrive  # noqa: E402
from app.services.media import generate_thumbnails  # noqa: E402

settings = get_settings()
MEDIA_DIR = Path(settings.MEDIA_DIR)
DB_PATH = Path(settings.DATABASE_PATH) if hasattr(settings, "DATABASE_PATH") else Path("/data/sharehub/data/app.db")

# Refresh pmdrive module-level creds in case it imported before env was loaded
pmdrive.EMAIL = settings.PMDRIVE_EMAIL
pmdrive.PASSWORD = settings.PMDRIVE_PASSWORD


async def download_to_tmp(uri: str, tmp_path: Path) -> int:
    """Download the original file from PM Drive to tmp_path. Returns bytes."""
    url = await pmdrive.get_source_url(uri)
    total = 0
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as cli:
        async with cli.stream("GET", url) as r:
            r.raise_for_status()
            with tmp_path.open("wb") as f:
                async for chunk in r.aiter_bytes(1024 * 256):
                    f.write(chunk)
                    total += len(chunk)
    return total


def extract_video_frame(video_path: Path, frame_path: Path) -> None:
    """Use ffmpeg to grab a single still frame from the video, ~1 second in."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH")
    cmd = [
        ffmpeg, "-y",
        "-ss", "1",               # seek 1s in (skip black intros)
        "-i", str(video_path),
        "-frames:v", "1",         # one frame
        "-vf", "scale=1280:-2",   # cap width so full-quality encode is snappy
        "-q:v", "2",
        str(frame_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0 or not frame_path.exists() or frame_path.stat().st_size == 0:
        # Retry at 0s in case the video is shorter than 1s
        cmd_retry = [ffmpeg, "-y", "-i", str(video_path), "-frames:v", "1",
                     "-vf", "scale=1280:-2", "-q:v", "2", str(frame_path)]
        proc = subprocess.run(cmd_retry, capture_output=True, text=True, timeout=60)
        if proc.returncode != 0 or not frame_path.exists():
            raise RuntimeError(f"ffmpeg failed: {proc.stderr[-500:]}")


async def process_row(conn: sqlite3.Connection, row: sqlite3.Row, dry_run: bool) -> tuple[str, str]:
    pid = row["id"]
    mtype = row["media_type"]
    uri = row["pmdrive_uri"]
    if not uri:
        return ("skip", f"id={pid} no pmdrive_uri")

    if mtype not in ("image", "video"):
        return ("skip", f"id={pid} media_type={mtype}")

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"backfill_{pid}_") as tdir:
        td = Path(tdir)
        orig = td / (f"orig{Path(row['filename']).suffix or ''}")
        t0 = time.time()
        size = await download_to_tmp(uri, orig)
        dl_ms = (time.time() - t0) * 1000

        if mtype == "image":
            thumb_src = orig
        else:
            # Extract a frame first
            frame_path = td / "frame.jpg"
            t1 = time.time()
            extract_video_frame(orig, frame_path)
            ff_ms = (time.time() - t1) * 1000
            thumb_src = frame_path

        t2 = time.time()
        # generate_thumbnails writes into MEDIA_DIR/thumbnails/ directly
        thumbs = generate_thumbnails(str(thumb_src), str(MEDIA_DIR))
        th_ms = (time.time() - t2) * 1000

        if not thumbs or "md" not in thumbs:
            return ("fail", f"id={pid} generate_thumbnails returned empty: {thumbs}")

        thumb_rel = thumbs["md"]  # e.g. thumbnails/<uuid>_md.webp
        msg = f"id={pid} {mtype} size={size/1024:.0f}KB dl={dl_ms:.0f}ms"
        if mtype == "video":
            msg += f" ff={ff_ms:.0f}ms"
        msg += f" thumb={th_ms:.0f}ms → {thumb_rel}"

        if dry_run:
            return ("dry", msg + " [dry-run, DB not updated]")

        # Remove the old thumbnail (both sm + md variants) if present
        old = row["old_thumb"] if "old_thumb" in row.keys() else None
        if old:
            try:
                old_md = MEDIA_DIR / old
                if old_md.exists():
                    old_md.unlink()
                stem = Path(old).name
                if stem.endswith("_md.webp"):
                    old_sm = old_md.parent / (stem[:-len("_md.webp")] + "_sm.webp")
                    if old_sm.exists():
                        old_sm.unlink()
            except Exception as e:
                print(f"  warn: old thumb cleanup failed: {e}")

        conn.execute("UPDATE posts SET thumbnail_path = ? WHERE id = ?", (thumb_rel, pid))
        conn.commit()
        return ("ok", msg)


async def main():
    dry_run = "--dry-run" in sys.argv
    force_all = "--all" in sys.argv
    limit_arg = None
    for i, a in enumerate(sys.argv):
        if a == "--limit" and i + 1 < len(sys.argv):
            limit_arg = int(sys.argv[i + 1])

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Only image posts need thumbnails (videos use previews instead).
    if force_all:
        q = """SELECT id, media_type, filename, pmdrive_uri, thumbnail_path AS old_thumb
               FROM posts
               WHERE media_type = 'image'
                 AND pmdrive_uri IS NOT NULL AND pmdrive_uri != ''
               ORDER BY id"""
    else:
        q = """SELECT id, media_type, filename, pmdrive_uri, thumbnail_path AS old_thumb
               FROM posts
               WHERE (thumbnail_path IS NULL OR thumbnail_path = '')
                 AND pmdrive_uri IS NOT NULL AND pmdrive_uri != ''
                 AND media_type = 'image'
               ORDER BY id"""
    rows = conn.execute(q).fetchall()
    if limit_arg:
        rows = rows[:limit_arg]

    print(f"Targets: {len(rows)} post(s). dry_run={dry_run} force_all={force_all}")
    print(f"MEDIA_DIR: {MEDIA_DIR}")
    print(f"DB: {DB_PATH}")
    print("-" * 60)

    stats = {"ok": 0, "dry": 0, "fail": 0, "skip": 0}
    for row in rows:
        try:
            status, msg = await process_row(conn, row, dry_run)
        except Exception as e:
            status, msg = "fail", f"id={row['id']} exception: {type(e).__name__}: {e}"
        stats[status] = stats.get(status, 0) + 1
        prefix = {"ok": "[+]", "dry": "[=]", "fail": "[!]", "skip": "[-]"}.get(status, "[?]")
        print(f"{prefix} {msg}")

    print("-" * 60)
    print(f"Summary: {stats}")
    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
