/* A tiny interaction layer: no animation framework, no permanent frame loop. */
(() => {
  'use strict';
  const root = document.documentElement;
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const finePointer = matchMedia('(hover: hover) and (pointer: fine)');
  const connection = navigator.connection;
  const scene = document.getElementById('mascot-scene');
  const mascot = document.getElementById('mascot-greet');
  const motionButton = document.getElementById('motion-toggle');
  let manualPause = false;
  try { manualPause = localStorage.getItem('sharehub-motion') === 'off'; } catch (_) { /* Storage may be unavailable. */ }
  const quiet = () => manualPause || reducedMotion.matches || !!connection?.saveData;
  function applyMotion() {
    root.dataset.motion = quiet() ? 'off' : 'on';
    if (motionButton) {
      motionButton.textContent = reducedMotion.matches || connection?.saveData ? '已减少动效' : manualPause ? '开启动效' : '暂停动效';
      motionButton.setAttribute('aria-pressed', String(quiet()));
      motionButton.disabled = reducedMotion.matches || !!connection?.saveData;
    }
    if (quiet()) resetTilt();
    stopPreviews();
  }
  const previewVideos = [...document.querySelectorAll('video[data-preview-src]')];
  function stopPreviews() {
    previewVideos.forEach(video => { video.pause(); video.parentElement.classList.remove('is-playing'); });
  }
  function resetTilt() {
    if (!mascot) return;
    mascot.style.removeProperty('--muse-x');
    mascot.style.removeProperty('--muse-y');
  }
  applyMotion();
  reducedMotion.addEventListener('change', applyMotion);
  connection?.addEventListener('change', applyMotion);
  motionButton?.addEventListener('click', () => {
    manualPause = !manualPause;
    try { localStorage.setItem('sharehub-motion', manualPause ? 'off' : 'on'); } catch (_) {}
    applyMotion();
  });
  function visibilityChanged() {
    root.toggleAttribute('data-page-hidden', document.hidden);
    if (document.hidden) { stopPreviews(); resetTilt(); }
  }
  document.addEventListener('visibilitychange', visibilityChanged);
  visibilityChanged();
  if (scene && 'IntersectionObserver' in window) {
    new IntersectionObserver(entries => {
      scene.classList.toggle('scene-paused', !entries[0].isIntersecting);
      if (!entries[0].isIntersecting) resetTilt();
    }, {threshold: .1}).observe(scene);
  }
  if (mascot) {
    let frame = 0;
    mascot.addEventListener('pointermove', event => {
      if (quiet() || !finePointer.matches || frame) return;
      const x = event.clientX, y = event.clientY;
      frame = requestAnimationFrame(() => {
        frame = 0;
        if (quiet() || !mascot.matches(':hover')) return;
        const bounds = scene.getBoundingClientRect();
        mascot.style.setProperty('--muse-x', `${Math.max(-5, Math.min(5, (x - bounds.left - bounds.width / 2) / bounds.width * 10))}deg`);
        mascot.style.setProperty('--muse-y', `${Math.max(-3, Math.min(3, -(y - bounds.top - bounds.height / 2) / bounds.height * 6))}deg`);
      });
    }, {passive:true});
    mascot.addEventListener('pointerleave', () => { cancelAnimationFrame(frame); frame = 0; resetTilt(); });
    const greetings = ['嗨！送你一颗今天的灵感星星 ✦', '发现喜欢的作品，记得收藏哦。', '今天想创造怎样的小小宇宙？', '很高兴遇见你，一起探索吧！'];
    let greetingIndex = 0;
    mascot.addEventListener('click', () => {
      if (mascot.classList.contains('is-greeting')) return;
      document.getElementById('mascot-message').textContent = greetings[greetingIndex++ % greetings.length];
      if (quiet()) return;
      mascot.classList.add('is-greeting');
      const stars = [];
      for (let i = 0; i < 5; i++) {
        const star = document.createElement('span');
        star.className = 'greeting-star'; star.textContent = i % 2 ? '✧' : '✦'; star.setAttribute('aria-hidden', 'true');
        star.style.setProperty('--star-x', `${(i - 2) * 36}px`);
        star.style.setProperty('--star-y', `${-55 - (2 - Math.abs(i - 2)) * 27}px`);
        scene.appendChild(star); stars.push(star);
      }
      // One bounded timeout also cleans up if animation is disabled mid-greeting.
      setTimeout(() => { mascot.classList.remove('is-greeting'); stars.forEach(star => star.remove()); }, 1000);
    });
  }
  // Keep missing legacy thumbnails from looking like broken layout.
  function markMissingImage(image) {
    if (!(image instanceof HTMLImageElement) || !image.closest('.gallery-item')) return;
    image.classList.add('media-unavailable');
    image.closest('.gallery-item').classList.add('has-missing-preview');
  }
  document.addEventListener('error', event => markMissingImage(event.target), true);
  document.querySelectorAll('.gallery-item img').forEach(image => {
    if (image.complete && image.naturalWidth === 0) markMissingImage(image);
  });
  const tabs = [...document.querySelectorAll('[role="tab"][data-tab]')];
  function activateTab(tab) {
    stopPreviews();
    tabs.forEach(item => {
      const active = item === tab;
      item.classList.toggle('active', active);
      item.setAttribute('aria-selected', String(active));
      item.tabIndex = active ? 0 : -1;
      const panel = document.getElementById(item.getAttribute('aria-controls'));
      panel.hidden = !active; panel.classList.toggle('active', active);
    });
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => activateTab(tab));
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      else if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = tabs.length - 1;
      else return;
      event.preventDefault(); activateTab(tabs[next]); tabs[next].focus();
    });
  });
  // Video previews load only on deliberate hover/focus; touch opens the post normally.
  previewVideos.forEach(video => {
    const link = video.closest('a');
    const start = () => {
      if (quiet() || document.hidden || video.closest('[hidden]')) return;
      if (!video.getAttribute('src')) video.src = video.dataset.previewSrc;
      video.play().then(() => {
        if (quiet() || document.hidden || video.closest('[hidden]') || (!link.matches(':hover') && !link.matches(':focus'))) video.pause();
        else video.parentElement.classList.add('is-playing');
      }).catch(() => {});
    };
    const stop = () => { video.pause(); video.parentElement.classList.remove('is-playing'); };
    link.addEventListener('pointerenter', () => { if (finePointer.matches) start(); });
    link.addEventListener('pointerleave', stop);
    link.addEventListener('focus', start);
    link.addEventListener('blur', stop);
  });
  if (previewVideos.length && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if (!entry.isIntersecting) { entry.target.pause(); entry.target.parentElement.classList.remove('is-playing'); }
    }));
    previewVideos.forEach(video => observer.observe(video));
  }
})();
