/**
 * AJAX 评论功能 - 无刷新提交评论
 */

(function() {
    'use strict';

    const CommentHandler = {
        init() {
            this.bindEvents();
            this.initAutoResize();
        },

        bindEvents() {
            // 监听评论表单提交
            const forms = document.querySelectorAll('.comment-form');
            forms.forEach(form => {
                form.addEventListener('submit', this.handleSubmit.bind(this));
            });
        },

        initAutoResize() {
            const textareas = document.querySelectorAll('.comment-form textarea[name="content"]');
            textareas.forEach(textarea => {
                const resize = () => {
                    textarea.style.height = 'auto';
                    textarea.style.height = `${textarea.scrollHeight}px`;
                };
                textarea.addEventListener('input', resize);
                resize();
            });
        },

        async handleSubmit(e) {
            e.preventDefault();
            const form = e.target;
            const submitBtn = form.querySelector('button[type="submit"]');
            const textarea = form.querySelector('textarea[name="content"]');

            // 获取数据
            const formData = new FormData(form);
            const content = formData.get('content');

            if (!content || !content.trim()) {
                Toast.show('请输入评论内容', 'warning');
                return;
            }

            // 禁用提交按钮
            const originalText = submitBtn.textContent;
            submitBtn.disabled = true;
            submitBtn.textContent = '提交中...';

            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    Toast.show('评论成功！', 'success');
                    textarea.value = '';
                    textarea.style.height = 'auto';

                    // 重新加载页面以显示新评论
                    // 后续可改为动态插入
                    setTimeout(() => {
                        window.location.reload();
                    }, 500);
                } else {
                    const data = await response.json();
                    Toast.show(data.error || '评论失败', 'error');
                }
            } catch (error) {
                console.error('评论提交失败:', error);
                Toast.show('评论提交失败，请重试', 'error');
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            }
        }
    };

    // 页面加载完成后初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => CommentHandler.init());
    } else {
        CommentHandler.init();
    }
})();
