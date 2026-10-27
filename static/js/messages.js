/**
 * 私信页面交互逻辑
 * - 自动滚动到底部
 * - AJAX 发送消息（支持附带帖子卡片）
 * - 轮询新消息
 * - 帖子分享选择器
 */

(function () {
    'use strict';

    const messagesContainer = document.getElementById('chat-messages');
    const messageForm = document.getElementById('message-form');
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.querySelector('.send-btn');

    let isSending = false;
    let pollInterval = null;
    let lastMessageId = 0;

    // 附件相关
    const attachedPostId = document.getElementById('attached-post-id');
    const attachedPreview = document.getElementById('attached-post-preview');
    const attachedThumb = document.getElementById('attached-post-thumb');
    const attachedTitle = document.getElementById('attached-post-title');
    const removeAttachedBtn = document.getElementById('remove-attached-post');
    const sharePostBtn = document.getElementById('share-post-btn');

    // 弹窗相关
    const shareModal = document.getElementById('share-post-modal');
    const closeModalBtn = document.getElementById('close-share-modal');
    const shareSearchInput = document.getElementById('share-search-input');
    const sharePostList = document.getElementById('share-post-list');

    let searchTimer = null;

    // 初始化
    document.addEventListener('DOMContentLoaded', function () {
        if (!messagesContainer) return;

        scrollToBottom();
        setupInputHandlers();
        setupSharePost();

        // 获取最后一条消息ID用于轮询
        var allMsgRows = messagesContainer.querySelectorAll('.message-row');
        if (allMsgRows.length > 0) {
            lastMessageId = parseInt(allMsgRows[allMsgRows.length - 1].dataset.id || 0);
        }

        // 开始轮询 (5秒一次)
        pollInterval = setInterval(pollNewMessages, 5000);
    });

    // 页面卸载时清除轮询
    window.addEventListener('beforeunload', function () {
        if (pollInterval) clearInterval(pollInterval);
    });

    function scrollToBottom() {
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }

    function setupInputHandlers() {
        if (!messageInput) return;

        messageInput.addEventListener('input', function () {
            updateSendBtnState();
            messageInput.style.height = 'auto';
            messageInput.style.height = Math.min(messageInput.scrollHeight, 100) + 'px';
        });

        messageInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!sendBtn.disabled) {
                    messageForm.dispatchEvent(new Event('submit'));
                }
            }
        });

        if (messageForm) {
            messageForm.addEventListener('submit', handleSend);
        }
    }

    function updateSendBtnState() {
        var hasContent = messageInput && messageInput.value.trim().length > 0;
        var hasAttachment = attachedPostId && attachedPostId.value;
        sendBtn.disabled = !(hasContent || hasAttachment);
    }

    // ==================== 发送消息 ====================

    async function handleSend(e) {
        e.preventDefault();
        if (isSending) return;

        var content = messageInput.value.trim();
        var postId = attachedPostId ? attachedPostId.value : '';

        if (!content && !postId) return;

        var partnerUsername = messageForm.dataset.partner;
        if (!partnerUsername) return;

        isSending = true;
        sendBtn.disabled = true;

        try {
            var body = { content: content };
            if (postId) body.post_id = parseInt(postId);

            var response = await fetch('/messages/' + partnerUsername + '/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });

            var data = await response.json();

            if (data.success) {
                messageInput.value = '';
                messageInput.style.height = 'auto';
                clearAttachedPost();

                appendMessage(data, true);
                scrollToBottom();

                lastMessageId = data.message_id;
            } else {
                alert('发送失败: ' + (data.error || '未知错误'));
            }
        } catch (error) {
            console.error('Send error:', error);
            alert('网络错误，请重试');
        } finally {
            isSending = false;
            updateSendBtnState();
        }
    }

    // ==================== 轮询 ====================

    async function pollNewMessages() {
        if (document.hidden) return;
        var partnerUsername = messageForm ? messageForm.dataset.partner : null;
        if (!partnerUsername) return;

        try {
            var response = await fetch('/api/messages/' + partnerUsername + '/poll?after_id=' + lastMessageId);
            if (!response.ok) return;

            var data = await response.json();
            if (data.messages && data.messages.length > 0) {
                data.messages.forEach(function (msg) {
                    if (!msg.is_me) {
                        appendMessage(msg, false);
                        lastMessageId = Math.max(lastMessageId, msg.id);
                    }
                });
                scrollToBottom();
            }
        } catch (error) {
            console.error('Poll error:', error);
        }
    }

    // ==================== 渲染消息 ====================

    function appendMessage(msg, isMe) {
        var div = document.createElement('div');
        div.className = 'message-row ' + (isMe ? 'me' : 'other');
        div.dataset.id = msg.message_id || msg.id;

        // 头像
        var avatarHtml = '';
        if (!isMe) {
            var partnerAvatar = document.querySelector('.partner-info img');
            if (partnerAvatar) {
                avatarHtml = '<div class="message-avatar"><img src="' + partnerAvatar.src + '" class="avatar-xs"></div>';
            } else {
                avatarHtml = '<div class="message-avatar"><div class="avatar-placeholder-xs"></div></div>';
            }
        }

        // 帖子卡片
        var postCardHtml = '';
        var postData = msg.post;
        if (postData) {
            var mediaHtml = '';
            if (postData.media_type === 'video') {
                mediaHtml = (postData.thumbnail_path ? '<img src="/media/' + esc(postData.thumbnail_path) + '" alt="视频封面" class="shared-post-media" loading="lazy">' : '') + '<div class="play-badge">▶</div>';
            } else if (postData.media_type === 'file') {
                mediaHtml = '<span class="shared-post-media file-preview">文件</span>';
            } else if (postData.thumbnail_path) {
                mediaHtml = '<img src="/media/' + esc(postData.thumbnail_path) + '" alt="' + esc(postData.title) + '" class="shared-post-media" loading="lazy">';
            } else {
                mediaHtml = '<img src="/media/' + esc(postData.filename) + '" alt="' + esc(postData.title) + '" class="shared-post-media" loading="lazy">';
            }

            var metaText = '';
            if (postData.source === 'ai') metaText += '🤖 AI · ';
            metaText += (postData.media_type === 'image' ? '图片' : postData.media_type === 'video' ? '视频' : '文件') + ' · ❤️ ' + (postData.likes || 0);

            postCardHtml =
                '<a href="/post/' + postData.id + '" class="shared-post-card">' +
                    '<div class="shared-post-thumb">' + mediaHtml + '</div>' +
                    '<div class="shared-post-info">' +
                        '<div class="shared-post-title">' + esc(postData.title) + '</div>' +
                        '<div class="shared-post-meta">' + metaText + '</div>' +
                    '</div>' +
                '</a>';
        }

        // 文本
        var textHtml = '';
        var content = msg.content || '';
        if (content && content !== '[分享帖子]') {
            textHtml = '<div class="message-text">' + escapeHtml(content) + '</div>';
        } else if (!postData) {
            textHtml = '<div class="message-text">' + escapeHtml(content) + '</div>';
        }

        div.innerHTML =
            avatarHtml +
            '<div class="message-bubble">' +
                postCardHtml +
                textHtml +
                '<div class="message-meta">刚刚</div>' +
            '</div>';

        messagesContainer.appendChild(div);
    }

    // ==================== 帖子分享选择器 ====================

    function setupSharePost() {
        if (!sharePostBtn) return;

        sharePostBtn.addEventListener('click', function () {
            shareModal.style.display = 'flex';
            shareSearchInput.value = '';
            loadSharePosts('');
            shareSearchInput.focus();
        });

        if (closeModalBtn) {
            closeModalBtn.addEventListener('click', closeShareModal);
        }
        if (shareModal) {
            shareModal.addEventListener('click', function (e) {
                if (e.target === shareModal) closeShareModal();
            });
        }

        if (shareSearchInput) {
            shareSearchInput.addEventListener('input', function () {
                clearTimeout(searchTimer);
                searchTimer = setTimeout(function () {
                    loadSharePosts(shareSearchInput.value.trim());
                }, 300);
            });
        }

        if (removeAttachedBtn) {
            removeAttachedBtn.addEventListener('click', clearAttachedPost);
        }
    }

    function closeShareModal() {
        if (shareModal) shareModal.style.display = 'none';
    }

    async function loadSharePosts(query) {
        sharePostList.innerHTML = '<div class="share-loading">加载中...</div>';

        try {
            var res = await fetch('/api/messages/share-posts?q=' + encodeURIComponent(query));
            var data = await res.json();

            if (!data.posts || data.posts.length === 0) {
                sharePostList.innerHTML = '<div class="share-empty">没有找到帖子</div>';
                return;
            }

            sharePostList.innerHTML = '';
            data.posts.forEach(function (post) {
                var item = document.createElement('div');
                item.className = 'share-post-item';

                var badge = post.share_source === 'favorite' ? '🔖 收藏' : '📝 我的';
                var typeBadge = post.media_type === 'video' ? '🎬' : '📷';
                var aiBadge = post.source === 'ai' ? ' 🤖' : '';

                var thumbHtml = '';
                if (post.media_type === 'video') {
                    thumbHtml = post.thumbnail_path ? '<img src="' + esc(post.thumb_url) + '" alt="视频封面" class="share-thumb-img" loading="lazy"><div class="play-badge-sm">▶</div>' : '<div class="share-thumb-img file-preview" aria-label="视频">▶</div>';
                } else {
                    thumbHtml = '<img src="' + esc(post.thumb_url) + '" alt="' + esc(post.title) + '" class="share-thumb-img" loading="lazy">';
                }

                item.innerHTML =
                    '<div class="share-post-thumb-wrap">' + thumbHtml + '</div>' +
                    '<div class="share-post-detail">' +
                        '<div class="share-post-name">' + esc(post.title) + '</div>' +
                        '<div class="share-post-tags">' + badge + ' ' + typeBadge + aiBadge + '</div>' +
                    '</div>';

                item.addEventListener('click', function () {
                    selectPost(post);
                });
                sharePostList.appendChild(item);
            });
        } catch (e) {
            sharePostList.innerHTML = '<div class="share-empty">加载失败</div>';
        }
    }

    function selectPost(post) {
        attachedPostId.value = post.id;
        attachedThumb.src = post.thumb_url;
        attachedTitle.textContent = post.title;
        attachedPreview.style.display = 'block';
        closeShareModal();
        updateSendBtnState();
    }

    function clearAttachedPost() {
        if (attachedPostId) attachedPostId.value = '';
        if (attachedPreview) attachedPreview.style.display = 'none';
        if (attachedThumb) attachedThumb.src = '';
        if (attachedTitle) attachedTitle.textContent = '';
        updateSendBtnState();
    }

    // ==================== 工具函数 ====================

    function escapeHtml(text) {
        var d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }

    function esc(str) {
        if (!str) return '';
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

})();
