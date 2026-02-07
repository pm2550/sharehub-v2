"""标签服务"""

import sqlite3
import re
from typing import List, Optional
from app.services.auth import now_iso


def slugify(text: str) -> str:
    """将文本转换为 slug（URL 友好格式）"""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:50]


def get_or_create_tag(conn: sqlite3.Connection, name: str) -> int:
    """获取或创建标签"""
    name = name.strip()
    if not name or len(name) > 50:
        raise ValueError("标签名称长度需在 1-50")
    
    slug = slugify(name)
    
    # 尝试获取已存在的标签
    existing = conn.execute(
        "SELECT id FROM tags WHERE slug = ?", (slug,)
    ).fetchone()
    
    if existing:
        return existing["id"]
    
    # 创建新标签
    conn.execute(
        "INSERT INTO tags(name, slug, created_at) VALUES (?, ?, ?)",
        (name, slug, now_iso())
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def add_tags_to_post(conn: sqlite3.Connection, post_id: int, tag_names: List[str]):
    """为帖子添加标签"""
    for name in tag_names:
        if not name.strip():
            continue
        tag_id = get_or_create_tag(conn, name)
        conn.execute(
            "INSERT OR IGNORE INTO post_tags(post_id, tag_id, created_at) VALUES (?, ?, ?)",
            (post_id, tag_id, now_iso())
        )


def get_post_tags(conn: sqlite3.Connection, post_id: int) -> List[sqlite3.Row]:
    """获取帖子的标签"""
    return conn.execute(
        """
        SELECT t.id, t.name, t.slug
        FROM tags t
        JOIN post_tags pt ON pt.tag_id = t.id
        WHERE pt.post_id = ?
        ORDER BY t.name
        """,
        (post_id,)
    ).fetchall()


def get_popular_tags(conn: sqlite3.Connection, limit: int = 20) -> List[sqlite3.Row]:
    """获取热门标签（按使用次数排序）"""
    return conn.execute(
        """
        SELECT t.id, t.name, t.slug, COUNT(pt.post_id) as post_count
        FROM tags t
        LEFT JOIN post_tags pt ON pt.tag_id = t.id
        GROUP BY t.id
        ORDER BY post_count DESC, t.name
        LIMIT ?
        """,
        (limit,)
    ).fetchall()


def get_tag_by_slug(conn: sqlite3.Connection, slug: str) -> Optional[sqlite3.Row]:
    """根据 slug 获取标签"""
    return conn.execute(
        "SELECT id, name, slug FROM tags WHERE slug = ?",
        (slug,)
    ).fetchone()


def get_posts_by_tag(conn: sqlite3.Connection, tag_id: int, limit: int = 20, offset: int = 0) -> List[sqlite3.Row]:
    """获取某个标签的所有帖子"""
    return conn.execute(
        """
        SELECT p.id, p.title, p.description, p.media_type, p.filename,
               p.thumbnail_path, p.likes, p.created_at,
               COALESCE(u.display_name, u.username, 'legacy') AS author,
               COALESCE(u.username, 'legacy') AS author_username
        FROM posts p
        JOIN post_tags pt ON pt.post_id = p.id
        LEFT JOIN users u ON u.id = p.user_id
        WHERE pt.tag_id = ?
        ORDER BY p.id DESC
        LIMIT ? OFFSET ?
        """,
        (tag_id, limit, offset)
    ).fetchall()
