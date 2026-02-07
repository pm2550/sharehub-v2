import base64
import hashlib
import hmac
import os
import secrets
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlparse

import requests
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

APP_DIR = Path("/data/sharehub")
DB_PATH = APP_DIR / "data" / "app.db"
MEDIA_DIR = APP_DIR / "data" / "media"
STATIC_DIR = APP_DIR / "static"
TEMPLATES_DIR = APP_DIR / "templates"

A1111_URL = os.getenv("A1111_URL", "http://127.0.0.1:8188")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-me")
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-session-secret")
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "2592000"))  # 30 days
SITE_TITLE = os.getenv("SITE_TITLE", "ShareHub")

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
ALLOWED_VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v"}
FEED_PAGE_SIZE = 18
USER_PAGE_SIZE = 18
ME_PAGE_SIZE = 8
AI_DEFAULT_JOB_SECONDS = int(os.getenv("AI_DEFAULT_JOB_SECONDS", "50"))
AI_JOB_HISTORY = int(os.getenv("AI_JOB_HISTORY", "30"))

_worker_started = False
_worker_lock = threading.Lock()

app = FastAPI(title="ShareHub")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=False,
    max_age=SESSION_MAX_AGE,
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def safe_next(target: str) -> str:
    if not target or not target.startswith("/") or target.startswith("//"):
        return "/"
    return target


def safe_back(request: Request, default_path: str) -> str:
    referer = (request.headers.get("referer") or "").strip()
    if not referer:
        return default_path
    try:
        parsed = urlparse(referer)
    except Exception:
        return default_path

    # Accept only same-host referer to avoid open redirects.
    if parsed.netloc and parsed.hostname != request.url.hostname:
        return default_path

    path = parsed.path or "/"
    if path.startswith("/post/") or path in ("/login", "/register"):
        return default_path

    query = f"?{parsed.query}" if parsed.query else ""
    fragment = f"#{parsed.fragment}" if parsed.fragment else ""
    target = f"{path}{query}{fragment}"
    return safe_next(target)


