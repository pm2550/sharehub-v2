"""数据库连接管理"""

import sqlite3
import threading
import logging
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger("sharehub.db")

# 线程本地存储
_local = threading.local()


def _get_connection(db_path: str) -> sqlite3.Connection:
    """获取或创建线程本地数据库连接"""
    if not hasattr(_local, "connection") or _local.connection is None:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row

        # 优化 PRAGMA 设置
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA temp_store=MEMORY")

        _local.connection = conn
        logger.debug(f"Created new database connection for thread {threading.current_thread().name}")

    return _local.connection


@contextmanager
def get_db(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """
    数据库连接上下文管理器

    成功时自动 commit，失败时自动 rollback
    """
    conn = _get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def close_connection():
    """关闭当前线程的数据库连接"""
    if hasattr(_local, "connection") and _local.connection is not None:
        _local.connection.close()
        _local.connection = None
        logger.debug(f"Closed database connection for thread {threading.current_thread().name}")
