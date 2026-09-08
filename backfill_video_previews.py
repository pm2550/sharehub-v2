"""One-shot + incremental: generate low-bitrate MP4 previews for video posts.

For each video without preview_path:
  - Download original from PM Drive to /tmp
  - ffmpeg: 4s, 360p, ~250kbps H.264, no audio, faststart
  - Move to /data/sharehub/data/media/previews/<uuid>.mp4
  - UPDATE posts.preview_path

Run:
  cd /data/sharehub && .venv/bin/python backfill_video_previews.py
Options: --dry-run, --limit N, --force (re-generate even if preview_path set)
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
import uuid
from pathlib import Path

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

settings = get_settings()
MEDIA_DIR = Path(settings.MEDIA_DIR)
DB_PATH = Path(getattr(settings, "DATABASE_PATH", "/data/sharehub/data/app.db"))

pmdrive.EMAIL = settings.PMDRIVE_EMAIL
pmdrive.PASSWORD = settings.PMDRIVE_PASSWORD


async def download_to_tmp(uri: str, tmp_path: Path) -> int:
    url = await pmdrive.get_source_url(uri)
    total = 0
    async with httpx.AsyncClient(timeout=300, follow_redirects=True) as cli:
        async with cli.stream("GET", url) as r:
            r.raise_for_status()
            with tmp_path.open("wb") as f:
                async for chunk in r.aiter_bytes(1024 * 256):
                    f.write(chunk)
                    total += len(chunk)
    return total


def generate_preview(src: Path, out: Path) -> None:
    """Generate preview via media.generate_video_preview (centralised quality settings).

    media.generate_video_preview writes to MEDIA_DIR/previews/<uuid>.mp4 with its own
    UUID, but we want a specific output path here. So we invoke ffmpeg directly with
    the same params used by media.py so quality stays in sync.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")
    cmd = [
        ffmpeg, "-y",
        "-i", str(src),
        "-t", "4",
        # Scale long edge to <=1280, keep aspect, even dims. Horizontal → 720p; vertical → 1280 tall (~720w).
        "-vf", "scale='if(gt(iw,ih),min(1280,iw),-2)':'if(gt(iw,ih),-2,min(1280,ih))'",
        "-c:v", "libx264",
        "-crf", "22",
        "-preset", "medium",
        "-profile:v", "high",
        "-level", "4.1",
        "-movflags", "+faststart",
        "-an",
        "-pix_fmt", "yuv420p",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr[-500:]}")


async def process_row(conn: sqlite3.Connection, row: sqlite3.Row, dry_run: bool) -> tuple[str, str]:
    pid = row["id"]
    uri = row["pmdrive_uri"]
    if not uri:
        return ("skip", f"id={pid} no pmdrive_uri")

    previews_dir = MEDIA_DIR / "previews"
    previews_dir.mkdir(parents=True, exist_ok=True)

    old_preview = row["preview_path"] if "preview_path" in row.keys() else None

    with tempfile.TemporaryDirectory(prefix=f"preview_{pid}_") as tdir:
        td = Path(tdir)
        orig = td / f"orig{Path(row['filename']).suffix or '.mp4'}"
        t0 = time.time()
        size = await download_to_tmp(uri, orig)
        dl_ms = (time.time() - t0) * 1000

        preview_name = f"{uuid.uuid4().hex}.mp4"
        tmp_out = td / preview_name
        t1 = time.time()
        generate_preview(orig, tmp_out)
        ff_ms = (time.time() - t1) * 1000
        out_size = tmp_out.stat().st_size

        final = previews_dir / preview_name
        msg = f"id={pid} orig={size/1024:.0f}KB dl={dl_ms:.0f}ms ff={ff_ms:.0f}ms preview={out_size/1024:.0f}KB"

        if dry_run:
            return ("dry", msg + " [dry-run]")

        shutil.move(str(tmp_out), str(final))
        rel = f"previews/{preview_name}"

        # Remove old preview file (if regenerating)
        if old_preview and old_preview != rel:
            try:
                op = MEDIA_DIR / old_preview
                if op.exists():
                    op.unlink()
            except Exception as e:
                print(f"  warn: old preview cleanup failed: {e}")

        conn.execute("UPDATE posts SET preview_path = ? WHERE id = ?", (rel, pid))
        conn.commit()
        return ("ok", msg + f" → {rel}")


async def main():
    dry_run = "--dry-run" in sys.argv
    force = "--force" in sys.argv
    limit_arg = None
    for i, a in enumerate(sys.argv):
        if a == "--limit" and i + 1 < len(sys.argv):
            limit_arg = int(sys.argv[i + 1])

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if force:
        q = """SELECT id, filename, pmdrive_uri, preview_path FROM posts
               WHERE media_type='video' AND pmdrive_uri IS NOT NULL AND pmdrive_uri != ''
               ORDER BY id"""
    else:
        q = """SELECT id, filename, pmdrive_uri, preview_path FROM posts
               WHERE media_type='video' AND pmdrive_uri IS NOT NULL AND pmdrive_uri != ''
                 AND (preview_path IS NULL OR preview_path = '')
               ORDER BY id"""
    rows = conn.execute(q).fetchall()
    if limit_arg:
        rows = rows[:limit_arg]

    print(f"Targets: {len(rows)} video(s). dry_run={dry_run} force={force}")
    print(f"MEDIA_DIR: {MEDIA_DIR}")
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
