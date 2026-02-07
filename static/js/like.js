/**
 * AJAX 点赞功能
 * 无需刷新页面即可点赞/取消点赞
 */

(function() {
    'use strict';

    // 初始化所有点赞按钮
    document.addEventListener('DOMContentLoaded', function() {
        initLikeButtons();
    });

    function initLikeButtons() {
        const likeButtons = document.querySelectorAll('.like-btn');

        likeButtons.forEach(button => {
            button.addEventListener('click', handleLikeClick);
        });
    }

    async function handleLikeClick(e) {
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
            const response = await fetch(`/post/${postId}/like`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });

            const data = await response.json();

            if (data.success) {
                updateLikeButton(button, data.liked, data.likes_count);

                // 显示Toast提示（如果有toast系统）
                if (window.Toast) {
                    Toast.show(data.message, 'success', 2000);
                }
            } else {
                console.error('Like failed:', data.error);
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

    function updateLikeButton(button, isLiked, likesCount) {
        // 更新按钮状态
        if (isLiked) {
            button.classList.add('liked');
            button.setAttribute('aria-pressed', 'true');
        } else {
            button.classList.remove('liked');
            button.setAttribute('aria-pressed', 'false');
        }

        // 更新图标（如果使用emoji）
        const icon = button.querySelector('.like-icon');
        if (icon) {
            icon.textContent = isLiked ? '❤️' : '🤍';
        }

        // 更新计数
        const countSpan = button.querySelector('.like-count');
        if (countSpan) {
            countSpan.textContent = likesCount;
        }

        // 动画效果
        button.classList.add('like-animation');
        setTimeout(() => {
            button.classList.remove('like-animation');
        }, 300);
    }

    // 导出到全局（可选）
    window.LikeModule = {
        init: initLikeButtons
    };
})();
