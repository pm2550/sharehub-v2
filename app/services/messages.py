"""私信/对话服务"""

import sqlite3
from typing import List, Optional
from app.services.auth import now_iso


def send_message(
    conn: sqlite3.Connection,
    sender_id: int,
    receiver_id: int,
    content: str,
    post_id: Optional[int] = None
) -> int:
    """
    发送私信

    Args:
        sender_id: 发送者ID
        receiver_id: 接收者ID
        content: 消息内容
        post_id: 附带的帖子ID（可选，分享帖子卡片）

    Returns:
        消息ID
    """
    if sender_id == receiver_id:
        raise ValueError("不能给自己发消息")

    # 截断内容到2000字符
    content = content[:2000].strip()

    # 如果有帖子附件但没有文本内容，使用默认文本
    if not content and post_id:
        content = "[分享帖子]"
    elif not content:
        raise ValueError("消息内容不能为空")

    # 验证帖子存在
    if post_id:
        post_exists = conn.execute("SELECT 1 FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not post_exists:
            post_id = None

    conn.execute(
        """
        INSERT INTO messages(sender_id, receiver_id, content, post_id, is_read, created_at)
        VALUES (?, ?, ?, ?, 0, ?)
        """,
        (sender_id, receiver_id, content, post_id, now_iso())
    )

    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def _enrich_post_info(conn: sqlite3.Connection, msg_dict: dict) -> dict:
    """为消息附加帖子预览信息"""
    post_id = msg_dict.get("post_id")
    if post_id:
        post = conn.execute(
            """
            SELECT p.id, p.title, p.media_type, p.filename, p.thumbnail_path, p.preview_path,
                   p.likes, p.source,
                   COALESCE(u.display_name, u.username, 'legacy') AS author
            FROM posts p
            LEFT JOIN users u ON u.id = p.user_id
            WHERE p.id = ?
            """,
            (post_id,)
        ).fetchone()
        if post:
            msg_dict["post"] = dict(post)
        else:
            msg_dict["post"] = None
    else:
        msg_dict["post"] = None
    return msg_dict


def get_conversations(
    conn: sqlite3.Connection,
    user_id: int,
    limit: int = 20,
    offset: int = 0
) -> List[dict]:
    """
    获取用户的对话列表

    每个对话显示：对方用户信息、最新一条消息、未读数
    """
    rows = conn.execute(
        """
        SELECT
            m.id, m.sender_id, m.receiver_id, m.content, m.post_id,
            m.created_at, m.is_read,
            CASE
                WHEN m.sender_id = ? THEN m.receiver_id
                ELSE m.sender_id
            END AS other_user_id
        FROM messages m
        WHERE m.id IN (
            SELECT MAX(id)
            FROM messages
            WHERE sender_id = ? OR receiver_id = ?
            GROUP BY
                CASE WHEN sender_id < receiver_id THEN sender_id ELSE receiver_id END,
                CASE WHEN sender_id < receiver_id THEN receiver_id ELSE sender_id END
        )
        ORDER BY m.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (user_id, user_id, user_id, limit, offset)
    ).fetchall()

    conversations = []
    for row in rows:
        other_id = row["other_user_id"]

        other_user = conn.execute(
            "SELECT id, username, display_name, avatar_path FROM users WHERE id = ?",
            (other_id,)
        ).fetchone()

        if not other_user:
            continue

        unread = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE sender_id = ? AND receiver_id = ? AND is_read = 0",
            (other_id, user_id)
        ).fetchone()[0]

        last_msg = dict(row)
        # 对话列表中如果最后一条是帖子分享，显示 "[图片/视频]" 前缀
        if last_msg.get("post_id"):
            last_msg["content_preview"] = "📎 " + last_msg["content"]
        else:
            last_msg["content_preview"] = last_msg["content"]

        conversations.append({
            "other_user": dict(other_user),
            "last_message": last_msg,
            "unread_count": unread,
        })

    return conversations


def count_conversations(conn: sqlite3.Connection, user_id: int) -> int:
    """计算对话总数"""
    row = conn.execute(
        """
        SELECT COUNT(DISTINCT
            CASE WHEN sender_id < receiver_id THEN sender_id ELSE receiver_id END || '-' ||
            CASE WHEN sender_id < receiver_id THEN receiver_id ELSE sender_id END
        )
        FROM messages
        WHERE sender_id = ? OR receiver_id = ?
        """,
        (user_id, user_id)
    ).fetchone()
    return row[0] if row else 0


def get_conversation_messages(
    conn: sqlite3.Connection,
    user_id: int,
    other_user_id: int,
    limit: int = 50,
    offset: int = 0
) -> List[dict]:
    """
    获取与某用户的对话消息

    按时间正序排列（最早的在前，像聊天界面），包含帖子预览信息
    """
    rows = conn.execute(
        """
        SELECT m.id, m.sender_id, m.receiver_id, m.content, m.post_id,
               m.is_read, m.created_at,
               COALESCE(u.display_name, u.username, 'legacy') AS sender_name,
               COALESCE(u.avatar_path, '') AS sender_avatar
        FROM messages m
        LEFT JOIN users u ON u.id = m.sender_id
        WHERE (m.sender_id = ? AND m.receiver_id = ?)
           OR (m.sender_id = ? AND m.receiver_id = ?)
        ORDER BY m.created_at ASC
        LIMIT ? OFFSET ?
        """,
        (user_id, other_user_id, other_user_id, user_id, limit, offset)
    ).fetchall()

    result = []
    for row in rows:
        msg = dict(row)
        _enrich_post_info(conn, msg)
        result.append(msg)
    return result


def mark_conversation_read(
    conn: sqlite3.Connection,
    user_id: int,
    other_user_id: int
) -> int:
    """标记对话已读"""
    result = conn.execute(
        """
        UPDATE messages
        SET is_read = 1
        WHERE sender_id = ? AND receiver_id = ? AND is_read = 0
        """,
        (other_user_id, user_id)
    )
    return result.rowcount


def get_total_unread_count(conn: sqlite3.Connection, user_id: int) -> int:
    """获取所有未读消息总数"""
    row = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE receiver_id = ? AND is_read = 0",
        (user_id,)
    ).fetchone()
    return row[0] if row else 0


def get_unread_count_per_conversation(
    conn: sqlite3.Connection,
    user_id: int,
    other_user_id: int
) -> int:
    """获取与某用户的未读消息数"""
    row = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE sender_id = ? AND receiver_id = ? AND is_read = 0",
        (other_user_id, user_id)
    ).fetchone()
    return row[0] if row else 0


def get_new_messages(
    conn: sqlite3.Connection,
    user_id: int,
    other_user_id: int,
    after_id: int
) -> List[dict]:
    """
    获取对话中的新消息（用于轮询），包含帖子预览
    """
    rows = conn.execute(
        """
        SELECT m.id, m.sender_id, m.receiver_id, m.content, m.post_id,
               m.is_read, m.created_at,
               COALESCE(u.display_name, u.username, 'legacy') AS sender_name,
               COALESCE(u.avatar_path, '') AS sender_avatar
        FROM messages m
        LEFT JOIN users u ON u.id = m.sender_id
        WHERE ((m.sender_id = ? AND m.receiver_id = ?)
           OR (m.sender_id = ? AND m.receiver_id = ?))
          AND m.id > ?
        ORDER BY m.created_at ASC
        """,
        (user_id, other_user_id, other_user_id, user_id, after_id)
    ).fetchall()

    result = []
    for row in rows:
        msg = dict(row)
        _enrich_post_info(conn, msg)
        result.append(msg)
    return result
