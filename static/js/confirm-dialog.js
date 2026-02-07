/**
 * 删除确认对话框
 * 使用方式：<button data-confirm="确定要删除这条内容吗？" data-confirm-action="/post/123/delete">删除</button>
 */

(function() {
    'use strict';

    document.addEventListener('DOMContentLoaded', function() {
        // 监听所有带 data-confirm 属性的元素
        document.addEventListener('click', function(e) {
            const target = e.target.closest('[data-confirm]');
            if (!target) return;

            e.preventDefault();
            e.stopPropagation();

            const message = target.dataset.confirm || '确定要执行此操作吗？';
            const action = target.dataset.confirmAction || target.href;
            const method = target.dataset.confirmMethod || 'POST';

            if (confirm(message)) {
                if (method === 'GET') {
                    window.location.href = action;
                } else {
                    // POST 请求
                    const form = document.createElement('form');
                    form.method = method;
                    form.action = action;
                    document.body.appendChild(form);
                    form.submit();
                }
            }
        });
    });
})();
