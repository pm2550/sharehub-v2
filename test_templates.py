#!/usr/bin/env python3
"""快速测试模板渲染"""
import sys
from jinja2 import Environment, FileSystemLoader, select_autoescape

# 创建 Jinja2 环境
env = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=select_autoescape(['html', 'xml'])
)

def test_template(name, context):
    """测试单个模板"""
    try:
        template = env.get_template(name)
        result = template.render(**context)
        print(f"✓ {name} - 渲染成功 ({len(result)} 字符)")
        return True
    except Exception as e:
        print(f"✗ {name} - 错误: {e}")
        return False

# 测试上下文数据
contexts = {
    'feed.html': {
        'site_title': 'ShareHub',
        'page_title': '图片广场',
        'page_desc': '所有用户上传的图片',
        'active': 'images',
        'current_user': None,
        'posts': [],
        'pagination': {
            'page': 1,
            'total_pages': 1,
            'total': 0
        }
    },
    'ai.html': {
        'site_title': 'ShareHub',
        'page_title': 'AI 生图',
        'page_desc': 'A1111 生成的图片',
        'active': 'ai',
        'current_user': None,
        'posts': [],
        'pagination': {
            'page': 1,
            'total_pages': 1,
            'total': 0
        },
        'active_queue_jobs': [],
        'my_queue_jobs': [],
        'avg_seconds': 30
    },
    'home.html': {
        'site_title': 'ShareHub',
        'active': 'home',
        'current_user': None,
        'stats': {
            'users': 0,
            'posts': 0,
            'images': 0,
            'videos': 0,
            'ai': 0
        },
        'recent_images': [],
        'recent_videos': [],
        'recent_ai': []
    }
}

print("测试模板渲染...\n")
success = 0
total = 0

for template_name, context in contexts.items():
    total += 1
    if test_template(template_name, context):
        success += 1

print(f"\n结果: {success}/{total} 模板渲染成功")
sys.exit(0 if success == total else 1)
