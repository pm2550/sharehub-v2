/**
 * ShareHub 2.0 - 主题切换（暗色/亮色模式）
 */

(function() {
    'use strict';

    const STORAGE_KEY = 'sharehub-theme';
    const THEMES = ['light', 'dark', 'system'];

    // 获取当前主题
    function getCurrentTheme() {
        return localStorage.getItem(STORAGE_KEY) || 'system';
    }

    // 应用主题
    function applyTheme(theme) {
        if (theme === 'system') {
            document.documentElement.removeAttribute('data-theme');
        } else {
            document.documentElement.setAttribute('data-theme', theme);
        }
    }

    // 获取系统主题
    function getSystemTheme() {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    // 切换主题
    function toggleTheme() {
        const current = getCurrentTheme();
        const currentIndex = THEMES.indexOf(current);
        const nextIndex = (currentIndex + 1) % THEMES.length;
        const next = THEMES[nextIndex];

        localStorage.setItem(STORAGE_KEY, next);
        applyTheme(next);
        updateThemeIcon(next);

        // 显示提示
        if (window.Toast) {
            const messages = {
                'light': '🌞 已切换到亮色模式',
                'dark': '🌙 已切换到暗色模式',
                'system': '🖥️ 已切换到跟随系统'
            };
            Toast.show(messages[next], 'info', 2000);
        }
    }

    // 更新图标
    function updateThemeIcon(theme) {
        const button = document.getElementById('theme-toggle');
        if (!button) return;

        const icons = {
            'light': '☀️',
            'dark': '🌙',
            'system': '🖥️'
        };

        const actualTheme = theme === 'system' ? getSystemTheme() : theme;
        button.innerHTML = icons[actualTheme];
        button.setAttribute('aria-label', `当前主题: ${theme}`);
    }

    // 监听系统主题变化
    function watchSystemTheme() {
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addEventListener('change', () => {
            if (getCurrentTheme() === 'system') {
                applyTheme('system');
            }
        });
    }

    // 初始化
    function init() {
        const theme = getCurrentTheme();
        applyTheme(theme);

        document.addEventListener('DOMContentLoaded', () => {
            updateThemeIcon(theme);

            const button = document.getElementById('theme-toggle');
            if (button) {
                button.addEventListener('click', toggleTheme);
            }

            watchSystemTheme();
        });
    }

    // 页面加载前就应用主题，防止闪烁
    init();

    // 导出到全局
    window.ThemeManager = {
        toggle: toggleTheme,
        getCurrent: getCurrentTheme,
        apply: applyTheme
    };
})();
