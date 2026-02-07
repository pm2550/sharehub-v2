# ShareHub 2.0

现代化内容分享平台 - 支持图片、视频和AI生成内容

## ✨ 特性

- 📷 **图片分享** - 支持多种图片格式上传和展示
- 🎬 **视频分享** - 流畅的视频播放体验
- 🤖 **AI生成** - 集成Stable Diffusion AI图像生成
- 💬 **社交功能** - 点赞、评论、关注系统
- 🔔 **实时通知** - 完整的通知系统
- 🏷️ **标签系统** - 内容分类和搜索
- 🌓 **暗黑模式** - 精美的日间/夜间主题

## 🛠️ 技术栈

- **后端**: FastAPI + Python 3.8+
- **数据库**: SQLite
- **前端**: 现代化HTML/CSS/JavaScript
- **AI**: Stable Diffusion WebUI (A1111)

## 🚀 快速开始

### 环境要求

- Python 3.8+
- SQLite 3
- (可选) Stable Diffusion WebUI 用于AI生成功能

### 安装步骤

1. **克隆仓库**
```bash
git clone https://github.com/YOUR_USERNAME/sharehub-v2.git
cd sharehub-v2
```

2. **创建虚拟环境**
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件，设置必要的配置
```

5. **运行数据库迁移**
```bash
python -c "from app.db.migrations import run_all_migrations; run_all_migrations()"
```

6. **启动应用**
```bash
python run.py
# 或使用
./start.sh
```

7. **访问应用**
```
http://localhost:8090
```

## 📁 项目结构

```
sharehub-v2/
├── app/                 # 应用主代码
│   ├── routers/        # API路由
│   ├── services/       # 业务逻辑
│   ├── db/             # 数据库相关
│   └── workers/        # 后台任务
├── templates/          # HTML模板
├── static/            # 静态资源
│   ├── css/          # 样式文件
│   └── js/           # JavaScript
├── data/             # 数据存储
│   ├── sharehub.db  # SQLite数据库
│   └── media/       # 上传文件
└── requirements.txt  # Python依赖
```

## 🎨 功能亮点

### 用户系统
- 用户注册/登录
- 个人资料管理
- 关注/粉丝系统

### 内容管理
- 图片/视频上传
- 内容标签
- 搜索功能
- 分页浏览

### AI生成
- Stable Diffusion集成
- 提示词管理
- 生成队列系统
- 自动缩略图

### 社交互动
- 点赞系统
- 评论功能
- 通知中心
- 用户关注

## 🔧 配置说明

主要配置项（.env文件）：

```env
DATABASE_PATH=data/sharehub.db
MEDIA_DIR=data/media
A1111_API_URL=http://localhost:7860
SITE_TITLE=ShareHub
```

## 📝 License

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题，请提交 Issue
