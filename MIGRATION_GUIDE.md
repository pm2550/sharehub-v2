# ShareHub 升级迁移指南

## 当前进度

已完成 Phase 1 的核心基础设施：
- ✅ 配置管理系统 (`app/config.py`)
- ✅ 数据库连接池 (`app/db/connection.py`)
- ✅ 数据库迁移系统 (`app/db/migrations.py`) - 10个版本的Schema升级
- ✅ Services 层 (`app/services/`) - auth, posts, comments, likes, media, ai_queue
- ✅ AI Worker 重构 (`app/workers/ai_worker.py`)
- ✅ 中间件 (`app/middleware/logging.py`)
- ✅ 依赖注入 (`app/dependencies.py`)

## 迁移路径

### 选项 A: 渐进式迁移（推荐）

保持原 `app.py` 运行，逐步将功能迁移到新架构：

1. **现在就可以做的优化：**
   ```bash
   # 1. 安装新依赖
   cd /data/sharehub
   pip install pydantic-settings python-dotenv Pillow

   # 2. 创建 .env 文件
   cp .env.example .env
   # 编辑 .env，设置 SESSION_SECRET 和 ADMIN_TOKEN

   # 3. 运行数据库迁移（添加索引和新表）
   python3 << EOF
from app.db.migrations import run_migrations
run_migrations("/data/sharehub/data/app.db")
EOF
   ```

2. **使用新的 AI Worker：**
   - 修改原 `app.py`，将 AI Worker 部分替换为:
   ```python
   from app.workers.ai_worker import start_ai_worker, stop_ai_worker
   from app.config import get_settings

   @app.on_event("startup")
   def startup():
       settings = get_settings()
       start_ai_worker(
           db_path=settings.DATABASE_PATH,
           media_dir=settings.MEDIA_DIR,
           api_url=settings.A1111_API_URL
       )
   ```

3. **逐个迁移路由：**
   - 从 `app/services/` 使用已有的业务逻辑
   - 例如登录路由可以改为:
   ```python
   from app.services.auth import authenticate_user

   @app.post("/login")
   def login(username: str = Form(...), password: str = Form(...)):
       with get_db(settings.DATABASE_PATH) as conn:
           user = authenticate_user(conn, username, password)
           if user:
               request.session["uid"] = user["id"]
               return RedirectResponse(...)
   ```

### 选项 B: 完全重写（需要更多工作）

创建完整的新路由系统。我已经创建了基础，你需要：

1. 创建所有 router 文件 (`app/routers/auth.py`, `app/routers/pages.py` 等)
2. 在 `app/main.py` 中注册这些路由
3. 迁移所有模板到新结构
4. 测试所有功能

## 数据库迁移详情

已创建的迁移包括：
1. **Version 1**: 所有现有表的索引（大幅提升查询性能）
2. **Version 2**: 用户表新增 `avatar_path`, `theme_preference`
3. **Version 3**: 帖子表新增 `thumbnail_path`, `media_width`, `media_height`
4. **Version 4**: AI任务表新增 `retry_count`, `cancelled`, `sampler`, `cfg_scale` 等
5. **Version 5**: 标签系统 (`tags`, `post_tags`)
6. **Version 6**: 关注系统 (`follows`)
7. **Version 7**: 通知系统 (`notifications`)
8. **Version 8**: 举报系统 (`reports`)
9. **Version 9**: FTS5 全文搜索虚拟表
10. **Version 10**: FTS5 同步触发器

运行迁移后，你可以立即使用这些新功能。

## 快速开始：使用新基础设施

最小改动方案（1小时内完成）：

```python
# 在你的 app.py 开头添加：
from app.config import get_settings
from app.db.migrations import run_migrations
from app.workers.ai_worker import start_ai_worker, stop_ai_worker

settings = get_settings()

# 在 startup 事件中：
@app.on_event("startup")
def startup():
    run_migrations(settings.DATABASE_PATH)  # 运行迁移
    start_ai_worker(
        db_path=settings.DATABASE_PATH,
        media_dir=settings.MEDIA_DIR,
        api_url=settings.A1111_API_URL
    )

@app.on_event("shutdown")
def shutdown():
    stop_ai_worker()

# 然后就可以享受：
# - 所有数据库索引（更快的查询）
# - 更健壮的AI Worker（失败重试、取消任务）
# - 新表结构（为Phase 2/3功能准备）
```

## 下一步

1. 运行数据库迁移
2. 测试现有功能是否正常
3. 决定是渐进式迁移还是完全重写
4. 开始 Phase 2 (UI改造) 或 Phase 3 (新功能)

## 需要帮助？

- 查看 `/data/sharehub/app/` 下的所有模块
- 每个 service 文件都有清晰的函数签名
- 所有数据库操作都已封装好
- Migration系统是幂等的，可以安全运行多次
