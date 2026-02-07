# AJAX点赞功能使用指南

## 📦 已创建的文件

- ✅ `app/routers/likes.py` - 后端API路由
- ✅ `static/js/like.js` - 前端AJAX逻辑
- ✅ `static/css/like-button.css` - 点赞按钮样式

## 🚀 快速集成

### 步骤1: 注册路由

在你的 `app.py` 或 `app/main.py` 中添加：

```python
from app.routers import likes

app.include_router(likes.router)
```

### 步骤2: 在模板中引入CSS和JS

在你的 `post.html` 或基础模板中添加：

```html
<head>
    <!-- 其他CSS -->
    <link rel="stylesheet" href="/static/css/like-button.css">
</head>

<body>
    <!-- 页面内容 -->

    <!-- 在页面底部引入JS -->
    <script src="/static/js/like.js"></script>
</body>
```

### 步骤3: 使用点赞按钮

在帖子详情页或列表页中添加：

```html
<!-- 单个帖子的点赞按钮 -->
{% if current_user %}
<button class="like-btn {% if liked %}liked{% endif %}"
        data-post-id="{{ post['id'] }}"
        aria-pressed="{% if liked %}true{% else %}false{% endif %}"
        aria-label="点赞">
    <span class="like-icon">{% if liked %}❤️{% else %}🤍{% endif %}</span>
    <span class="like-count">{{ post['likes'] }}</span>
</button>
{% else %}
<a href="/login?next=/post/{{ post['id'] }}" class="like-btn">
    <span class="like-icon">🤍</span>
    <span class="like-count">{{ post['likes'] }}</span>
</a>
{% endif %}
```

## 📝 模板变量说明

你需要在渲染模板时提供以下变量：

```python
# 在路由处理函数中
liked = is_liked_by_user(db, post_id, user["id"]) if user else False

return templates.TemplateResponse("post.html", {
    "request": request,
    "post": post,
    "liked": liked,  # ← 关键变量
    "current_user": user
})
```

## 🎨 自定义样式

### 修改颜色

在 `like-button.css` 中修改：

```css
.like-btn.liked {
    border-color: #your-color;
    background: #your-bg-color;
    color: #your-text-color;
}
```

### 使用SVG图标替代Emoji

```html
<button class="like-btn" data-post-id="{{ post['id'] }}">
    <svg class="like-icon" width="20" height="20" viewBox="0 0 24 24">
        <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
    </svg>
    <span class="like-count">{{ post['likes'] }}</span>
</button>
```

## 🧪 测试

### 1. 手动测试

```bash
# 启动应用
cd /data/sharehub
python3 run.py  # 或使用你现有的启动方式

# 访问帖子页面，点击点赞按钮
# 应该看到：
# - 按钮颜色变化
# - 计数实时更新
# - 无需页面刷新
```

### 2. API测试

```bash
# 测试点赞API（需要登录）
curl -X POST http://localhost:8000/post/1/like \
  -H "Cookie: session=你的session值" \
  -H "Content-Type: application/json"

# 预期响应：
# {"success": true, "liked": true, "likes_count": 5, "message": "已点赞"}
```

## 🔧 故障排查

### 问题1: 点击无反应

**检查**:
- 浏览器控制台是否有JS错误
- 按钮是否有 `data-post-id` 属性
- 用户是否已登录

### 问题2: 返回401错误

**原因**: 用户未登录

**解决**: 确保前端检查登录状态，未登录用户显示登录链接而非按钮

### 问题3: 样式不生效

**检查**:
- CSS文件是否正确引入
- 浏览器缓存（强制刷新 Ctrl+F5）
- 检查CSS类名是否匹配

## 🎯 完整示例

`post.html` 模板示例：

```html
<!doctype html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>{{ post['title'] }}</title>
    <link rel="stylesheet" href="/static/style.css">
    <link rel="stylesheet" href="/static/css/like-button.css">
</head>
<body>
    <article>
        <h1>{{ post['title'] }}</h1>

        {% if post['media_type'] == 'image' %}
            <img src="/media/{{ post['filename'] }}" alt="{{ post['title'] }}">
        {% endif %}

        <p>{{ post['description'] }}</p>

        <!-- 点赞按钮 -->
        <div class="post-actions">
            {% if current_user %}
                <button class="like-btn {% if liked %}liked{% endif %}"
                        data-post-id="{{ post['id'] }}"
                        aria-pressed="{% if liked %}true{% else %}false{% endif %}">
                    <span class="like-icon">{% if liked %}❤️{% else %}🤍{% endif %}</span>
                    <span class="like-count">{{ post['likes'] }}</span>
                </button>
            {% else %}
                <a href="/login?next=/post/{{ post['id'] }}" class="like-btn">
                    <span class="like-icon">🤍</span>
                    <span class="like-count">{{ post['likes'] }}</span>
                    <span>登录后点赞</span>
                </a>
            {% endif %}
        </div>
    </article>

    <script src="/static/js/like.js"></script>
</body>
</html>
```

## ✨ 特性

- ✅ **无刷新点赞** - AJAX实现，体验流畅
- ✅ **Toggle功能** - 点赞/取消点赞
- ✅ **实时更新** - 计数即时显示
- ✅ **动画效果** - 点击时有缩放动画
- ✅ **防重复点击** - 自动禁用按钮防止多次提交
- ✅ **响应式设计** - 移动端友好
- ✅ **可访问性** - 支持 aria 属性

## 🔄 与现有代码集成

如果你想在原有 `app.py` 中快速添加此功能：

```python
# 在 app.py 中添加
from app.routers.likes import router as likes_router
app.include_router(likes_router)

# 修改你的 post_detail 路由
@app.get("/post/{post_id}")
def post_detail(post_id: int, request: Request):
    user = current_user(request)

    # ... 获取帖子数据 ...

    # 添加点赞状态检查
    from app.services.likes import is_liked_by_user
    with get_db(settings.DATABASE_PATH) as conn:
        liked = is_liked_by_user(conn, post_id, user["id"]) if user else False

    return templates.TemplateResponse("post.html", {
        "request": request,
        "post": post,
        "liked": liked,  # 新增
        "current_user": user
    })
```

完成！你现在有一个完整的AJAX点赞功能了！🎉