def transcode_video_compatible(input_path: Path, output_path: Path) -> None:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise HTTPException(status_code=500, detail="ffmpeg is not installed on server")

    tmp_out = output_path.with_suffix(".tmp.mp4")
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(tmp_out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        if tmp_out.exists():
            tmp_out.unlink()
        err = (proc.stderr or proc.stdout or "ffmpeg failed").strip()
        raise HTTPException(status_code=400, detail=f"视频编码不兼容，转码失败: {err[-500:]}")

    tmp_out.replace(output_path)


def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def hash_password(password: str, salt: Optional[str] = None) -> str:
    raw_salt = bytes.fromhex(salt) if salt else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), raw_salt, 120_000)
    return f"{raw_salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    candidate = hash_password(password, salt)
    return hmac.compare_digest(candidate, stored)


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    with db_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT,
                bio TEXT,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                media_type TEXT NOT NULL,
                filename TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'upload',
                prompt TEXT,
                likes INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_id INTEGER,
                author TEXT,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS post_likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(post_id, user_id),
                FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS ai_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                prompt TEXT NOT NULL,
                negative_prompt TEXT,
                steps INTEGER NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                started_unix INTEGER,
                finished_unix INTEGER,
                result_post_id INTEGER,
                error TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(result_post_id) REFERENCES posts(id)
            );
            """
        )

        post_cols = _columns(conn, "posts")
        if "user_id" not in post_cols:
            conn.execute("ALTER TABLE posts ADD COLUMN user_id INTEGER")

        user_cols = _columns(conn, "users")
        if "is_admin" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        if "display_name" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT")
        if "bio" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN bio TEXT")
        conn.execute("UPDATE users SET display_name = username WHERE display_name IS NULL OR display_name = ''")

        comment_cols = _columns(conn, "comments")
        if "user_id" not in comment_cols:
            conn.execute("ALTER TABLE comments ADD COLUMN user_id INTEGER")
        if "author" not in comment_cols:
            conn.execute("ALTER TABLE comments ADD COLUMN author TEXT")

        ai_cols = _columns(conn, "ai_jobs")
        if "started_unix" not in ai_cols:
            conn.execute("ALTER TABLE ai_jobs ADD COLUMN started_unix INTEGER")
        if "finished_unix" not in ai_cols:
            conn.execute("ALTER TABLE ai_jobs ADD COLUMN finished_unix INTEGER")
        if "result_post_id" not in ai_cols:
            conn.execute("ALTER TABLE ai_jobs ADD COLUMN result_post_id INTEGER")
        if "error" not in ai_cols:
            conn.execute("ALTER TABLE ai_jobs ADD COLUMN error TEXT")

        # If service restarted while running a job, return it to pending.
        conn.execute("UPDATE ai_jobs SET status='pending' WHERE status='running'")


def current_user(request: Request):
    uid = request.session.get("uid")
    if not uid:
        return None

    with db_conn() as conn:
        user = conn.execute(
            "SELECT id, username, display_name, bio, is_admin, created_at FROM users WHERE id = ?",
            (uid,),
        ).fetchone()

    if not user:
        request.session.pop("uid", None)
        return None
    return user


def require_user(request: Request, next_path: str):
    user = current_user(request)
    if user:
        return user, None
    return None, RedirectResponse(url=f"/login?next={quote(next_path, safe='/?=&')}", status_code=303)


def render(request: Request, template: str, context: dict):
    base = {
        "request": request,
        "site_title": SITE_TITLE,
        "current_user": current_user(request),
    }
    base.update(context)
    return templates.TemplateResponse(template, base)


def query_posts(
    where_sql: str = "",
    params: tuple = (),
    limit: Optional[int] = None,
    offset: int = 0,
):
    sql = (
        """
        SELECT p.id, p.user_id, p.title, p.description, p.media_type, p.filename, p.source, p.prompt, p.likes, p.created_at,
               COALESCE(u.display_name, u.username, 'legacy') AS author,
               COALESCE(u.username, 'legacy') AS author_username
        FROM posts p
        LEFT JOIN users u ON u.id = p.user_id
        """
    )
    if where_sql:
        sql += f" WHERE {where_sql}"
    sql += " ORDER BY p.id DESC"
    if limit is not None:
        sql += f" LIMIT {int(limit)} OFFSET {max(0, int(offset))}"

    with db_conn() as conn:
        return conn.execute(sql, params).fetchall()


def count_posts(where_sql: str = "", params: tuple = ()) -> int:
    sql = "SELECT COUNT(*) FROM posts p LEFT JOIN users u ON u.id = p.user_id"
    if where_sql:
        sql += f" WHERE {where_sql}"
    with db_conn() as conn:
        return int(conn.execute(sql, params).fetchone()[0])


def build_pagination(page: int, total: int, page_size: int) -> dict:
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = 0 if total == 0 else (page - 1) * page_size + 1
    end = min(total, page * page_size)
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1,
        "next_page": page + 1,
        "start": start,
        "end": end,
    }


def now_unix() -> int:
    return int(time.time())


def seconds_to_text(seconds: int) -> str:
    if seconds <= 0:
        return "即将完成"
    if seconds < 60:
        return f"约 {seconds} 秒"
    mins, secs = divmod(seconds, 60)
    if mins < 60:
        return f"约 {mins} 分 {secs} 秒"
    hours, mins = divmod(mins, 60)
    return f"约 {hours} 小时 {mins} 分"


def average_job_seconds() -> int:
    with db_conn() as conn:
        rows = conn.execute(
            """
            SELECT started_unix, finished_unix
            FROM ai_jobs
            WHERE status='done'
              AND started_unix IS NOT NULL
              AND finished_unix IS NOT NULL
              AND finished_unix > started_unix
            ORDER BY id DESC
            LIMIT ?
            """,
            (AI_JOB_HISTORY,),
        ).fetchall()
    if not rows:
        return AI_DEFAULT_JOB_SECONDS
    total = sum(int(r["finished_unix"]) - int(r["started_unix"]) for r in rows)
    avg = max(5, int(total / len(rows)))
    return avg


def queue_runtime_map(avg_seconds: int) -> dict[int, dict]:
    with db_conn() as conn:
        waiting = conn.execute(
            """
            SELECT id, status, started_unix
            FROM ai_jobs
            WHERE status IN ('running', 'pending')
            ORDER BY CASE status WHEN 'running' THEN 0 ELSE 1 END, id ASC
            """
        ).fetchall()

    mapping: dict[int, dict] = {}
    remaining = 0
    position = 0
    for row in waiting:
        job_id = int(row["id"])
        status = row["status"]
        if status == "running":
            started_unix = row["started_unix"] or now_unix()
            elapsed = max(0, now_unix() - int(started_unix))
            remaining = max(5, avg_seconds - elapsed)
            mapping[job_id] = {
                "position": 0,
                "eta_seconds": remaining,
                "eta_text": seconds_to_text(remaining),
            }
        else:
            position += 1
            remaining += avg_seconds
            mapping[job_id] = {
                "position": position,
                "eta_seconds": remaining,
                "eta_text": seconds_to_text(remaining),
            }
    return mapping


def list_jobs(limit: int = 30, only_user_id: Optional[int] = None) -> list[dict]:
    where = ""
    params: list = []
    if only_user_id is not None:
        where = "WHERE j.user_id = ?"
        params.append(only_user_id)
    params.append(limit)

    with db_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT j.id, j.user_id, j.prompt, j.negative_prompt, j.steps, j.width, j.height, j.status,
                   j.created_at, j.started_at, j.finished_at, j.error, j.result_post_id,
                   COALESCE(u.display_name, u.username, 'legacy') AS owner,
                   COALESCE(u.username, 'legacy') AS owner_username
            FROM ai_jobs j
            LEFT JOIN users u ON u.id = j.user_id
            {where}
            ORDER BY j.id DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()

    avg = average_job_seconds()
    queue_map = queue_runtime_map(avg)
    jobs: list[dict] = []
    for row in rows:
        item = dict(row)
        q = queue_map.get(item["id"], {})
        item["queue_position"] = q.get("position")
        item["eta_seconds"] = q.get("eta_seconds")
        item["eta_text"] = q.get("eta_text")
        jobs.append(item)
    return jobs


def process_one_ai_job() -> bool:
    with db_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        job = conn.execute(
            """
            SELECT id, user_id, prompt, negative_prompt, steps, width, height
            FROM ai_jobs
            WHERE status='pending'
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()
        if not job:
            conn.commit()
            return False
        started_at = now_iso()
        started_unix = now_unix()
        conn.execute(
            "UPDATE ai_jobs SET status='running', started_at=?, started_unix=? WHERE id=?",
            (started_at, started_unix, job["id"]),
        )
        conn.commit()

    payload = {
        "prompt": job["prompt"],
        "negative_prompt": job["negative_prompt"] or "",
        "steps": int(job["steps"]),
        "width": int(job["width"]),
        "height": int(job["height"]),
        "sampler_name": "Euler a",
    }

    try:
        resp = requests.post(f"{A1111_URL}/sdapi/v1/txt2img", json=payload, timeout=900)
        resp.raise_for_status()
        data = resp.json()
        images = data.get("images") or []
        if not images:
            raise RuntimeError("A1111 returned no images")

        b64 = images[0]
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        img_bytes = base64.b64decode(b64)
        filename = f"gen_{uuid.uuid4().hex}.png"
        (MEDIA_DIR / filename).write_bytes(img_bytes)

        finished_at = now_iso()
        finished_unix = now_unix()
        with db_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO posts(user_id, title, description, media_type, filename, source, prompt, created_at)
                VALUES (?, ?, ?, 'image', ?, 'ai', ?, ?)
                """,
                (
                    job["user_id"],
                    f"AI: {job['prompt'][:60]}",
                    "",
                    filename,
                    job["prompt"][:2000],
                    finished_at,
                ),
            )
            post_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute(
                """
                UPDATE ai_jobs
                SET status='done', finished_at=?, finished_unix=?, result_post_id=?, error=NULL
                WHERE id=?
                """,
                (finished_at, finished_unix, post_id, job["id"]),
            )
            conn.commit()
    except Exception as exc:
        finished_at = now_iso()
        finished_unix = now_unix()
        with db_conn() as conn:
            conn.execute(
                """
                UPDATE ai_jobs
                SET status='failed', finished_at=?, finished_unix=?, error=?
                WHERE id=?
                """,
                (finished_at, finished_unix, str(exc)[:1500], job["id"]),
            )
    return True


def ai_worker_loop() -> None:
    while True:
        has_job = process_one_ai_job()
        time.sleep(1 if has_job else 2)


def start_worker_once() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        worker = threading.Thread(target=ai_worker_loop, name="sharehub-ai-worker", daemon=True)
        worker.start()
        _worker_started = True


@app.on_event("startup")
def startup() -> None:
    init_db()
    start_worker_once()


@app.get("/")
def home(request: Request):
    with db_conn() as conn:
        stats = {
            "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "posts": conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
            "images": conn.execute("SELECT COUNT(*) FROM posts WHERE media_type='image' AND source='upload'").fetchone()[0],
            "videos": conn.execute("SELECT COUNT(*) FROM posts WHERE media_type='video'").fetchone()[0],
            "ai": conn.execute("SELECT COUNT(*) FROM posts WHERE source='ai'").fetchone()[0],
        }

    recent_images = query_posts("p.media_type='image' AND p.source='upload'", limit=12)
    recent_videos = query_posts("p.media_type='video'", limit=12)
    recent_ai = query_posts("p.source='ai'", limit=12)

    return render(
        request,
        "home.html",
        {
            "active": "home",
            "stats": stats,
            "recent_images": recent_images,
            "recent_videos": recent_videos,
            "recent_ai": recent_ai,
        },
    )


@app.get("/images")
def images_page(request: Request, page: int = Query(1, ge=1)):
    where = "p.media_type='image' AND p.source='upload'"
    total = count_posts(where)
    pagination = build_pagination(page, total, FEED_PAGE_SIZE)
    posts = query_posts(where, limit=FEED_PAGE_SIZE, offset=(pagination["page"] - 1) * FEED_PAGE_SIZE)
    return render(
        request,
        "feed.html",
        {
            "active": "images",
            "page_title": "图片广场",
            "page_desc": "所有用户上传的图片",
            "posts": posts,
            "pagination": pagination,
            "page_path": "/images",
            "show_quick_upload": True,
        },
    )


@app.get("/videos")
def videos_page(request: Request, page: int = Query(1, ge=1)):
    where = "p.media_type='video'"
    total = count_posts(where)
    pagination = build_pagination(page, total, FEED_PAGE_SIZE)
    posts = query_posts(where, limit=FEED_PAGE_SIZE, offset=(pagination["page"] - 1) * FEED_PAGE_SIZE)
    return render(
        request,
        "feed.html",
        {
            "active": "videos",
            "page_title": "视频广场",
            "page_desc": "所有用户上传的视频",
            "posts": posts,
            "pagination": pagination,
            "page_path": "/videos",
        },
    )


@app.get("/ai")
def ai_page(request: Request, page: int = Query(1, ge=1), queued: int = Query(0, ge=0)):
    where = "p.source='ai'"
    total = count_posts(where)
    pagination = build_pagination(page, total, FEED_PAGE_SIZE)
    posts = query_posts(where, limit=FEED_PAGE_SIZE, offset=(pagination["page"] - 1) * FEED_PAGE_SIZE)
    user = current_user(request)
    queue_jobs = list_jobs(limit=30)
    active_queue_jobs = [j for j in queue_jobs if j["status"] in ("running", "pending")]
    my_queue_jobs = list_jobs(limit=20, only_user_id=user["id"]) if user else []
    avg_seconds = average_job_seconds()
    return render(
        request,
        "ai.html",
        {
            "active": "ai",
            "page_title": "AI 生图",
            "page_desc": "A1111 生成并发布的图片",
            "posts": posts,
            "pagination": pagination,
            "page_path": "/ai",
            "queue_jobs": queue_jobs,
            "active_queue_jobs": active_queue_jobs,
            "my_queue_jobs": my_queue_jobs,
            "avg_seconds": avg_seconds,
            "queued": queued,
        },
    )


@app.get("/user/{username}")
def user_page(username: str, request: Request, page: int = Query(1, ge=1)):
    with db_conn() as conn:
        user = conn.execute(
            "SELECT id, username, display_name, bio, created_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
    where = "p.user_id = ?"
    params = (user["id"],)
    total = count_posts(where, params)
    pagination = build_pagination(page, total, USER_PAGE_SIZE)
    posts = query_posts(
        where,
        params,
        limit=USER_PAGE_SIZE,
        offset=(pagination["page"] - 1) * USER_PAGE_SIZE,
    )

    return render(
        request,
        "user.html",
        {
            "active": "",
            "profile_user": user,
            "posts": posts,
            "pagination": pagination,
            "page_path": f"/user/{username}",
        },
    )


@app.get("/register")
def register_page(request: Request, next: str = "/"):
    if current_user(request):
        return RedirectResponse(url=safe_next(next), status_code=303)
    return render(request, "register.html", {"next": safe_next(next), "error": "", "active": ""})


@app.post("/register")
def register(request: Request, username: str = Form(...), password: str = Form(...), next: str = Form("/")):
    username = username.strip()
    if len(username) < 3 or len(username) > 32:
        return render(request, "register.html", {"next": safe_next(next), "error": "用户名长度需在 3-32", "active": ""})
    if len(password) < 6:
        return render(request, "register.html", {"next": safe_next(next), "error": "密码至少 6 位", "active": ""})

    with db_conn() as conn:
        exists = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        if exists:
            return render(request, "register.html", {"next": safe_next(next), "error": "用户名已存在", "active": ""})

        conn.execute(
            "INSERT INTO users(username, display_name, password_hash, is_admin, created_at) VALUES (?, ?, ?, 0, ?)",
            (username, username, hash_password(password), now_iso()),
        )
        user_id = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"]

    request.session["uid"] = user_id
    return RedirectResponse(url=safe_next(next), status_code=303)


@app.get("/login")
def login_page(request: Request, next: str = "/"):
    if current_user(request):
        return RedirectResponse(url=safe_next(next), status_code=303)
    return render(request, "login.html", {"next": safe_next(next), "error": "", "active": ""})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), next: str = Form("/")):
    with db_conn() as conn:
        user = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()

    if not user or not verify_password(password, user["password_hash"]):
        return render(request, "login.html", {"next": safe_next(next), "error": "用户名或密码错误", "active": ""})

    request.session["uid"] = user["id"]
    return RedirectResponse(url=safe_next(next), status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@app.get("/me")
def me_page(request: Request, page: int = Query(1, ge=1)):
    user, redirect = require_user(request, "/me")
    if redirect:
        return redirect

    with db_conn() as conn:
        total = int(conn.execute("SELECT COUNT(*) FROM posts WHERE user_id = ?", (user["id"],)).fetchone()[0])
        pagination = build_pagination(page, total, ME_PAGE_SIZE)
        my_posts = conn.execute(
            """
            SELECT p.id, p.title, p.description, p.media_type, p.filename, p.source, p.likes, p.created_at
            FROM posts p
            WHERE p.user_id = ?
            ORDER BY p.id DESC
            LIMIT ? OFFSET ?
            """,
            (user["id"], ME_PAGE_SIZE, (pagination["page"] - 1) * ME_PAGE_SIZE),
        ).fetchall()
    my_jobs = list_jobs(limit=30, only_user_id=user["id"])
    queue_active = [j for j in my_jobs if j["status"] in ("pending", "running")]

    return render(
        request,
        "me.html",
        {
            "active": "me",
            "my_posts": my_posts,
            "my_jobs": my_jobs,
            "queue_active_count": len(queue_active),
            "pagination": pagination,
            "profile_msg": "",
            "pwd_msg": "",
        },
    )


@app.post("/me/profile")
def update_profile(request: Request, display_name: str = Form(...), bio: str = Form("")):
    user, redirect = require_user(request, "/me")
    if redirect:
        return redirect

    name = display_name.strip()
    if len(name) < 2 or len(name) > 32:
        raise HTTPException(status_code=400, detail="昵称长度需在 2-32")

    with db_conn() as conn:
        conn.execute("UPDATE users SET display_name = ?, bio = ? WHERE id = ?", (name, bio.strip()[:500], user["id"]))

    return RedirectResponse(url="/me", status_code=303)


@app.post("/me/password")
def update_password(request: Request, old_password: str = Form(...), new_password: str = Form(...)):
    user, redirect = require_user(request, "/me")
    if redirect:
        return redirect

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")

    with db_conn() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
        if not row or not verify_password(old_password, row["password_hash"]):
            raise HTTPException(status_code=400, detail="旧密码错误")
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_password), user["id"]))

    return RedirectResponse(url="/me", status_code=303)


@app.post("/post/{post_id}/edit")
def edit_post(request: Request, post_id: int, title: str = Form(...), description: str = Form("")):
    user, redirect = require_user(request, f"/post/{post_id}")
    if redirect:
        return redirect

    with db_conn() as conn:
        post = conn.execute("SELECT user_id FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        if post["user_id"] != user["id"] and not user["is_admin"]:
            raise HTTPException(status_code=403, detail="Not allowed")

        conn.execute(
            "UPDATE posts SET title = ?, description = ? WHERE id = ?",
            (title.strip()[:120] or "Untitled", description.strip()[:1000], post_id),
        )

    return RedirectResponse(url="/me", status_code=303)


@app.get("/post/{post_id}")
def post_detail(post_id: int, request: Request):
    user = current_user(request)
    with db_conn() as conn:
        post = conn.execute(
            """
            SELECT p.*, COALESCE(u.display_name, u.username, 'legacy') AS author,
                   COALESCE(u.username, 'legacy') AS author_username
            FROM posts p
            LEFT JOIN users u ON u.id = p.user_id
            WHERE p.id = ?
            """,
            (post_id,),
        ).fetchone()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        comments = conn.execute(
            """
            SELECT COALESCE(u.display_name, u.username, c.author, 'legacy') AS author,
                   COALESCE(u.username, 'legacy') AS author_username,
                   c.content,
                   c.created_at
            FROM comments c
            LEFT JOIN users u ON u.id = c.user_id
            WHERE c.post_id = ?
            ORDER BY c.id DESC
            """,
            (post_id,),
        ).fetchall()

        liked = 0
        if user:
            row = conn.execute(
                "SELECT 1 FROM post_likes WHERE post_id = ? AND user_id = ?",
                (post_id, user["id"]),
            ).fetchone()
            liked = 1 if row else 0

    is_owner = bool(user and post["user_id"] and user["id"] == post["user_id"])
    is_admin = bool(user and user["is_admin"])
    default_back = "/images"
    if post["source"] == "ai":
        default_back = "/ai"
    elif post["media_type"] == "video":
        default_back = "/videos"
    back_url = safe_back(request, default_back)
    return render(
        request,
        "post.html",
        {
            "active": "",
            "post": post,
            "comments": comments,
            "is_owner": is_owner,
            "is_admin": is_admin,
            "liked": liked,
            "back_url": back_url,
        },
    )


@app.get("/media/{filename}")
def media_file(filename: str):
    safe_name = os.path.basename(filename)
    file_path = MEDIA_DIR / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


@app.post("/upload")
async def upload(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    next: str = Form("/me"),
    media: UploadFile = File(...),
):
    user, redirect = require_user(request, "/me")
    if redirect:
        return redirect

    ext = Path(media.filename or "").suffix.lower()
    ctype = (media.content_type or "").lower()

    if ext in ALLOWED_IMAGE_EXT or ctype.startswith("image/"):
        media_type = "image"
    elif ext in ALLOWED_VIDEO_EXT or ctype.startswith("video/"):
        media_type = "video"
    else:
        raise HTTPException(status_code=400, detail="Only common image/video formats are supported")

    if media_type == "video":
        base = uuid.uuid4().hex
        raw_name = f"{base}_raw{ext or '.bin'}"
        raw_path = MEDIA_DIR / raw_name
        unique_name = f"{base}.mp4"
        file_path = MEDIA_DIR / unique_name

        with raw_path.open("wb") as f:
            while True:
                chunk = await media.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)

        try:
            transcode_video_compatible(raw_path, file_path)
        finally:
            if raw_path.exists():
                raw_path.unlink()
    else:
        unique_name = f"{uuid.uuid4().hex}{ext or '.bin'}"
        file_path = MEDIA_DIR / unique_name
        with file_path.open("wb") as f:
            while True:
                chunk = await media.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)

    with db_conn() as conn:
        conn.execute(
            """
            INSERT INTO posts(user_id, title, description, media_type, filename, source, created_at)
            VALUES (?, ?, ?, ?, ?, 'upload', ?)
            """,
            (user["id"], title.strip()[:120] or "Untitled", description.strip()[:1000], media_type, unique_name, now_iso()),
        )

    target = safe_next(next)
    # If upload was triggered from a typed feed, redirect to the matching feed.
    if target in ("/images", "/videos"):
        target = "/images" if media_type == "image" else "/videos"
    elif target == "/" and media_type == "video":
        target = "/videos"
    return RedirectResponse(url=target, status_code=303)


@app.post("/generate")
def generate_image(
    request: Request,
    prompt: str = Form(...),
    negative_prompt: str = Form(""),
    steps: int = Form(20),
    width: int = Form(512),
    height: int = Form(512),
    next: str = Form("/ai"),
):
    user, redirect = require_user(request, "/me")
    if redirect:
        return redirect

    prompt = prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    safe_steps = max(1, min(60, steps))
    safe_width = max(256, min(1024, width))
    safe_height = max(256, min(1024, height))

    with db_conn() as conn:
        conn.execute(
            """
            INSERT INTO ai_jobs(user_id, prompt, negative_prompt, steps, width, height, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (user["id"], prompt[:2000], negative_prompt[:2000], safe_steps, safe_width, safe_height, now_iso()),
        )

    target = safe_next(next)
    if target == "/ai":
        target = "/ai?queued=1"
    return RedirectResponse(url=target, status_code=303)


