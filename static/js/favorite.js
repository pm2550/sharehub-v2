/**
 * AJAX 收藏功能
 * 无需刷新页面即可收藏/取消收藏
 */

(function() {
    'use strict';

    // 初始化所有收藏按钮
    document.addEventListener('DOMContentLoaded', function() {
        initBookmarkButtons();
    });

    function initBookmarkButtons() {
        const bookmarkButtons = document.querySelectorAll('.bookmark-btn');

        bookmarkButtons.forEach(button => {
            button.addEventListener('click', handleBookmarkClick);
        });
    }

    async function handleBookmarkClick(e) {
        e.preventDefault();

        const button = e.currentTarget;
        const postId = button.dataset.postId;

        if (!postId) {
            console.error('Missing post ID');
            return;
        }

        // 防止重复点击
        if (button.disabled) return;
        button.disabled = true;

        try {
            const response = await fetch(`/post/${postId}/favorite`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });

            const data = await response.json();

            if (data.success) {
                updateBookmarkButton(button, data.favorited);

                // 显示Toast提示（如果有toast系统）
                if (window.Toast) {
                    Toast.show(data.message, 'success', 2000);
                }
            } else {
                console.error('Bookmark failed:', data.error);
                if (window.Toast) {
                    Toast.show(data.error || '操作失败', 'error');
                }
            }
        } catch (error) {
            console.error('Error:', error);
            if (window.Toast) {
                Toast.show('网络错误，请重试', 'error');
            }
        } finally {
            button.disabled = false;
        }
    }

    function updateBookmarkButton(button, isFavorited) {
        // 更新按钮状态
        if (isFavorited) {
            button.classList.add('bookmarked');
            button.setAttribute('aria-pressed', 'true');
        } else {
            button.classList.remove('bookmarked');
            button.setAttribute('aria-pressed', 'false');
        }

        // 更新图标（如果使用emoji）
        const icon = button.querySelector('.bookmark-icon');
        if (icon) {
            icon.textContent = isFavorited ? '🔖' : '📑';
        }

        // 更新文本
        const text = button.querySelector('.bookmark-text');
        if (text) {
            text.textContent = isFavorited ? '已收藏' : '收藏';
        }

        // 动画效果
        button.classList.add('bookmark-animation');
        setTimeout(() => {
            button.classList.remove('bookmark-animation');
        }, 300);
    }

    // 导出到全局（可选）
    window.FavoriteModule = {
        init: initBookmarkButtons
    };
})();
