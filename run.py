#!/usr/bin/env python3
"""ShareHub 启动脚本"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

# 加载 .env 文件
from dotenv import load_dotenv
load_dotenv()

# 检查必需的环境变量
required_env_vars = ["SESSION_SECRET", "ADMIN_TOKEN"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]

if missing_vars:
    print(f"错误: 缺少必需的环境变量: {', '.join(missing_vars)}")
    print(f"请创建 .env 文件并设置这些变量")
    print(f"参考 .env.example 文件")
    sys.exit(1)

# 启动应用
if __name__ == "__main__":
    import uvicorn
    from app.main import app

    print("=" * 60)
    print("ShareHub 正在启动...")
    print("=" * 60)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
