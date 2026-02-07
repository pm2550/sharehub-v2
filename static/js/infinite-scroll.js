// 无限滚动加载
(function () {
    'use strict';

    const gallery = document.querySelector('.post-grid');
    const paginationContainer = document.querySelector('.pagination');

    if (!gallery) return;

    let currentPage = 1;
    let isLoading = false;
    let hasMore = true;

    // 从分页器获取初始页码
    const paginationInfo = document.querySelector('[data-current-page]');
    if (paginationInfo) {
        currentPage = parseInt(paginationInfo.dataset.currentPage) || 1;
        const totalPages = parseInt(paginationInfo.dataset.totalPages) || 1;
        hasMore = currentPage < totalPages;
    }

    // 获取当前路径用于 AJAX 请求
    const currentPath = window.location.pathname;

    // 创建loading indicator
    const loadingIndicator = document.createElement('div');
    loadingIndicator.className = 'text-center py-lg';
    loadingIndicator.style.display = 'none';
    loadingIndicator.innerHTML = `
        <div class="spinner"></div>
        <p class="text-muted mt-sm">加载中...</p>
    `;

    // 将loading indicator添加到gallery后面
    if (gallery.parentNode) {
        gallery.parentNode.insertBefore(loadingIndicator, gallery.nextSibling);
    }

    // 创建 Intersection Observer
    const sentinel = document.createElement('div');
    sentinel.className = 'scroll-sentinel';
    sentinel.style.height = '1px';
    if (gallery.parentNode) {
        gallery.parentNode.appendChild(sentinel);
    }

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && hasMore && !isLoading) {
                loadMore();
            }
        });
    }, {
        rootMargin: '200px' // 提前200px开始加载
    });

    observer.observe(sentinel);

    function loadMore() {
        if (isLoading || !hasMore) return;

        isLoading = true;
        loadingIndicator.style.display = 'block';

        const nextPage = currentPage + 1;
        const url = `${currentPath}?page=${nextPage}`;

        fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.text();
            })
            .then(html => {
                // 创建临时容器解析HTML
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');

                // 提取新的帖子
                const newPosts = doc.querySelectorAll('.post-grid .post-card');

                if (newPosts.length === 0) {
                    hasMore = false;
                    loadingIndicator.innerHTML = '<p class="text-muted">没有更多内容了</p>';
                    setTimeout(() => {
                        loadingIndicator.style.display = 'none';
                    }, 2000);
                    return;
                }

                // 添加新帖子到gallery
                newPosts.forEach(post => {
                    gallery.appendChild(post.cloneNode(true));
                });

                currentPage = nextPage;

                // 检查是否还有更多
                const newPaginationInfo = doc.querySelector('[data-current-page]');
                if (newPaginationInfo) {
                    const totalPages = parseInt(newPaginationInfo.dataset.totalPages) || 1;
                    hasMore = currentPage < totalPages;
                }

                // 隐藏原始分页器
                if (paginationContainer) {
                    paginationContainer.style.display = 'none';
                }

                // 重新初始化可能需要的功能（如lightbox, like等）
                if (window.Lightbox) {
                    window.Lightbox.init();
                }
            })
            .catch(error => {
                console.error('加载失败:', error);
                Toast.show('加载失败，请稍后重试', 'error');
                hasMore = false;
            })
            .finally(() => {
                isLoading = false;
                loadingIndicator.style.display = 'none';
            });
    }

    // 添加简单的spinner样式
    if (!document.getElementById('spinner-style')) {
        const style = document.createElement('style');
        style.id = 'spinner-style';
        style.textContent = `
            .spinner {
                display: inline-block;
                width: 32px;
                height: 32px;
                border: 3px solid var(--color-border);
                border-top-color: var(--color-primary);
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(style);
    }
})();
