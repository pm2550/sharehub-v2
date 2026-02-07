"""评论管理服务"""

import sqlite3
from typing import List
from app.services.auth import now_iso


def get_comments_by_post(conn: sqlite3.Connection, post_id: int) -> List[sqlite3.Row]:
    """获取帖子的所有评论"""
    return conn.execute(
        """
        SELECT c.id, c.post_id, c.user_id, c.content, c.created_at,
               COALESCE(u.display_name, u.username, c.author, 'legacy') AS author,
               COALESCE(u.username, 'legacy') AS author_username,
               COALESCE(u.avatar_path, '') AS author_avatar
        FROM comments c
        LEFT JOIN users u ON u.id = c.user_id
        WHERE c.post_id = ?
        ORDER BY c.id DESC
        """,
        (post_id,),
    ).fetchall()


def create_comment(
    conn: sqlite3.Connection, post_id: int, user_id: int, display_name: str, content: str
) -> int:
    """
    创建评论

    Returns:
        新评论的ID
    """
    text = content.strip()
    if not text:
        raise ValueError("评论内容不能为空")

    conn.execute(
        "INSERT INTO comments(post_id, user_id, author, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (post_id, user_id, display_name, text[:1000], now_iso()),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_comment(conn: sqlite3.Connection, comment_id: int):
    """删除评论"""
    conn.execute("DELETE FROM comments WHERE id = ?", (comment_id,))


def get_comment_by_id(conn: sqlite3.Connection, comment_id: int):
    """根据ID获取评论"""
    return conn.execute(
        "SELECT * FROM comments WHERE id = ?", (comment_id,)
    ).fetchone()
