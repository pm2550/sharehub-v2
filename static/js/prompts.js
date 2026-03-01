/**
 * Prompt 保存/加载管理
 */
(function () {
    'use strict';

    const panel = document.getElementById('saved-prompts-panel');
    if (!panel) return;

    const listEl = document.getElementById('prompts-list');
    const saveBtn = document.getElementById('save-prompt-btn');
    const toggleBtn = document.getElementById('toggle-prompts-btn');

    // 表单字段
    const promptField = document.getElementById('prompt');
    const negField = document.getElementById('negative_prompt');
    const stepsField = document.getElementById('steps');
    const widthField = document.getElementById('width');
    const heightField = document.getElementById('height');

    // 加载保存的 prompt 列表
    async function loadPrompts() {
        try {
            const res = await fetch('/api/prompts');
            if (!res.ok) return;
            const data = await res.json();
            renderList(data.prompts);
        } catch (e) {
            console.error('Load prompts failed:', e);
        }
    }

    function renderList(prompts) {
        if (!prompts || prompts.length === 0) {
            listEl.innerHTML = '<div class="prompt-empty">还没有保存的 Prompt，点击上方按钮保存当前设置</div>';
            return;
        }

        listEl.innerHTML = prompts.map(p => `
            <div class="prompt-item" data-id="${p.id}">
                <div class="prompt-item-header">
                    <strong class="prompt-item-name">${escapeHtml(p.name)}</strong>
                    <div class="prompt-item-actions">
                        <button type="button" class="prompt-action-btn load-btn" title="加载" data-id="${p.id}">📥</button>
                        <button type="button" class="prompt-action-btn update-btn" title="覆盖更新" data-id="${p.id}">💾</button>
                        <button type="button" class="prompt-action-btn delete-btn" title="删除" data-id="${p.id}">🗑️</button>
                    </div>
                </div>
                <div class="prompt-item-preview">${escapeHtml(p.prompt.substring(0, 80))}${p.prompt.length > 80 ? '...' : ''}</div>
                <div class="prompt-item-meta">${p.width}×${p.height} · ${p.steps} steps</div>
            </div>
        `).join('');
    }

    function escapeHtml(text) {
        const d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }

    // 保存当前表单内容为新 Prompt
    async function saveCurrentPrompt() {
        const name = window.prompt('给这个 Prompt 起个名字：');
        if (!name || !name.trim()) return;

        const formData = new FormData();
        formData.append('name', name.trim());
        formData.append('prompt', promptField.value);
        formData.append('negative_prompt', negField.value);
        formData.append('steps', stepsField.value);
        formData.append('width', widthField.value);
        formData.append('height', heightField.value);

        try {
            const res = await fetch('/api/prompts', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (res.ok) {
                if (window.Toast) Toast.show('Prompt 已保存！', 'success');
                loadPrompts();
            } else {
                if (window.Toast) Toast.show(data.error || '保存失败', 'error');
            }
        } catch (e) {
            console.error('Save prompt failed:', e);
        }
    }

    // 加载 Prompt 到表单
    async function loadPrompt(id) {
        try {
            const res = await fetch(`/api/prompts/${id}`);
            if (!res.ok) return;
            const data = await res.json();
            const p = data.prompt;

            promptField.value = p.prompt;
            negField.value = p.negative_prompt;
            stepsField.value = p.steps;
            widthField.value = p.width;
            heightField.value = p.height;

            if (window.Toast) Toast.show(`已加载: ${p.name}`, 'success');
        } catch (e) {
            console.error('Load prompt failed:', e);
        }
    }

    // 覆盖更新已有 Prompt
    async function updatePrompt(id) {
        if (!confirm('确定要用当前表单内容覆盖更新这个 Prompt 吗？')) return;

        // 先获取原名称
        try {
            const getRes = await fetch(`/api/prompts/${id}`);
            if (!getRes.ok) return;
            const getData = await getRes.json();

            const formData = new FormData();
            formData.append('name', getData.prompt.name);
            formData.append('prompt', promptField.value);
            formData.append('negative_prompt', negField.value);
            formData.append('steps', stepsField.value);
            formData.append('width', widthField.value);
            formData.append('height', heightField.value);

            const res = await fetch(`/api/prompts/${id}`, {
                method: 'PUT',
                body: formData
            });
            if (res.ok) {
                if (window.Toast) Toast.show('Prompt 已更新！', 'success');
                loadPrompts();
            }
        } catch (e) {
            console.error('Update prompt failed:', e);
        }
    }

    // 删除 Prompt
    async function deletePrompt(id) {
        if (!confirm('确定要删除这个 Prompt 吗？')) return;

        try {
            const res = await fetch(`/api/prompts/${id}`, {
                method: 'DELETE'
            });
            if (res.ok) {
                if (window.Toast) Toast.show('已删除', 'success');
                loadPrompts();
            }
        } catch (e) {
            console.error('Delete prompt failed:', e);
        }
    }

    // 事件绑定
    if (saveBtn) {
        saveBtn.addEventListener('click', saveCurrentPrompt);
    }

    if (toggleBtn) {
        toggleBtn.addEventListener('click', function () {
            panel.classList.toggle('collapsed');
            this.textContent = panel.classList.contains('collapsed') ? '📂 我的 Prompt' : '📁 收起';
        });
    }

    listEl.addEventListener('click', function (e) {
        const btn = e.target.closest('.prompt-action-btn');
        if (!btn) return;

        const id = btn.dataset.id;
        if (btn.classList.contains('load-btn')) {
            loadPrompt(id);
        } else if (btn.classList.contains('update-btn')) {
            updatePrompt(id);
        } else if (btn.classList.contains('delete-btn')) {
            deletePrompt(id);
        }
    });

    // 初始加载
    loadPrompts();
})();
