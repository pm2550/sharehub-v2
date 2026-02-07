"""用户 Prompt 保存服务"""

import sqlite3
from typing import List, Optional
from app.services.auth import now_iso


def save_prompt(
    conn: sqlite3.Connection,
    user_id: int,
    name: str,
    prompt: str,
    negative_prompt: str = "",
    steps: int = 40,
    width: int = 768,
    height: int = 1024,
) -> int:
    """保存一条 Prompt"""
    name = name.strip()[:100]
    if not name:
        raise ValueError("请输入 Prompt 名称")

    now = now_iso()
    conn.execute(
        """
        INSERT INTO user_prompts(user_id, name, prompt, negative_prompt, steps, width, height, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, name, prompt, negative_prompt, steps, width, height, now, now)
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def update_prompt(
    conn: sqlite3.Connection,
    prompt_id: int,
    user_id: int,
    name: str,
    prompt: str,
    negative_prompt: str = "",
    steps: int = 40,
    width: int = 768,
    height: int = 1024,
) -> bool:
    """更新一条 Prompt"""
    name = name.strip()[:100]
    if not name:
        raise ValueError("请输入 Prompt 名称")

    result = conn.execute(
        """
        UPDATE user_prompts
        SET name = ?, prompt = ?, negative_prompt = ?, steps = ?, width = ?, height = ?, updated_at = ?
        WHERE id = ? AND user_id = ?
        """,
        (name, prompt, negative_prompt, steps, width, height, now_iso(), prompt_id, user_id)
    )
    return result.rowcount > 0


def delete_prompt(conn: sqlite3.Connection, prompt_id: int, user_id: int) -> bool:
    """删除一条 Prompt"""
    result = conn.execute(
        "DELETE FROM user_prompts WHERE id = ? AND user_id = ?",
        (prompt_id, user_id)
    )
    return result.rowcount > 0


def get_user_prompts(conn: sqlite3.Connection, user_id: int) -> List[sqlite3.Row]:
    """获取用户保存的所有 Prompt"""
    return conn.execute(
        """
        SELECT id, name, prompt, negative_prompt, steps, width, height, created_at, updated_at
        FROM user_prompts
        WHERE user_id = ?
        ORDER BY updated_at DESC
        """,
        (user_id,)
    ).fetchall()


def get_prompt_by_id(conn: sqlite3.Connection, prompt_id: int, user_id: int) -> Optional[sqlite3.Row]:
    """获取单条 Prompt"""
    return conn.execute(
        """
        SELECT id, name, prompt, negative_prompt, steps, width, height, created_at, updated_at
        FROM user_prompts
        WHERE id = ? AND user_id = ?
        """,
        (prompt_id, user_id)
    ).fetchone()
