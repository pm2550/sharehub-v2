"""AI 队列管理服务"""

import sqlite3
import time
from typing import List, Optional
from app.services.auth import now_iso


def now_unix() -> int:
    """返回当前Unix时间戳"""
    return int(time.time())


def seconds_to_text(seconds: int) -> str:
    """将秒数转换为友好文本"""
    if seconds <= 0:
        return "即将完成"
    if seconds < 60:
        return f"约 {seconds} 秒"
    mins, secs = divmod(seconds, 60)
    if mins < 60:
        return f"约 {mins} 分 {secs} 秒"
    hours, mins = divmod(mins, 60)
    return f"约 {hours} 小时 {mins} 分"


def create_ai_job(
    conn: sqlite3.Connection,
    user_id: int,
    prompt: str,
    negative_prompt: str = "",
    steps: int = 20,
    width: int = 512,
    height: int = 512,
    sampler: str = "Euler a",
    cfg_scale: float = 7.0,
) -> int:
    """
    创建AI生成任务

    Returns:
        新任务的ID
    """
    conn.execute(
        """
        INSERT INTO ai_jobs(user_id, prompt, negative_prompt, steps, width, height,
                            sampler, cfg_scale, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """,
        (
            user_id,
            prompt[:2000],
            negative_prompt[:2000],
            max(1, min(60, steps)),
            max(256, min(1024, width)),
            max(256, min(1024, height)),
            sampler,
            cfg_scale,
            now_iso(),
        ),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


# 别名，用于兼容性
submit_job = create_ai_job


def cancel_ai_job(conn: sqlite3.Connection, job_id: int, user_id: int) -> bool:
    """
    取消AI任务（仅pending状态可取消）

    Returns:
        是否成功取消
    """
    result = conn.execute(
        """
        UPDATE ai_jobs SET cancelled = 1
        WHERE id = ? AND user_id = ? AND status = 'pending'
        """,
        (job_id, user_id),
    )
    return result.rowcount > 0


def delete_ai_job(conn: sqlite3.Connection, job_id: int, user_id: int) -> bool:
    """
    删除AI任务（pending/failed/done状态均可删除，running状态不可删）

    Returns:
        是否成功删除
    """
    result = conn.execute(
        """
        DELETE FROM ai_jobs
        WHERE id = ? AND user_id = ? AND status != 'running'
        """,
        (job_id, user_id),
    )
    return result.rowcount > 0


def move_job_up(conn: sqlite3.Connection, job_id: int, user_id: int) -> bool:
    """
    将任务在队列中上移（降低priority值）

    只能移动自己的pending任务
    """
    job = conn.execute(
        "SELECT id, priority FROM ai_jobs WHERE id = ? AND user_id = ? AND status = 'pending'",
        (job_id, user_id)
    ).fetchone()
    if not job:
        return False

    current_priority = job["priority"] or 0
    new_priority = current_priority - 1

    conn.execute(
        "UPDATE ai_jobs SET priority = ? WHERE id = ?",
        (new_priority, job_id)
    )
    return True


def move_job_down(conn: sqlite3.Connection, job_id: int, user_id: int) -> bool:
    """
    将任务在队列中下移（增加priority值）

    只能移动自己的pending任务
    """
    job = conn.execute(
        "SELECT id, priority FROM ai_jobs WHERE id = ? AND user_id = ? AND status = 'pending'",
        (job_id, user_id)
    ).fetchone()
    if not job:
        return False

    current_priority = job["priority"] or 0
    new_priority = current_priority + 1

    conn.execute(
        "UPDATE ai_jobs SET priority = ? WHERE id = ?",
        (new_priority, job_id)
    )
    return True


def get_ai_job_by_id(conn: sqlite3.Connection, job_id: int) -> Optional[sqlite3.Row]:
    """获取AI任务详情"""
    return conn.execute(
        "SELECT * FROM ai_jobs WHERE id = ?", (job_id,)
    ).fetchone()


def average_job_seconds(conn: sqlite3.Connection, history_limit: int = 30) -> int:
    """计算平均任务耗时"""
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
        (history_limit,),
    ).fetchall()

    if not rows:
        return 50  # 默认50秒

    total = sum(int(r["finished_unix"]) - int(r["started_unix"]) for r in rows)
    avg = max(5, int(total / len(rows)))
    return avg


def queue_runtime_map(conn: sqlite3.Connection, avg_seconds: int) -> dict:
    """计算队列中每个任务的预估完成时间"""
    waiting = conn.execute(
        """
        SELECT id, status, started_unix
        FROM ai_jobs
        WHERE status IN ('running', 'pending') AND cancelled = 0
        ORDER BY CASE status WHEN 'running' THEN 0 ELSE 1 END, priority ASC, id ASC
        """
    ).fetchall()

    mapping = {}
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
        else:  # pending
            position += 1
            remaining += avg_seconds
            mapping[job_id] = {
                "position": position,
                "eta_seconds": remaining,
                "eta_text": seconds_to_text(remaining),
            }

    return mapping


def list_jobs(
    conn: sqlite3.Connection, limit: int = 30, only_user_id: Optional[int] = None
) -> List[dict]:
    """
    列出AI任务

    Args:
        conn: 数据库连接
        limit: 限制返回数量
        only_user_id: 仅返回指定用户的任务

    Returns:
        任务列表（包含队列位置和ETA信息）
    """
    where = ""
    params = []
    if only_user_id is not None:
        where = "WHERE j.user_id = ?"
        params.append(only_user_id)
    params.append(limit)

    rows = conn.execute(
        f"""
        SELECT j.id, j.user_id, j.prompt, j.negative_prompt, j.steps, j.width, j.height,
               j.status, j.created_at, j.started_at, j.finished_at, j.error_message,
               j.result_post_id, j.sampler, j.cfg_scale,
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

    avg = average_job_seconds(conn)
    queue_map = queue_runtime_map(conn, avg)

    jobs = []
    for row in rows:
        item = dict(row)
        q = queue_map.get(item["id"], {})
        item["queue_position"] = q.get("position")
        item["eta_seconds"] = q.get("eta_seconds")
        item["eta_text"] = q.get("eta_text")
        jobs.append(item)

    return jobs
