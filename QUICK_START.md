# ShareHub 2.0 - 快速启动指南

## 🎉 新架构说明

ShareHub 已完成 Phase 1 重构，从单体 `app.py` 迁移到模块化架构！

### 架构变更
- ✅ 模块化代码结构 (`app/` 目录)
- ✅ 环境变量配置管理 (`.env`)
- ✅ 数据库连接优化 (WAL 模式)
- ✅ 自动迁移系统
- ✅ AI Worker 重构
- ✅ 请求日志中间件

## 🚀 启动应用

### 方法 1：使用启动脚本（最简单）

```bash
cd /data/sharehub
./start.sh
```

### 方法 2：使用 uvicorn

```bash
cd /data/sharehub
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 方法 3：使用 Python 直接运行

```bash
cd /data/sharehub
source .venv/bin/activate
python -m app.main
```

## 🌐 访问应用

启动后，在浏览器中访问：
- **本地**: http://localhost:8000
- **局域网**: http://YOUR_IP:8000

## 📋 页面导航

- **首页** (`/`) - Hero 部分 + 统计 + 最新内容
- **图片广场** (`/images`) - 所有上传的图片
- **视频广场** (`/videos`) - 所有上传的视频
- **AI 生图** (`/ai`) - AI 生成的作品 + 队列
- **我的中心** (`/me`) - 个人资料 + 上传 + AI 队列 + 内容管理
- **登录** (`/login`) - 用户登录
- **注册** (`/register`) - 用户注册

## ✨ 新功能测试

### 1. 暗色模式
- 点击导航栏右上角的 🌙 图标
- 循环切换：亮色 → 暗色 → 跟随系统
- 设置会自动保存

### 2. AJAX 点赞
- 进入任何帖子详情页
- 点击点赞按钮（❤️/🤍）
- 页面不刷新，计数即时更新

### 3. Lightbox 图片查看
- 进入图片广场或 AI 广场
- 点击任何图片
- 使用键盘导航：
  - `←` 上一张
  - `→` 下一张
  - `Esc` 关闭
- 或点击左右箭头按钮

### 4. Toast 通知
- 执行任何操作（登录、点赞、切换主题等）
- 右上角（移动端底部）会显示提示消息
- 自动消失或手动关闭

### 5. 响应式设计
- 调整浏览器窗口大小
- 或使用浏览器开发者工具模拟移动设备
- 查看自适应布局

## 🔧 故障排查

### 模板未更新？
清除浏览器缓存：
- Chrome/Edge: `Ctrl + Shift + R` (Windows) 或 `Cmd + Shift + R` (Mac)
- Firefox: `Ctrl + F5`

### CSS 未加载？
检查静态文件路径：
```bash
ls -la /data/sharehub/static/css/
ls -la /data/sharehub/static/js/
```

应该看到：
- `variables.css`, `base.css`, `components.css`
- `toast.css`, `like-button.css`, `lightbox.css`
- `theme.js`, `toast.js`, `like.js`, `lightbox.js`

## 📊 测试清单

- [ ] 首页加载正常
- [ ] 暗色模式切换正常
- [ ] 图片广场显示图片
- [ ] 视频广场显示视频
- [ ] AI 广场显示 AI 作品
- [ ] Lightbox 可以打开和关闭
- [ ] 点赞功能正常（AJAX）
- [ ] Toast 提示显示正常
- [ ] 登录/注册页面正常
- [ ] 我的中心 4 个 tab 切换正常
- [ ] 移动端响应式布局正常

享受全新的 ShareHub 2.0 体验！🎉
