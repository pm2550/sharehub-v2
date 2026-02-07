// 通知轮询和实时更新
(function () {
    'use strict';

    const notificationBell = document.getElementById('notification-bell');
    const notificationBadge = document.getElementById('notification-badge');

    if (!notificationBell || !notificationBadge) return;

    // 30秒轮询一次未读通知数
    const POLL_INTERVAL = 30000;
    let pollTimer;

    function updateUnreadCount() {
        fetch('/api/v1/notifications/unread-count')
            .then(response => {
                if (!response.ok) throw new Error('Failed to fetch');
                return response.json();
            })
            .then(data => {
                const count = data.unread_count || 0;
                updateBadge(count);
            })
            .catch(error => {
                console.error('获取未读通知数失败:', error);
            });
    }

    function updateBadge(count) {
        if (count > 0) {
            notificationBadge.textContent = count > 99 ? '99+' : count;
            notificationBadge.style.display = 'inline-block';

            // 添加脉冲动画效果
            notificationBadge.classList.add('pulse');
            setTimeout(() => {
                notificationBadge.classList.remove('pulse');
            }, 1000);
        } else {
            notificationBadge.style.display = 'none';
        }
    }

    function startPolling() {
        // 立即执行一次
        updateUnreadCount();

        // 启动定时轮询
        pollTimer = setInterval(updateUnreadCount, POLL_INTERVAL);
    }

    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    // 页面可见时轮询，隐藏时停止
    document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
            stopPolling();
        } else {
            startPolling();
        }
    });

    // 启动轮询
    startPolling();

    // 标记通知已读（在通知页面）
    const markReadButtons = document.querySelectorAll('.mark-read-btn');
    markReadButtons.forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            const notificationId = this.dataset.id;

            fetch(`/api/v1/notifications/${notificationId}/read`, {
                method: 'POST'
            })
                .then(response => {
                    if (!response.ok) throw new Error('Failed to mark as read');
                    return response.json();
                })
                .then(() => {
                    // 移除未读样式
                    const notificationItem = this.closest('.notification-item');
                    if (notificationItem) {
                        notificationItem.classList.remove('unread');
                        this.remove();
                    }

                    // 更新未读数
                    updateUnreadCount();

                    Toast.show('已标记为已读', 'success');
                })
                .catch(error => {
                    console.error('标记已读失败:', error);
                    Toast.show('操作失败', 'error');
                });
        });
    });

    // 全部标记已读
    const markAllReadBtn = document.getElementById('mark-all-read');
    if (markAllReadBtn) {
        markAllReadBtn.addEventListener('click', function (e) {
            e.preventDefault();

            fetch('/api/v1/notifications/mark-all-read', {
                method: 'POST'
            })
                .then(response => {
                    if (!response.ok) throw new Error('Failed to mark all as read');
                    return response.json();
                })
                .then(() => {
                    // 移除所有未读样式
                    const unreadItems = document.querySelectorAll('.notification-item.unread');
                    unreadItems.forEach(item => {
                        item.classList.remove('unread');
                    });

                    // 移除所有标记按钮
                    const markReadButtons = document.querySelectorAll('.mark-read-btn');
                    markReadButtons.forEach(btn => btn.remove());

                    // 更新badge
                    updateBadge(0);

                    Toast.show('全部标记为已读', 'success');
                })
                .catch(error => {
                    console.error('全部标记已读失败:', error);
                    Toast.show('操作失败', 'error');
                });
        });
    }

    // 添加脉冲动画样式
    if (!document.getElementById('notification-pulse-style')) {
        const style = document.createElement('style');
        style.id = 'notification-pulse-style';
        style.textContent = `
            .notification-badge.pulse {
                animation: notification-pulse 0.5s ease-out;
            }
            @keyframes notification-pulse {
                0% {
                    transform: scale(1);
                }
                50% {
                    transform: scale(1.3);
                }
                100% {
                    transform: scale(1);
                }
            }
        `;
        document.head.appendChild(style);
    }
})();
