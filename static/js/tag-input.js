// 标签输入自动补全
(function () {
    'use strict';

    const tagInput = document.getElementById('tag-input');
    const tagSuggestions = document.getElementById('tag-suggestions');
    const tagsContainer = document.getElementById('tags-container');
    const tagsHiddenInput = document.getElementById('tags-hidden');

    if (!tagInput) return;

    let selectedTags = [];
    let allTags = [];
    let currentFocus = -1;

    // 加载所有可用标签
    loadAllTags();

    function loadAllTags() {
        fetch('/api/v1/tags/popular?limit=100')
            .then(response => response.json())
            .then(data => {
                allTags = data.tags || [];
            })
            .catch(error => {
                console.error('加载标签失败:', error);
            });
    }

    // 监听输入
    tagInput.addEventListener('input', function (e) {
        const query = e.target.value.trim().toLowerCase();

        if (query.length === 0) {
            hideSuggestions();
            return;
        }

        // 过滤匹配的标签
        const matches = allTags.filter(tag =>
            tag.name.toLowerCase().includes(query) &&
            !selectedTags.includes(tag.name)
        ).slice(0, 10);

        showSuggestions(matches);
    });

    // 监听键盘事件
    tagInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();

            if (currentFocus >= 0 && tagSuggestions) {
                // 选择建议的标签
                const items = tagSuggestions.getElementsByClassName('tag-suggestion-item');
                if (items[currentFocus]) {
                    items[currentFocus].click();
                }
            } else {
                // 直接添加输入的标签
                const tag = tagInput.value.trim();
                if (tag) {
                    addTag(tag);
                    tagInput.value = '';
                    hideSuggestions();
                }
            }
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (tagSuggestions && tagSuggestions.style.display !== 'none') {
                currentFocus++;
                addActive();
            }
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (tagSuggestions && tagSuggestions.style.display !== 'none') {
                currentFocus--;
                addActive();
            }
        } else if (e.key === 'Escape') {
            hideSuggestions();
        } else if (e.key === ',') {
            e.preventDefault();
            const tag = tagInput.value.trim();
            if (tag) {
                addTag(tag);
                tagInput.value = '';
                hideSuggestions();
            }
        }
    });

    function showSuggestions(tags) {
        if (!tagSuggestions || tags.length === 0) {
            hideSuggestions();
            return;
        }

        let html = '';
        tags.forEach(tag => {
            html += `
                <div class="tag-suggestion-item" data-tag="${escapeHtml(tag.name)}">
                    <span class="tag-name">${escapeHtml(tag.name)}</span>
                    <span class="tag-count">${tag.count || 0} 个帖子</span>
                </div>
            `;
        });

        tagSuggestions.innerHTML = html;
        tagSuggestions.style.display = 'block';
        currentFocus = -1;

        // 绑定点击事件
        const items = tagSuggestions.getElementsByClassName('tag-suggestion-item');
        Array.from(items).forEach(item => {
            item.addEventListener('click', function () {
                const tagName = this.dataset.tag;
                addTag(tagName);
                tagInput.value = '';
                hideSuggestions();
            });
        });
    }

    function hideSuggestions() {
        if (tagSuggestions) {
            tagSuggestions.style.display = 'none';
            tagSuggestions.innerHTML = '';
        }
        currentFocus = -1;
    }

    function addActive() {
        if (!tagSuggestions) return;

        const items = tagSuggestions.getElementsByClassName('tag-suggestion-item');
        if (items.length === 0) return;

        removeActive();

        if (currentFocus >= items.length) currentFocus = 0;
        if (currentFocus < 0) currentFocus = items.length - 1;

        items[currentFocus].classList.add('active');
    }

    function removeActive() {
        if (!tagSuggestions) return;

        const items = tagSuggestions.getElementsByClassName('tag-suggestion-item');
        Array.from(items).forEach(item => {
            item.classList.remove('active');
        });
    }

    function addTag(tagName) {
        tagName = tagName.trim().toLowerCase();

        // 验证标签
        if (!tagName || tagName.length > 30) {
            Toast.show('标签长度应在1-30字符之间', 'error');
            return;
        }

        if (selectedTags.includes(tagName)) {
            Toast.show('标签已存在', 'warning');
            return;
        }

        if (selectedTags.length >= 10) {
            Toast.show('最多只能添加10个标签', 'warning');
            return;
        }

        selectedTags.push(tagName);
        updateTagsDisplay();
        updateHiddenInput();
    }

    function removeTag(tagName) {
        selectedTags = selectedTags.filter(t => t !== tagName);
        updateTagsDisplay();
        updateHiddenInput();
    }

    function updateTagsDisplay() {
        if (!tagsContainer) return;

        let html = '';
        selectedTags.forEach(tag => {
            html += `
                <span class="tag-badge">
                    ${escapeHtml(tag)}
                    <button type="button" class="tag-remove" data-tag="${escapeHtml(tag)}">×</button>
                </span>
            `;
        });

        tagsContainer.innerHTML = html;

        // 绑定删除事件
        const removeButtons = tagsContainer.getElementsByClassName('tag-remove');
        Array.from(removeButtons).forEach(btn => {
            btn.addEventListener('click', function () {
                const tagName = this.dataset.tag;
                removeTag(tagName);
            });
        });
    }

    function updateHiddenInput() {
        if (tagsHiddenInput) {
            tagsHiddenInput.value = selectedTags.join(',');
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 点击外部关闭建议
    document.addEventListener('click', function (e) {
        if (!tagInput.contains(e.target) && tagSuggestions && !tagSuggestions.contains(e.target)) {
            hideSuggestions();
        }
    });

    // 初始化已有标签（编辑模式）
    if (tagsHiddenInput && tagsHiddenInput.value) {
        selectedTags = tagsHiddenInput.value.split(',').filter(t => t.trim());
        updateTagsDisplay();
    }
})();
