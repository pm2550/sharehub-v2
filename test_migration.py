#!/usr/bin/env python3
"""测试数据库迁移"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.migrations import run_migrations
from app.db.connection import get_db

def test_migration():
    """测试数据库迁移"""
    db_path = "/data/sharehub/data/app.db"

    print("=" * 60)
    print("测试数据库迁移")
    print("=" * 60)

    # 运行迁移
    print("\n正在运行迁移...")
    try:
        run_migrations(db_path)
        print("✓ 迁移完成")
    except Exception as e:
        print(f"✗ 迁移失败: {e}")
        return False

    # 验证新表和索引
    print("\n验证数据库结构...")
    with get_db(db_path) as conn:
        # 检查新表
        tables = [
            "tags", "post_tags", "follows", "notifications",
            "reports", "posts_fts", "users_fts", "_schema_version"
        ]

        for table in tables:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ).fetchone()
            if result:
                print(f"✓ 表 {table} 存在")
            else:
                print(f"✗ 表 {table} 不存在")

        # 检查索引
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        ).fetchall()
        print(f"\n✓ 共创建了 {len(indexes)} 个索引")

        # 检查版本
        version = conn.execute(
            "SELECT MAX(version) as v FROM _schema_version"
        ).fetchone()
        print(f"✓ 当前Schema版本: {version['v']}")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_migration()
    sys.exit(0 if success else 1)
