// 拖拽上传功能
(function () {
    'use strict';

    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const preview = document.getElementById('preview');
    const uploadForm = document.getElementById('upload-form');
    const uploadBtn = document.getElementById('upload-btn');
    const progressBar = document.getElementById('upload-progress');
    const progressFill = document.getElementById('upload-progress-fill');
    const progressText = document.getElementById('upload-progress-text');

    if (!dropZone || !fileInput) return;

    // 阻止默认拖拽行为
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // 拖拽高亮效果
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });

    function highlight(e) {
        dropZone.classList.add('drag-over');
    }

    function unhighlight(e) {
        dropZone.classList.remove('drag-over');
    }

    // 处理拖拽上传
    dropZone.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    // 点击上传
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });

    function handleFiles(files) {
        if (files.length === 0) return;

        const file = files[0];
        fileInput.files = files; // 设置表单字段

        // 显示预览
        showPreview(file);
    }

    function showPreview(file) {
        if (!preview) return;

        preview.innerHTML = '';

        const reader = new FileReader();
        reader.onload = function (e) {
            const isImage = file.type.startsWith('image/');
            const isVideo = file.type.startsWith('video/');

            let element;
            if (isImage) {
                element = document.createElement('img');
                element.src = e.target.result;
                element.alt = file.name;
                element.style.maxWidth = '100%';
                element.style.maxHeight = '300px';
                element.style.borderRadius = 'var(--radius-md)';
            } else if (isVideo) {
                element = document.createElement('video');
                element.src = e.target.result;
                element.controls = true;
                element.style.maxWidth = '100%';
                element.style.maxHeight = '300px';
                element.style.borderRadius = 'var(--radius-md)';
            } else {
                element = document.createElement('p');
                element.textContent = '文件: ' + file.name;
            }

            preview.appendChild(element);

            // 添加文件信息
            const info = document.createElement('p');
            info.className = 'text-sm text-muted mt-sm';
            info.textContent = `${file.name} (${formatFileSize(file.size)})`;
            preview.appendChild(info);
        };

        reader.readAsDataURL(file);
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }

    // XHR 上传带进度条
    if (uploadForm && uploadBtn) {
        uploadForm.addEventListener('submit', function (e) {
            e.preventDefault();

            if (!fileInput.files || fileInput.files.length === 0) {
                Toast.show('请选择文件', 'error');
                return;
            }

            const formData = new FormData(uploadForm);
            const xhr = new XMLHttpRequest();

            // 显示进度条
            if (progressBar) {
                progressBar.style.display = 'block';
            }

            // 禁用提交按钮
            uploadBtn.disabled = true;
            uploadBtn.textContent = '上传中...';

            // 监听上传进度
            xhr.upload.addEventListener('progress', function (e) {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    if (progressFill) {
                        progressFill.style.width = percentComplete + '%';
                    }
                    if (progressText) {
                        progressText.textContent = Math.round(percentComplete) + '%';
                    }
                }
            });

            // 上传完成
            xhr.addEventListener('load', function () {
                if (xhr.status === 200 || xhr.status === 303) {
                    Toast.show('上传成功！', 'success');
                    // 尝试从响应头获取重定向URL
                    const redirectUrl = xhr.getResponseHeader('Location') || '/images';
                    setTimeout(() => {
                        window.location.href = redirectUrl;
                    }, 500);
                } else {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        Toast.show(response.detail || '上传失败', 'error');
                    } catch {
                        Toast.show('上传失败', 'error');
                    }
                    uploadBtn.disabled = false;
                    uploadBtn.textContent = '上传';
                }
            });

            // 上传出错
            xhr.addEventListener('error', function () {
                Toast.show('上传失败，请检查网络连接', 'error');
                uploadBtn.disabled = false;
                uploadBtn.textContent = '上传';
            });

            // 发送请求
            xhr.open('POST', uploadForm.action || '/upload');
            xhr.send(formData);
        });
    }
})();