@app.post("/post/{post_id}/like")
def like(post_id: int, request: Request):
    user, redirect = require_user(request, f"/post/{post_id}")
    if redirect:
        return redirect

    with db_conn() as conn:
        inserted = conn.execute(
            "INSERT OR IGNORE INTO post_likes(post_id, user_id, created_at) VALUES (?, ?, ?)",
            (post_id, user["id"], now_iso()),
        ).rowcount
        if inserted:
            conn.execute("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))

    return RedirectResponse(url=f"/post/{post_id}", status_code=303)


@app.post("/post/{post_id}/comment")
def comment(request: Request, post_id: int, content: str = Form(...)):
    user, redirect = require_user(request, f"/post/{post_id}")
    if redirect:
        return redirect

    text = content.strip()
    if not text:
        return RedirectResponse(url=f"/post/{post_id}", status_code=303)

    with db_conn() as conn:
        conn.execute(
            "INSERT INTO comments(post_id, user_id, author, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (post_id, user["id"], user["display_name"], text[:1000], now_iso()),
        )
    return RedirectResponse(url=f"/post/{post_id}", status_code=303)


@app.post("/post/{post_id}/delete")
def delete_post(request: Request, post_id: int, token: str = Form("")):
    user = current_user(request)

    with db_conn() as conn:
        post = conn.execute("SELECT id, user_id, filename FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not post:
            return RedirectResponse(url="/", status_code=303)

        is_owner = bool(user and post["user_id"] and user["id"] == post["user_id"])
        is_admin_user = bool(user and user["is_admin"])
        is_admin_token = bool(ADMIN_TOKEN and token == ADMIN_TOKEN)
        if not is_owner and not is_admin_user and not is_admin_token:
            raise HTTPException(status_code=403, detail="Not allowed")

        file_path = MEDIA_DIR / post["filename"]
        if file_path.exists():
            file_path.unlink()

        conn.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
        conn.execute("DELETE FROM post_likes WHERE post_id = ?", (post_id,))
        conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))

    return RedirectResponse(url="/me", status_code=303)
