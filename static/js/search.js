// 即时搜索功能
(function () {
    'use strict';

    const searchInput = document.getElementById('search-input');
    const searchResults = document.getElementById('search-results');

    if (!searchInput) return;

    let debounceTimer;
    let currentQuery = '';

    searchInput.addEventListener('input', function (e) {
        const query = e.target.value.trim();

        // 清除之前的定时器
        clearTimeout(debounceTimer);

        // 如果查询为空，隐藏结果
        if (query.length === 0) {
            hideResults();
            return;
        }

        // 防抖：300ms后执行搜索
        debounceTimer = setTimeout(() => {
            performSearch(query);
        }, 300);
    });

    function performSearch(query) {
        if (query === currentQuery) return;
        currentQuery = query;

        // 显示loading状态
        if (searchResults) {
            searchResults.innerHTML = '<div class="search-loading">搜索中...</div>';
            searchResults.style.display = 'block';
        }

        // 发送搜索请求
        fetch(`/api/v1/search?q=${encodeURIComponent(query)}&limit=5`)
            .then(response => {
                if (!response.ok) throw new Error('搜索失败');
                return response.json();
            })
            .then(data => {
                displayResults(data);
            })
            .catch(error => {
                console.error('搜索出错:', error);
                if (searchResults) {
                    searchResults.innerHTML = '<div class="search-error">搜索出错，请稍后重试</div>';
                }
            });
    }

    function displayResults(data) {
        if (!searchResults) return;

        const posts = data.posts || [];
        const users = data.users || [];

        if (posts.length === 0 && users.length === 0) {
            searchResults.innerHTML = '<div class="search-empty">未找到相关结果</div>';
            return;
        }

        let html = '';

        // 显示用户结果
        if (users.length > 0) {
            html += '<div class="search-section">';
            html += '<h4 class="search-section-title">用户</h4>';
            users.forEach(user => {
                html += `
                    <a href="/user/${escapeHtml(user.username)}" class="search-item">
                        <div class="search-item-icon">👤</div>
                        <div class="search-item-content">
                            <div class="search-item-title">${escapeHtml(user.display_name || user.username)}</div>
                            ${user.bio ? `<div class="search-item-desc">${escapeHtml(user.bio)}</div>` : ''}
                        </div>
                    </a>
                `;
            });
            html += '</div>';
        }

        // 显示帖子结果
        if (posts.length > 0) {
            html += '<div class="search-section">';
            html += '<h4 class="search-section-title">帖子</h4>';
            posts.forEach(post => {
                const icon = post.media_type === 'image' ? '🖼️' : '🎬';
                html += `
                    <a href="/post/${post.id}" class="search-item">
                        <div class="search-item-icon">${icon}</div>
                        <div class="search-item-content">
                            <div class="search-item-title">${escapeHtml(post.title)}</div>
                            ${post.description ? `<div class="search-item-desc">${escapeHtml(post.description)}</div>` : ''}
                            <div class="search-item-meta">by ${escapeHtml(post.author)}</div>
                        </div>
                    </a>
                `;
            });
            html += '</div>';
        }

        // 添加查看更多链接
        html += `
            <div class="search-footer">
                <a href="/search?q=${encodeURIComponent(currentQuery)}" class="search-view-all">
                    查看所有结果 →
                </a>
            </div>
        `;

        searchResults.innerHTML = html;
    }

    function hideResults() {
        currentQuery = '';
        if (searchResults) {
            searchResults.style.display = 'none';
            searchResults.innerHTML = '';
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 点击外部关闭搜索结果
    document.addEventListener('click', function (e) {
        if (searchResults && !searchInput.contains(e.target) && !searchResults.contains(e.target)) {
            hideResults();
        }
    });

    // ESC键关闭搜索结果
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            hideResults();
        }
    });
})();
