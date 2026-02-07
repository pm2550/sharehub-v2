/**
 * ShareHub 2.0 - Toast 通知系统
 */

(function() {
    'use strict';

    let container;

    // 初始化容器
    function init() {
        if (container) return;

        container = document.createElement('div');
        container.className = 'toast-container';
        container.setAttribute('aria-live', 'polite');
        container.setAttribute('aria-atomic', 'true');
        document.body.appendChild(container);
    }

    /**
     * 显示Toast消息
     * @param {string} message - 消息内容
     * @param {string} type - 类型: success, error, warning, info
     * @param {number} duration - 显示时长（毫秒），0表示不自动关闭
     */
    function show(message, type = 'info', duration = 4000) {
        init();

        const toast = document.createElement('div');
        toast.className = `toast toast--${type}`;
        toast.setAttribute('role', 'alert');

        const icon = getIcon(type);
        toast.innerHTML = `
            <span class="toast__icon">${icon}</span>
            <span class="toast__message">${escapeHtml(message)}</span>
            <button class="toast__close" aria-label="关闭">&times;</button>
        `;

        container.appendChild(toast);

        // 关闭按钮
        const closeBtn = toast.querySelector('.toast__close');
        closeBtn.addEventListener('click', () => removeToast(toast));

        // 触发入场动画
        requestAnimationFrame(() => {
            toast.classList.add('toast--visible');
        });

        // 自动关闭
        if (duration > 0) {
            setTimeout(() => removeToast(toast), duration);
        }

        return toast;
    }

    // 移除Toast
    function removeToast(toast) {
        toast.classList.remove('toast--visible');
        toast.addEventListener('transitionend', () => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        });
    }

    // 获取图标
    function getIcon(type) {
        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };
        return icons[type] || icons.info;
    }

    // HTML转义
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 快捷方法
    function success(message, duration) {
        return show(message, 'success', duration);
    }

    function error(message, duration) {
        return show(message, 'error', duration);
    }

    function warning(message, duration) {
        return show(message, 'warning', duration);
    }

    function info(message, duration) {
        return show(message, 'info', duration);
    }

    // 导出到全局
    window.Toast = {
        show,
        success,
        error,
        warning,
        info
    };
})();
