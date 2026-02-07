-- SQLite FTS5 全文搜索系统迁移

-- 1. 创建帖子全文搜索虚拟表
CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
    title,
    description,
    content='posts',
    content_rowid='id'
);

-- 2. 创建用户全文搜索虚拟表
CREATE VIRTUAL TABLE IF NOT EXISTS users_fts USING fts5(
    username,
    display_name,
    bio,
    content='users',
    content_rowid='id'
);

-- 3. 触发器：posts 插入时同步到 FTS
CREATE TRIGGER IF NOT EXISTS posts_fts_insert AFTER INSERT ON posts BEGIN
    INSERT INTO posts_fts(rowid, title, description)
    VALUES (new.id, new.title, COALESCE(new.description, ''));
END;

-- 4. 触发器：posts 更新时同步到 FTS
CREATE TRIGGER IF NOT EXISTS posts_fts_update AFTER UPDATE ON posts BEGIN
    UPDATE posts_fts
    SET title = new.title,
        description = COALESCE(new.description, '')
    WHERE rowid = new.id;
END;

-- 5. 触发器：posts 删除时同步到 FTS
CREATE TRIGGER IF NOT EXISTS posts_fts_delete AFTER DELETE ON posts BEGIN
    DELETE FROM posts_fts WHERE rowid = old.id;
END;

-- 6. 触发器：users 插入时同步到 FTS
CREATE TRIGGER IF NOT EXISTS users_fts_insert AFTER INSERT ON users BEGIN
    INSERT INTO users_fts(rowid, username, display_name, bio)
    VALUES (new.id, new.username, COALESCE(new.display_name, ''), COALESCE(new.bio, ''));
END;

-- 7. 触发器：users 更新时同步到 FTS
CREATE TRIGGER IF NOT EXISTS users_fts_update AFTER UPDATE ON users BEGIN
    UPDATE users_fts
    SET username = new.username,
        display_name = COALESCE(new.display_name, ''),
        bio = COALESCE(new.bio, '')
    WHERE rowid = new.id;
END;

-- 8. 触发器：users 删除时同步到 FTS
CREATE TRIGGER IF NOT EXISTS users_fts_delete AFTER DELETE ON users BEGIN
    DELETE FROM users_fts WHERE rowid = old.id;
END;

-- 9. 初始化：将现有数据导入 FTS
INSERT INTO posts_fts(rowid, title, description)
SELECT id, title, COALESCE(description, '') FROM posts;

INSERT INTO users_fts(rowid, username, display_name, bio)
SELECT id, username, COALESCE(display_name, ''), COALESCE(bio, '') FROM users;
