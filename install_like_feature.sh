#!/bin/bash
# ShareHub AJAX点赞功能一键安装脚本

echo "============================================"
echo "ShareHub AJAX点赞功能安装"
echo "============================================"
echo

# 检查是否在正确的目录
if [ ! -f "app.py" ]; then
    echo "❌ 错误: 请在 /data/sharehub 目录下运行此脚本"
    exit 1
fi

echo "✓ 目录检查通过"

# 1. 检查依赖是否已安装
echo
echo "检查依赖..."
python3 -c "import pydantic_settings" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  pydantic-settings 未安装，正在安装..."
    pip install pydantic-settings python-dotenv Pillow
else
    echo "✓ 依赖已安装"
fi

# 2. 运行数据库迁移（如果还没运行）
echo
echo "运行数据库迁移..."
python3 test_migration.py
if [ $? -eq 0 ]; then
    echo "✓ 数据库迁移成功"
else
    echo "❌ 数据库迁移失败"
    exit 1
fi

# 3. 创建.env文件（如果不存在）
if [ ! -f ".env" ]; then
    echo
    echo "创建.env配置文件..."
    cat > .env << EOF
# ShareHub 配置
SESSION_SECRET=$(openssl rand -hex 32)
ADMIN_TOKEN=$(openssl rand -hex 16)
A1111_API_URL=http://127.0.0.1:8188
DATABASE_PATH=/data/sharehub/data/app.db
MEDIA_DIR=/data/sharehub/data/media
SITE_TITLE=ShareHub
EOF
    echo "✓ .env 文件已创建（使用随机生成的密钥）"
else
    echo "✓ .env 文件已存在"
fi

# 4. 显示集成说明
echo
echo "============================================"
echo "安装完成！"
echo "============================================"
echo
echo "下一步："
echo "1. 编辑你的 app.py，在路由部分添加："
echo
echo "   from app.routers.likes import router as likes_router"
echo "   app.include_router(likes_router)"
echo
echo "2. 在模板中引入CSS和JS："
echo "   <link rel='stylesheet' href='/static/css/like-button.css'>"
echo "   <script src='/static/js/like.js'></script>"
echo
echo "3. 使用点赞按钮（参考 LIKE_USAGE.md）"
echo
echo "详细文档: cat LIKE_USAGE.md"
echo
echo "测试API: curl -X POST http://localhost:8000/post/1/like"
echo
