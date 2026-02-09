"""AI 图片生成 Worker"""

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

logger = logging.getLogger("sharehub.ai_worker")


class AIWorker:
    """AI 图片生成后台worker"""

    def __init__(self, db_path: str, media_dir: str, api_url: str,
                 poll_interval: float = 1.5, max_retries: int = 3,
                 job_timeout: int = 600):
        self.db_path = db_path
        self.media_dir = media_dir
        self.api_url = api_url
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self.job_timeout = job_timeout
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._cleanup_counter = 0

    def start(self):
        """启动worker线程"""
        self._recover_orphaned_jobs()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="ai-worker"
        )
        self._thread.start()
        logger.info("AI Worker started")

    def _recover_orphaned_jobs(self):
        """启动时把上次遗留的 running 任务重置为 pending（上次进程死掉导致的孤儿任务）"""
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
        # 降低worker线程优先级，避免影响主web服务
        try:
            os.nice(10)  # 降低CPU优先级
        except (OSError, AttributeError):
            pass  # Windows或权限不足时忽略

        while not self._stop_event.is_set():
            try:
                # 每20个循环清理一次超时任务
                self._cleanup_counter += 1
                if self._cleanup_counter >= 20:
                    self._cleanup_counter = 0
                    self._cleanup_stuck_jobs()

                has_job = self._process_next_job()
                # 有任务时更频繁检查，无任务时降低频率
                wait_time = self.poll_interval if has_job else self.poll_interval * 2
                self._stop_event.wait(wait_time)
            except Exception as e:
                logger.exception(f"Unhandled error in AI worker: {e}")
                self._stop_event.wait(5)  # 出错后等待5秒再继续

    def _cleanup_stuck_jobs(self):
        """清理卡住的 running 任务（A1111 没在跑但数据库显示 running）"""
        try:
            # 检查 A1111 是否有活跃任务
            resp = requests.get(f"{self.api_url}/sdapi/v1/progress", timeout=5)
            progress = resp.json()
            a1111_busy = progress.get("state", {}).get("job_count", 0) > 0
        except Exception:
            return  # A1111 不可达时不做清理

        if a1111_busy:
            return  # A1111 正在工作，不清理

        # A1111 空闲但有 running 任务 → 卡住了（至少等 60 秒避免竞态）
        cutoff = now_unix() - 60
        try:
            with get_db(self.db_path) as conn:
                stuck = conn.execute(
                    """
                    SELECT id, retry_count FROM ai_jobs
                    WHERE status = 'running' AND started_unix IS NOT NULL AND started_unix < ?
                    """,
                    (cutoff,)
                ).fetchall()

                if stuck:
                    for row in stuck:
                        job_id = row["id"]
                        retry_count = (row["retry_count"] or 0) + 1
                        if retry_count < self.max_retries:
                            # 还有重试次数，重置为 pending
                            conn.execute(
                                "UPDATE ai_jobs SET status = 'pending', started_at = NULL, started_unix = NULL, retry_count = ? WHERE id = ?",
                                (retry_count, job_id)
                            )
                            logger.warning(f"AI job #{job_id} stuck (A1111 idle), reset to pending (retry {retry_count}/{self.max_retries})")
                        else:
                            # 超过重试次数，标记失败
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
        """
        处理下一个待处理任务

        Returns:
            是否处理了任务
        """
        with get_db(self.db_path) as conn:
            # 获取下一个待处理任务（未取消的pending状态，按priority升序 + id升序）
            job = conn.execute(
                """
                SELECT * FROM ai_jobs
                WHERE status = 'pending' AND cancelled = 0
                ORDER BY priority ASC, id ASC LIMIT 1
                """
            ).fetchone()

            if not job:
                return False

            job = dict(job)  # sqlite3.Row → dict (支持 .get())
            job_id = job["id"]

            # 标记为running
            started_at = now_iso()
            started_unix = now_unix()
            conn.execute(
                """
                UPDATE ai_jobs SET status = 'running', started_at = ?, started_unix = ?
                WHERE id = ?
                """,
                (started_at, started_unix, job_id),
            )
            conn.commit()

        logger.info(f"Processing AI job #{job_id}")

        # 执行生成（在事务外，避免长时间持有锁）
        try:
            result_path, thumbnail_path = self._generate_image(job)
            self._save_result(job_id, job["user_id"], job["prompt"], result_path, thumbnail_path)
            logger.info(f"✓ AI job #{job_id} completed")
        except Exception as e:
            self._handle_failure(job_id, job, str(e))

        return True

    def _generate_image(self, job) -> tuple:
        """
        调用A1111 API生成图片

        Returns:
            (original_path, thumbnail_path)
        """
        payload = {
            "prompt": job["prompt"],
            "negative_prompt": job.get("negative_prompt", ""),
            "steps": int(job.get("steps", 40)),
            "sampler_name": job.get("sampler", "Euler a"),
            "cfg_scale": float(job.get("cfg_scale", 5.5)),
            "width": int(job.get("width", 1024)),
            "height": int(job.get("height", 768)),
            "override_settings": {
                "sd_model_checkpoint": "animagineXL40_v4Opt.safetensors"
            }
        }

        if job.get("denoising_strength") is not None:
            payload["denoising_strength"] = float(job["denoising_strength"])

        logger.debug(f"Calling A1111 API: {self.api_url}/sdapi/v1/txt2img")

        resp = requests.post(
            f"{self.api_url}/sdapi/v1/txt2img", json=payload, timeout=None
        )
        resp.raise_for_status()
        data = resp.json()

        images = data.get("images", [])
        if not images:
            raise RuntimeError("A1111 API returned no images")

        # 解码base64图片
        b64 = images[0]
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        img_bytes = base64.b64decode(b64)

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

    def _save_result(self, job_id: int, user_id: int, prompt: str, result_path: str, thumbnail_path: str):
        """保存生成结果为帖子"""
        finished_at = now_iso()
        finished_unix = now_unix()

        with get_db(self.db_path) as conn:
            # 创建帖子
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

            # 更新任务状态
            conn.execute(
                """
                UPDATE ai_jobs
                SET status = 'done', finished_at = ?, finished_unix = ?, result_post_id = ?, error_message = NULL
                WHERE id = ?
                """,
                (finished_at, finished_unix, post_id, job_id),
            )
            conn.commit()

    def _handle_failure(self, job_id: int, job, error_msg: str):
        """处理任务失败"""
        retry_count = (job.get("retry_count") or 0) + 1
        finished_at = now_iso()
        finished_unix = now_unix()

        with get_db(self.db_path) as conn:
            if retry_count < self.max_retries:
                # 重试
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
                # 超过重试次数，标记为失败
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
                    job_timeout: int = 600):
    """启动全局AI worker"""
    global _worker
    if _worker is None:
        _worker = AIWorker(db_path, media_dir, api_url, poll_interval, max_retries, job_timeout)
        _worker.start()
    return _worker


def stop_ai_worker():
    """停止全局AI worker"""
    global _worker
    if _worker is not None:
        _worker.stop()
        _worker = None
