/**
 * 分片上传队列 — 后台任务式上传，参考 Cloudreve 的任务面板
 *
 * 接管所有 form[action="/upload"]：选文件后不再整页提交，而是切片走
 * /api/upload/* 逐片传，页面留在原地可以继续操作。服务端记着传到第几片，
 * 断了或换页后重选同一个文件即可续传。
 */
(function () {
    'use strict';

    var CHUNK_RETRY = 3;
    var RETRY_BASE_MS = 800;

    var tasks = [];
    var running = false;
    var panel, panelBody, panelTitle, resumeHint;

    // ---------- 工具 ----------

    function fmtSize(bytes) {
        if (!bytes) return '0 B';
        var units = ['B', 'KB', 'MB', 'GB', 'TB'];
        var i = Math.floor(Math.log(bytes) / Math.log(1024));
        i = Math.min(i, units.length - 1);
        return (bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1) + ' ' + units[i];
    }

    function fmtEta(seconds) {
        if (!isFinite(seconds) || seconds <= 0) return '';
        if (seconds < 60) return Math.ceil(seconds) + ' 秒';
        if (seconds < 3600) return Math.ceil(seconds / 60) + ' 分钟';
        return (seconds / 3600).toFixed(1) + ' 小时';
    }

    function sleep(ms) {
        return new Promise(function (r) { setTimeout(r, ms); });
    }

    function toast(msg, type) {
        if (window.Toast) window.Toast.show(msg, type || 'info');
    }

    // ---------- 任务模型 ----------

    function makeTask(file, meta) {
        return {
            key: 'u' + Date.now() + Math.random().toString(36).slice(2, 8),
            file: file,
            title: (meta && meta.title) || file.name,
            description: (meta && meta.description) || '',
            uploadId: (meta && meta.uploadId) || null,
            chunkSize: (meta && meta.chunkSize) || 0,
            totalChunks: (meta && meta.totalChunks) || 0,
            received: (meta && meta.received) || 0,
            status: 'queued',
            statusText: '排队中',
            error: '',
            postUrl: '',
            paused: false,
            xhr: null,
            inFlightBytes: 0,
            samples: []
        };
    }

    function uploadedBytes(task) {
        if (!task.chunkSize) return 0;
        return Math.min(task.received * task.chunkSize + task.inFlightBytes, task.file.size);
    }

    function percent(task) {
        if (task.status === 'done') return 100;
        if (!task.file.size) return task.status === 'uploading' ? 50 : 0;
        return Math.min(99.9, uploadedBytes(task) / task.file.size * 100);
    }

    function trackSpeed(task) {
        var now = Date.now();
        task.samples.push({ t: now, b: uploadedBytes(task) });
        task.samples = task.samples.filter(function (s) { return now - s.t < 8000; });
        if (task.samples.length < 2) return 0;
        var first = task.samples[0];
        var last = task.samples[task.samples.length - 1];
        var dt = (last.t - first.t) / 1000;
        if (dt <= 0) return 0;
        return Math.max(0, (last.b - first.b) / dt);
    }

    // ---------- 网络 ----------

    async function initUpload(task) {
        var fd = new FormData();
        fd.append('filename', task.file.name);
        fd.append('size', String(task.file.size));
        fd.append('content_type', task.file.type || '');
        fd.append('title', task.title);
        fd.append('description', task.description);

        var res = await fetch('/api/upload/init', { method: 'POST', body: fd });
        var data = await res.json().catch(function () { return {}; });
        if (!res.ok) throw new Error(data.detail || '创建上传任务失败');
        return data;
    }

    function putChunk(task, index, blob) {
        return new Promise(function (resolve, reject) {
            var xhr = new XMLHttpRequest();
            task.xhr = xhr;
            xhr.open('PUT', '/api/upload/' + task.uploadId + '/chunk/' + index);
            xhr.upload.onprogress = function (e) {
                if (e.lengthComputable) {
                    task.inFlightBytes = e.loaded;
                    render();
                }
            };
            xhr.onload = function () {
                task.xhr = null;
                task.inFlightBytes = 0;
                var data = {};
                try { data = JSON.parse(xhr.responseText); } catch (e) { }
                if (xhr.status >= 200 && xhr.status < 300) resolve(data);
                else reject(new Error(data.detail || ('分片上传失败 (HTTP ' + xhr.status + ')')));
            };
            xhr.onerror = function () {
                task.xhr = null;
                task.inFlightBytes = 0;
                reject(new Error('网络中断'));
            };
            xhr.onabort = function () {
                task.xhr = null;
                task.inFlightBytes = 0;
                reject(new Error('__aborted__'));
            };
            xhr.send(blob);
        });
    }

    async function completeUpload(task) {
        var res = await fetch('/api/upload/' + task.uploadId + '/complete', { method: 'POST' });
        var data = await res.json().catch(function () { return {}; });
        if (!res.ok) throw new Error(data.detail || '上传收尾失败');
        return data;
    }

    async function abortUpload(task) {
        if (!task.uploadId) return;
        try {
            await fetch('/api/upload/' + task.uploadId + '/abort', { method: 'POST' });
        } catch (e) { /* 服务端有 24h 兜底清理 */ }
    }

    // ---------- 队列 ----------

    async function runTask(task) {
        task.status = 'uploading';
        task.statusText = '准备中';
        render();

        if (!task.uploadId) {
            var init = await initUpload(task);
            task.uploadId = init.upload_id;
            task.chunkSize = init.chunk_size;
            task.totalChunks = init.total_chunks;
            task.received = init.received_chunks;
        }

        while (task.received < task.totalChunks) {
            if (task.paused) {
                task.status = 'paused';
                task.statusText = '已暂停';
                render();
                return;
            }

            var index = task.received;
            var start = index * task.chunkSize;
            var blob = task.file.slice(start, Math.min(start + task.chunkSize, task.file.size));

            var lastErr = null;
            for (var attempt = 0; attempt < CHUNK_RETRY; attempt++) {
                try {
                    var res = await putChunk(task, index, blob);
                    task.received = res.received_chunks;
                    lastErr = null;
                    break;
                } catch (e) {
                    if (e.message === '__aborted__') return;   // 暂停/取消
                    lastErr = e;
                    if (attempt < CHUNK_RETRY - 1) {
                        task.statusText = '重试中 (' + (attempt + 1) + '/' + CHUNK_RETRY + ')';
                        render();
                        await sleep(RETRY_BASE_MS * Math.pow(2, attempt));
                    }
                }
            }
            if (lastErr) throw lastErr;

            var speed = trackSpeed(task);
            var remain = task.file.size - uploadedBytes(task);
            task.statusText = fmtSize(speed) + '/s' + (speed > 0 ? ' · 剩 ' + fmtEta(remain / speed) : '');
            render();
        }

        task.status = 'finalizing';
        task.statusText = task.file.type.indexOf('video/') === 0 ? '转码中…' : '处理中…';
        render();

        var done = await completeUpload(task);
        task.status = 'done';
        task.statusText = '已完成';
        task.postUrl = done.url;
        render();
        toast('「' + task.title + '」上传完成', 'success');
    }

    async function pump() {
        if (running) return;
        running = true;
        try {
            while (true) {
                var task = tasks.find(function (t) { return t.status === 'queued'; });
                if (!task) break;
                try {
                    await runTask(task);
                } catch (e) {
                    task.status = 'error';
                    task.error = e.message || String(e);
                    task.statusText = task.error;
                    render();
                    toast('「' + task.title + '」上传失败：' + task.error, 'error');
                }
            }
        } finally {
            running = false;
        }
    }

    // ---------- 面板渲染 ----------

    function ensurePanel() {
        if (panel) return panel;
        panel = document.getElementById('upload-panel');
        if (!panel) return null;
        panelBody = panel.querySelector('.upload-panel-body');
        panelTitle = panel.querySelector('.upload-panel-title');
        resumeHint = panel.querySelector('.upload-resume-hint');

        panel.querySelector('[data-upload-toggle]').addEventListener('click', function () {
            panel.classList.toggle('collapsed');
        });
        panel.querySelector('[data-upload-close]').addEventListener('click', function () {
            var active = tasks.filter(isActive);
            if (active.length && !confirm('还有 ' + active.length + ' 个上传未完成，关闭面板会取消它们，确定？')) return;
            active.forEach(cancelTask);
            tasks = [];
            panel.classList.remove('on');
            render();
        });
        return panel;
    }

    function isActive(t) {
        return t.status === 'queued' || t.status === 'uploading' || t.status === 'paused' || t.status === 'finalizing';
    }

    function showPanel() {
        if (!ensurePanel()) return;
        panel.classList.add('on');
        panel.classList.remove('collapsed');
    }

    function render() {
        if (!ensurePanel()) return;

        var active = tasks.filter(isActive).length;
        panelTitle.textContent = active ? '上传队列 (' + active + ')' : '上传队列';

        tasks.forEach(function (task) {
            var node = panelBody.querySelector('[data-task="' + task.key + '"]');
            if (!node) {
                node = document.createElement('div');
                node.className = 'upload-task';
                node.setAttribute('data-task', task.key);
                node.innerHTML =
                    '<div class="upload-task-head">' +
                    '<span class="upload-task-name"></span>' +
                    '<span class="upload-task-controls"></span>' +
                    '</div>' +
                    '<div class="upload-task-bar"><div class="upload-task-fill"></div></div>' +
                    '<div class="upload-task-meta">' +
                    '<span class="upload-task-size"></span>' +
                    '<span class="upload-task-status"></span>' +
                    '</div>';
                node.querySelector('.upload-task-name').textContent = task.title;
                panelBody.appendChild(node);
            }

            node.classList.toggle('is-done', task.status === 'done');
            node.classList.toggle('is-error', task.status === 'error');
            node.classList.toggle('is-paused', task.status === 'paused');
            node.querySelector('.upload-task-fill').style.width = percent(task).toFixed(1) + '%';

            var sizeEl = node.querySelector('.upload-task-size');
            if (task.status === 'done' && task.postUrl) {
                sizeEl.innerHTML = '';
                var link = document.createElement('a');
                link.href = task.postUrl;
                link.textContent = '查看作品 →';
                sizeEl.appendChild(link);
            } else {
                sizeEl.textContent = fmtSize(uploadedBytes(task)) + ' / ' + fmtSize(task.file.size);
            }
            node.querySelector('.upload-task-status').textContent = task.statusText;

            var controls = node.querySelector('.upload-task-controls');
            controls.innerHTML = '';
            if (task.status === 'uploading' || task.status === 'queued') {
                controls.appendChild(mkBtn('暂停', function () { pauseTask(task); }));
                controls.appendChild(mkBtn('取消', function () { cancelTask(task); }));
            } else if (task.status === 'paused') {
                controls.appendChild(mkBtn('继续', function () { resumeTask(task); }));
                controls.appendChild(mkBtn('取消', function () { cancelTask(task); }));
            } else if (task.status === 'error') {
                controls.appendChild(mkBtn('重试', function () { resumeTask(task); }));
                controls.appendChild(mkBtn('移除', function () { cancelTask(task); }));
            } else if (task.status === 'done') {
                controls.appendChild(mkBtn('移除', function () { removeTask(task); }));
            }
        });

        // 清掉已被移除的任务节点
        Array.prototype.forEach.call(panelBody.querySelectorAll('[data-task]'), function (node) {
            var key = node.getAttribute('data-task');
            if (!tasks.some(function (t) { return t.key === key; })) node.remove();
        });
    }

    function mkBtn(label, onClick) {
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'upload-task-btn';
        b.textContent = label;
        b.addEventListener('click', onClick);
        return b;
    }

    // ---------- 任务控制 ----------

    function pauseTask(task) {
        task.paused = true;
        task.status = 'paused';
        task.statusText = '已暂停';
        if (task.xhr) task.xhr.abort();
        render();
    }

    function resumeTask(task) {
        task.paused = false;
        task.status = 'queued';
        task.statusText = '排队中';
        task.error = '';
        render();
        pump();
    }

    function cancelTask(task) {
        task.paused = true;
        if (task.xhr) task.xhr.abort();
        abortUpload(task);
        removeTask(task);
    }

    function removeTask(task) {
        tasks = tasks.filter(function (t) { return t !== task; });
        render();
        if (!tasks.length && panel) panel.classList.remove('on');
    }

    // ---------- 续传提示 ----------

    async function loadResumable() {
        if (!ensurePanel()) return;
        try {
            var res = await fetch('/api/upload/resumable');
            if (!res.ok) return;
            var data = await res.json();
            var list = (data && data.uploads) || [];
            if (!list.length) return;

            resumeHint.innerHTML = '';
            var text = document.createElement('div');
            text.innerHTML = '有 <strong>' + list.length + '</strong> 个未完成的上传，重新选择同一个文件即可从断点继续：';
            resumeHint.appendChild(text);

            list.forEach(function (item) {
                var pct = Math.floor(item.received_chunks / item.total_chunks * 100);
                var row = document.createElement('div');
                row.style.marginTop = 'var(--spacing-xs)';
                row.textContent = item.filename + ' — 已传 ' + pct + '%';
                resumeHint.appendChild(row);

                var picker = document.createElement('input');
                picker.type = 'file';
                picker.style.display = 'none';
                picker.addEventListener('change', function () {
                    var file = picker.files && picker.files[0];
                    if (!file) return;
                    if (file.name !== item.filename || file.size !== item.size) {
                        toast('文件不匹配，请选择原来那个「' + item.filename + '」', 'error');
                        return;
                    }
                    var task = makeTask(file, {
                        title: item.title,
                        description: item.description,
                        uploadId: item.upload_id,
                        chunkSize: item.chunk_size,
                        totalChunks: item.total_chunks,
                        received: item.received_chunks
                    });
                    tasks.push(task);
                    row.remove();
                    btn.remove();
                    picker.remove();
                    if (!resumeHint.querySelector('input[type=file]')) resumeHint.innerHTML = '';
                    showPanel();
                    render();
                    pump();
                });
                var btn = mkBtn('选择文件继续', function () { picker.click(); });
                resumeHint.appendChild(btn);
                resumeHint.appendChild(picker);
            });

            showPanel();
        } catch (e) { /* 续传提示失败不影响正常上传 */ }
    }

    // ---------- 表单接管 ----------

    function attachForm(form) {
        var fileInput = form.querySelector('input[type="file"]');
        if (!fileInput) return;
        fileInput.setAttribute('multiple', 'multiple');

        form.addEventListener('submit', function (e) {
            e.preventDefault();

            var files = fileInput.files;
            if (!files || !files.length) {
                toast('请选择文件', 'error');
                return;
            }

            var titleInput = form.querySelector('[name="title"]');
            var descInput = form.querySelector('[name="description"]');
            var title = titleInput ? titleInput.value.trim() : '';
            var description = descInput ? descInput.value.trim() : '';

            for (var i = 0; i < files.length; i++) {
                // 多选时标题只对第一个生效，其余用各自的文件名
                tasks.push(makeTask(files[i], {
                    title: (i === 0 && title) ? title : files[i].name,
                    description: description
                }));
            }

            form.reset();
            var dialog = form.closest('dialog');
            if (dialog && dialog.open) dialog.close();

            showPanel();
            render();
            pump();
        });
    }

    // ---------- 启动 ----------

    document.addEventListener('DOMContentLoaded', function () {
        if (!ensurePanel()) return;

        Array.prototype.forEach.call(
            document.querySelectorAll('form[action="/upload"]'),
            attachForm
        );

        loadResumable();

        window.addEventListener('beforeunload', function (e) {
            if (tasks.some(isActive)) {
                e.preventDefault();
                e.returnValue = '还有文件正在上传，离开页面会中断（回来重选文件可以续传）';
                return e.returnValue;
            }
        });
    });

    window.ShareHubUploader = {
        enqueue: function (file, meta) {
            tasks.push(makeTask(file, meta || {}));
            showPanel();
            render();
            pump();
        },
        tasks: function () { return tasks.slice(); }
    };
})();
