/**
 * ShareHub 2.0 - Lightbox 图片灯箱
 */

(function() {
    'use strict';

    let lightbox;
    let currentImage;
    let allImages = [];
    let currentIndex = 0;

    // 初始化
    function init() {
        // 创建 lightbox 容器
        lightbox = document.createElement('div');
        lightbox.className = 'lightbox';
        lightbox.innerHTML = `
            <div class="lightbox-overlay"></div>
            <div class="lightbox-content">
                <button class="lightbox-close" aria-label="关闭">&times;</button>
                <button class="lightbox-prev" aria-label="上一张">‹</button>
                <button class="lightbox-next" aria-label="下一张">›</button>
                <div class="lightbox-image-container">
                    <img src="" alt="" class="lightbox-image" />
                </div>
                <div class="lightbox-caption"></div>
            </div>
        `;
        document.body.appendChild(lightbox);

        // 绑定事件
        lightbox.querySelector('.lightbox-close').addEventListener('click', close);
        lightbox.querySelector('.lightbox-overlay').addEventListener('click', close);
        lightbox.querySelector('.lightbox-prev').addEventListener('click', showPrev);
        lightbox.querySelector('.lightbox-next').addEventListener('click', showNext);

        // 键盘导航
        document.addEventListener('keydown', handleKeyboard);

        // 为所有图片添加点击事件
        attachToImages();
    }

    // 为图片添加点击事件
    function attachToImages() {
        // 选择所有可点击的图片（gallery 中的图片）
        const galleryImages = document.querySelectorAll('.gallery-item img, .post-media img');

        allImages = Array.from(galleryImages);

        allImages.forEach((img, index) => {
            // 跳过已处理的图片
            if (img.hasAttribute('data-lightbox-enabled')) return;

            img.setAttribute('data-lightbox-enabled', 'true');
            img.style.cursor = 'pointer';

            img.addEventListener('click', function(e) {
                // 如果图片在链接中，阻止默认行为
                const link = img.closest('a');
                if (link) {
                    e.preventDefault();
                    e.stopPropagation();
                }

                currentIndex = index;
                open(img);
            });
        });
    }

    // 打开 lightbox
    function open(img) {
        currentImage = img;

        const lightboxImg = lightbox.querySelector('.lightbox-image');
        const caption = lightbox.querySelector('.lightbox-caption');

        lightboxImg.src = img.src;
        lightboxImg.alt = img.alt || '';

        caption.textContent = img.alt || '';

        lightbox.classList.add('lightbox--active');
        document.body.style.overflow = 'hidden';

        // 更新导航按钮状态
        updateNavButtons();
    }

    // 关闭 lightbox
    function close() {
        lightbox.classList.remove('lightbox--active');
        document.body.style.overflow = '';
    }

    // 显示上一张
    function showPrev() {
        if (currentIndex > 0) {
            currentIndex--;
            open(allImages[currentIndex]);
        }
    }

    // 显示下一张
    function showNext() {
        if (currentIndex < allImages.length - 1) {
            currentIndex++;
            open(allImages[currentIndex]);
        }
    }

    // 更新导航按钮状态
    function updateNavButtons() {
        const prevBtn = lightbox.querySelector('.lightbox-prev');
        const nextBtn = lightbox.querySelector('.lightbox-next');

        prevBtn.style.display = currentIndex > 0 ? 'block' : 'none';
        nextBtn.style.display = currentIndex < allImages.length - 1 ? 'block' : 'none';
    }

    // 键盘导航
    function handleKeyboard(e) {
        if (!lightbox.classList.contains('lightbox--active')) return;

        switch(e.key) {
            case 'Escape':
                close();
                break;
            case 'ArrowLeft':
                showPrev();
                break;
            case 'ArrowRight':
                showNext();
                break;
        }
    }

    // 当 DOM 加载完成时初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // 导出到全局
    window.Lightbox = {
        init: init,
        open: open,
        close: close
    };
})();
