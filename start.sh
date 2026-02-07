#!/bin/bash
# ShareHub 2.0 启动脚本（新架构）

cd /data/sharehub

# 激活虚拟环境
source .venv/bin/activate

# 启动应用
echo "🚀 Starting ShareHub 2.0..."
echo "📍 Access at: http://localhost:8000"
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
