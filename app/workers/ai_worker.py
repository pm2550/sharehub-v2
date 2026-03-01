"""AI 图片生成 Worker — RunPod (主) + 本地 A1111 (备)"""

import base64
import logging
import os
import threading
import time
import uuid
import requests
from typing import Optional

from app.db.connection import get_db
from app.services.ai_queue import now_iso, now_unix
from app.services.media import generate_thumbnails
from app.services.runpod import (
    is_runpod_available, call_runpod_sdxl,
    get_user_daily_runpod_usage, increment_daily_runpod_usage,
)
from app.services.a1111_manager import a1111_mgr

logger = logging.getLogger("sharehub.ai_worker")


class AIWorker:
    """AI 图片生成后台worker — RunPod 优先，本地 A1111 兜底"""

    def __init__(self, db_path: str, media_dir: str, api_url: str,
                 poll_interval: float = 1.5, max_retries: int = 3,
                 job_timeout: int = 600,
                 runpod_api_key: str = "", runpod_endpoint_id: str = "",
                 runpod_daily_limit: int = 10, runpod_timeout: int = 120):
        self.db_path = db_path
        self.media_dir = media_dir
        self.api_url = api_url  # 本地 A1111
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self.job_timeout = job_timeout
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._cleanup_counter = 0

        # RunPod 配置
        self.runpod_api_key = runpod_api_key
        self.runpod_endpoint_id = runpod_endpoint_id
        self.runpod_daily_limit = runpod_daily_limit
        self.runpod_timeout = runpod_timeout
        self._runpod_ok = is_runpod_available(runpod_api_key, runpod_endpoint_id)

        if self._runpod_ok:
            logger.info("RunPod backend configured (primary)")
        else:
            logger.info("RunPod not configured — using local A1111 only")

    def start(self):
        """启动worker线程"""
        self._recover_orphaned_jobs()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="ai-worker"
        )
        self._thread.start()
        logger.info("AI Worker started")

    def _recover_orphaned_jobs(self):
        """启动时把上次遗留的 running 任务重置为 pending"""
        try:
            with get_db(self.db_path) as conn:
                orphaned = conn.execute(
                    "SELECT id FROM ai_jobs WHERE status = 'running'"
                ).fetchall()
                if orphaned:
                    conn.execute(
                        "UPDATE ai_jobs SET status = 'pending', started_at = NULL, started_unix = NULL WHERE status = 'running'"
                    )
                    conn.commit()
                    ids = [str(r["id"]) for r in orphaned]
                    logger.info(f"Recovered orphaned running jobs: #{', #'.join(ids)} → pending")
        except Exception as e:
            logger.error(f"Error recovering orphaned jobs: {e}")

    def stop(self):
        """停止worker线程"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("AI Worker stopped")

    def _run(self):
        """Worker主循环"""
        try:
            os.nice(10)
        except (OSError, AttributeError):
            pass

        while not self._stop_event.is_set():
            try:
                self._cleanup_counter += 1
                if self._cleanup_counter >= 20:
                    self._cleanup_counter = 0
                    self._cleanup_stuck_jobs()

                has_job = self._process_next_job()
                wait_time = self.poll_interval if has_job else self.poll_interval * 2
                self._stop_event.wait(wait_time)
            except Exception as e:
                logger.exception(f"Unhandled error in AI worker: {e}")
                self._stop_event.wait(5)

    def _cleanup_stuck_jobs(self):
        """清理卡住的 running 任务"""
        # 只清理 backend='local' 的任务 (RunPod 任务是同步调用，不会卡住)
        try:
            resp = requests.get(f"{self.api_url}/sdapi/v1/progress", timeout=5)
            progress = resp.json()
            a1111_busy = progress.get("state", {}).get("job_count", 0) > 0
        except Exception:
            # A1111 不可达时，对超时的 local 任务做清理
            a1111_busy = False

        if a1111_busy:
            return

        cutoff = now_unix() - 60
        try:
            with get_db(self.db_path) as conn:
                stuck = conn.execute(
                    """
                    SELECT id, retry_count FROM ai_jobs
                    WHERE status = 'running'
                      AND (backend = 'local' OR backend IS NULL)
                      AND started_unix IS NOT NULL AND started_unix < ?
                    """,
                    (cutoff,)
                ).fetchall()

                if stuck:
                    for row in stuck:
                        job_id = row["id"]
                        retry_count = (row["retry_count"] or 0) + 1
                        if retry_count < self.max_retries:
                            conn.execute(
                                "UPDATE ai_jobs SET status = 'pending', started_at = NULL, started_unix = NULL, retry_count = ? WHERE id = ?",
                                (retry_count, job_id)
                            )
                            logger.warning(f"AI job #{job_id} stuck, reset to pending (retry {retry_count}/{self.max_retries})")
                        else:
                            conn.execute(
                                """
                                UPDATE ai_jobs
                                SET status = 'failed', finished_at = ?, finished_unix = ?,
                                    error_message = ?, retry_count = ?
                                WHERE id = ?
                                """,
                                (now_iso(), now_unix(),
                                 f"任务失败：已重试 {retry_count} 次仍无法完成",
                                 retry_count, job_id)
                            )
                            logger.warning(f"AI job #{job_id} permanently failed after {retry_count} retries")
                    conn.commit()
        except Exception as e:
            logger.error(f"Error cleaning up stuck jobs: {e}")

    def _process_next_job(self) -> bool:
        """处理下一个待处理任务"""
        with get_db(self.db_path) as conn:
            job = conn.execute(
                """
                SELECT * FROM ai_jobs
                WHERE status = 'pending' AND cancelled = 0
                ORDER BY priority ASC, id ASC LIMIT 1
                """
            ).fetchone()

            if not job:
                return False

            job = dict(job)
            job_id = job["id"]

            # 决定使用哪个后端
            try:
                backend = self._choose_backend(conn, job)
            except RuntimeError as e:
                conn.execute(
                    """
                    UPDATE ai_jobs SET status = 'failed', finished_at = ?, finished_unix = ?, error_message = ?
                    WHERE id = ?
                    """,
                    (now_iso(), now_unix(), str(e), job_id),
                )
                conn.commit()
                logger.warning(f"AI job #{job_id} rejected: {e}")
                return True

            started_at = now_iso()
            started_unix = now_unix()
            conn.execute(
                """
                UPDATE ai_jobs SET status = 'running', started_at = ?, started_unix = ?, backend = ?
                WHERE id = ?
                """,
                (started_at, started_unix, backend, job_id),
            )
            conn.commit()

        logger.info(f"Processing AI job #{job_id} via {backend}")

        try:
            result_path, thumbnail_path = self._generate_image(job, backend)
            self._save_result(job_id, job["user_id"], job["prompt"], result_path, thumbnail_path, backend)

            # RunPod 成功后计费
            if backend == "runpod":
                try:
                    with get_db(self.db_path) as conn:
                        increment_daily_runpod_usage(conn, job["user_id"])
                        conn.commit()
                except Exception as e:
                    logger.error(f"Failed to increment RunPod usage: {e}")

            logger.info(f"✓ AI job #{job_id} completed via {backend}")
        except Exception as e:
            error_msg = str(e)
            # RunPod 失败时降级到本地按需启动
            if backend == "runpod":
                logger.warning(f"RunPod failed for job #{job_id}: {error_msg}, falling back to local (on-demand)")
                try:
                    with get_db(self.db_path) as conn:
                        conn.execute("UPDATE ai_jobs SET backend = 'local' WHERE id = ?", (job_id,))
                        conn.commit()
                    result_path, thumbnail_path = self._generate_image(job, "local")
                    self._save_result(job_id, job["user_id"], job["prompt"], result_path, thumbnail_path, "local")
                    logger.info(f"✓ AI job #{job_id} completed via local (fallback)")
                    return True
                except Exception as e2:
                    self._handle_failure(job_id, job, f"RunPod: {error_msg}; 本地: {e2}")
            else:
                self._handle_failure(job_id, job, error_msg)

        return True

    def _choose_backend(self, conn, job: dict) -> str:
        """选择生成后端：RunPod 优先，额度用完走本地按需启动"""
        if not self._runpod_ok:
            return "local"

        user_id = job["user_id"]
        used = get_user_daily_runpod_usage(conn, user_id)
        if used >= self.runpod_daily_limit:
            logger.info(f"User {user_id} RunPod 额度已用完（{used}/{self.runpod_daily_limit}），使用本地按需启动")
            return "local"

        return "runpod"

    def _generate_image(self, job: dict, backend: str) -> tuple:
        """
        生成图片

        Returns:
            (original_relative_path, thumbnail_path)
        """
        prompt = job["prompt"]
        negative_prompt = job.get("negative_prompt", "")
        width = int(job.get("width", 768))
        height = int(job.get("height", 1024))
        steps = int(job.get("steps", 40))

        if backend == "runpod":
            img_bytes = call_runpod_sdxl(
                api_key=self.runpod_api_key,
                endpoint_id=self.runpod_endpoint_id,
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                steps=steps,
                guidance_scale=float(job.get("cfg_scale", 5.5)),
                scheduler="K_EULER",
                timeout=self.runpod_timeout,
            )
        else:
            img_bytes = self._call_a1111(job)

        # 保存原图
        filename = f"gen_{uuid.uuid4().hex}.png"
        originals_dir = os.path.join(self.media_dir, "originals")
        os.makedirs(originals_dir, exist_ok=True)

        original_path = os.path.join(originals_dir, filename)
        with open(original_path, "wb") as f:
            f.write(img_bytes)

        # 生成缩略图
        thumbs = generate_thumbnails(original_path, self.media_dir)
        thumbnail_path = thumbs.get("sm", "")

        return f"originals/{filename}", thumbnail_path

    def _call_a1111(self, job: dict) -> bytes:
        """调用本地 A1111 API（按需启动）"""
        # 按需启动 A1111，获取实际 URL
        api_url = a1111_mgr.ensure_running()
        logger.info(f"A1111 就绪，开始生成...")

        payload = {
            "prompt": job["prompt"],
            "negative_prompt": job.get("negative_prompt", ""),
            "steps": int(job.get("steps", 40)),
            "sampler_name": job.get("sampler", "Euler a"),
            "cfg_scale": float(job.get("cfg_scale", 5.5)),
            "width": int(job.get("width", 768)),
            "height": int(job.get("height", 1024)),
            "override_settings": {
                "sd_model_checkpoint": "animagineXL40_v4Opt.safetensors"
            }
        }

        if job.get("denoising_strength") is not None:
            payload["denoising_strength"] = float(job["denoising_strength"])

        resp = requests.post(
            f"{api_url}/sdapi/v1/txt2img", json=payload, timeout=None
        )
        resp.raise_for_status()
        data = resp.json()

        images = data.get("images", [])
        if not images:
            raise RuntimeError("A1111 API returned no images")

        b64 = images[0]
        if "," in b64:
            b64 = b64.split(",", 1)[1]

        return base64.b64decode(b64)

    def _save_result(self, job_id: int, user_id: int, prompt: str,
                     result_path: str, thumbnail_path: str, backend: str = "local"):
        """保存生成结果为帖子"""
        finished_at = now_iso()
        finished_unix = now_unix()

        with get_db(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO posts(user_id, title, description, media_type, filename,
                                  thumbnail_path, source, prompt, created_at)
                VALUES (?, ?, ?, 'image', ?, ?, 'ai', ?, ?)
                """,
                (
                    user_id,
                    f"AI: {prompt[:60]}",
                    "",
                    result_path,
                    thumbnail_path,
                    prompt[:2000],
                    finished_at,
                ),
            )
            post_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

            conn.execute(
                """
                UPDATE ai_jobs
                SET status = 'done', finished_at = ?, finished_unix = ?,
                    result_post_id = ?, error_message = NULL, backend = ?
                WHERE id = ?
                """,
                (finished_at, finished_unix, post_id, backend, job_id),
            )
            conn.commit()

    def _handle_failure(self, job_id: int, job, error_msg: str):
        """处理任务失败"""
        retry_count = (job.get("retry_count") or 0) + 1
        finished_at = now_iso()
        finished_unix = now_unix()

        with get_db(self.db_path) as conn:
            if retry_count < self.max_retries:
                conn.execute(
                    """
                    UPDATE ai_jobs SET status = 'pending', retry_count = ?
                    WHERE id = ?
                    """,
                    (retry_count, job_id),
                )
                logger.warning(
                    f"AI job #{job_id} failed (attempt {retry_count}/{self.max_retries}): {error_msg}"
                )
            else:
                conn.execute(
                    """
                    UPDATE ai_jobs
                    SET status = 'failed', finished_at = ?, finished_unix = ?, error_message = ?
                    WHERE id = ?
                    """,
                    (finished_at, finished_unix, error_msg[:1500], job_id),
                )
                logger.error(
                    f"AI job #{job_id} permanently failed after {retry_count} attempts: {error_msg}"
                )
            conn.commit()


# 全局worker实例
_worker: Optional[AIWorker] = None


def start_ai_worker(db_path: str, media_dir: str, api_url: str,
                    poll_interval: float = 1.5, max_retries: int = 3,
                    job_timeout: int = 600,
                    runpod_api_key: str = "", runpod_endpoint_id: str = "",
                    runpod_daily_limit: int = 10, runpod_timeout: int = 120):
    """启动全局AI worker"""
    global _worker
    if _worker is None:
        _worker = AIWorker(
            db_path, media_dir, api_url, poll_interval, max_retries, job_timeout,
            runpod_api_key=runpod_api_key,
            runpod_endpoint_id=runpod_endpoint_id,
            runpod_daily_limit=runpod_daily_limit,
            runpod_timeout=runpod_timeout,
        )
        _worker.start()
    return _worker


def stop_ai_worker():
    """停止全局AI worker"""
    global _worker
    if _worker is not None:
        _worker.stop()
        _worker = None
