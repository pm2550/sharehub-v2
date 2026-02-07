/**
 * AI 队列状态轮询 - 替换页面自动刷新
 * 检测活跃任务并自动轮询状态更新
 */

(function() {
    'use strict';

    const AIPollHandler = {
        pollInterval: null,
        pollDelay: 3000, // 3秒轮询一次

        init() {
            // 检查页面是否有活跃的 AI 任务
            const activeJobs = document.querySelectorAll('.ai-job-status.active, .ai-job-status.running, .ai-job-status.pending');
            
            if (activeJobs.length > 0) {
                console.log(`检测到 ${activeJobs.length} 个活跃 AI 任务，启动轮询...`);
                this.startPolling();
            }
        },

        startPolling() {
            // 避免重复启动
            if (this.pollInterval) return;

            this.pollInterval = setInterval(() => {
                this.updateJobStatus();
            }, this.pollDelay);
        },

        stopPolling() {
            if (this.pollInterval) {
                clearInterval(this.pollInterval);
                this.pollInterval = null;
                console.log('AI 轮询已停止');
            }
        },

        async updateJobStatus() {
            try {
                // 简单方案：部分刷新队列区域
                const queueContainer = document.querySelector('.ai-queue-container');
                if (!queueContainer) {
                    this.stopPolling();
                    return;
                }

                // 获取当前页面 URL
                const response = await fetch(window.location.href, {
                    headers: {
                        'X-Requested-With': 'XMLHTTPRequest'
                    }
                });

                if (!response.ok) {
                    console.error('轮询失败');
                    return;
                }

                const html = await response.text();
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                
                const newQueue = doc.querySelector('.ai-queue-container');
                if (newQueue) {
                    queueContainer.innerHTML = newQueue.innerHTML;
                }

                // 检查是否还有活跃任务
                const activeJobs = document.querySelectorAll('.ai-job-status.active, .ai-job-status.running, .ai-job-status.pending');
                if (activeJobs.length === 0) {
                    Toast.show('所有 AI 任务已完成！', 'success');
                    this.stopPolling();
                }

            } catch (error) {
                console.error('更新队列状态失败:', error);
            }
        }
    };

    // 页面加载完成后初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => AIPollHandler.init());
    } else {
        AIPollHandler.init();
    }

    // 页面隐藏时停止轮询，显示时恢复
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            AIPollHandler.stopPolling();
        } else {
            AIPollHandler.init();
        }
    });
})();
