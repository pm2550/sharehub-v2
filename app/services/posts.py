"""帖子管理服务"""

import sqlite3
from typing import List, Optional, Tuple
from app.services.auth import now_iso


def query_posts(
    conn: sqlite3.Connection,
    where_sql: str = "",
    params: tuple = (),
    limit: Optional[int] = None,
    offset: int = 0,
    order_by: str = "p.id DESC",
) -> List[sqlite3.Row]:
    """
    查询帖子列表

    Args:
        conn: 数据库连接
        where_sql: WHERE 子句
        params: 查询参数
        limit: 限制返回数量
        offset: 偏移量
        order_by: 排序方式

    Returns:
        帖子列表
    """
    sql = """
        SELECT p.id, p.user_id, p.title, p.description, p.media_type, p.filename,
               p.thumbnail_path, p.preview_path, p.source, p.prompt, p.likes, p.created_at,
               p.file_size, p.original_filename,
               COALESCE(u.display_name, u.username, 'legacy') AS author,
               COALESCE(u.username, 'legacy') AS author_username,
               COALESCE(u.avatar_path, '') AS author_avatar
        FROM posts p
        LEFT JOIN users u ON u.id = p.user_id
    """

    if where_sql:
        sql += f" WHERE {where_sql}"

    sql += f" ORDER BY {order_by}"

    if limit is not None:
        sql += f" LIMIT {int(limit)} OFFSET {max(0, int(offset))}"

    return conn.execute(sql, params).fetchall()


def count_posts(
    conn: sqlite3.Connection, where_sql: str = "", params: tuple = ()
) -> int:
    """统计帖子数量"""
    sql = "SELECT COUNT(*) FROM posts p LEFT JOIN users u ON u.id = p.user_id"
    if where_sql:
        sql += f" WHERE {where_sql}"
    return int(conn.execute(sql, params).fetchone()[0])


def get_post_by_id(conn: sqlite3.Connection, post_id: int) -> Optional[sqlite3.Row]:
    """根据ID获取帖子详情"""
    return conn.execute(
        """
        SELECT p.*, COALESCE(u.display_name, u.username, 'legacy') AS author,
               COALESCE(u.username, 'legacy') AS author_username,
               COALESCE(u.avatar_path, '') AS author_avatar
        FROM posts p
        LEFT JOIN users u ON u.id = p.user_id
        WHERE p.id = ?
        """,
        (post_id,),
    ).fetchone()


def create_post(
    conn: sqlite3.Connection,
    user_id: int,
    title: str,
    description: str,
    media_type: str,
    filename: str,
    source: str = "upload",
    prompt: Optional[str] = None,
    thumbnail_path: Optional[str] = None,
    preview_path: Optional[str] = None,
) -> int:
    """
    创建新帖子

    Returns:
        新帖子的ID
    """
    conn.execute(
        """
        INSERT INTO posts(user_id, title, description, media_type, filename,
                          source, prompt, thumbnail_path, preview_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            title.strip()[:120] or "Untitled",
            description.strip()[:1000],
            media_type,
            filename,
            source,
            prompt[:2000] if prompt else None,
            thumbnail_path,
            preview_path,
            now_iso(),
        ),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def update_post(
    conn: sqlite3.Connection, post_id: int, title: str, description: str
):
    """更新帖子标题和描述"""
    conn.execute(
        "UPDATE posts SET title = ?, description = ? WHERE id = ?",
        (title.strip()[:120] or "Untitled", description.strip()[:1000], post_id),
    )


def delete_post(conn: sqlite3.Connection, post_id: int):
    """删除帖子（级联删除评论和点赞）"""
    conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))


def build_pagination(page: int, total: int, page_size: int) -> dict:
    """
    构建分页信息

    Args:
        page: 当前页码（从1开始）
        total: 总记录数
        page_size: 每页记录数

    Returns:
        分页信息字典
    """
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
