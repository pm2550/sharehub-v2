"""A1111 WebUI 按需启停管理器"""

import logging
import subprocess
import threading
import time
import requests

logger = logging.getLogger("sharehub.a1111_manager")

A1111_DIR = "/data/stable-diffusion-webui"
A1111_PORT = 8188
A1111_URL = f"http://127.0.0.1:{A1111_PORT}"
STARTUP_TIMEOUT = 300  # 最长等待启动 5 分钟
IDLE_SHUTDOWN = 600    # 空闲 10 分钟后自动关闭


class A1111Manager:
    """按需管理 A1111 进程：需要时启动，空闲后关闭"""

    def __init__(self):
        self._lock = threading.Lock()
        self._process: subprocess.Popen = None
        self._last_used: float = 0
        self._shutdown_timer: threading.Timer = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def ensure_running(self) -> str:
        """
        确保 A1111 正在运行并就绪，返回 API base URL。
        如果未运行则启动并等待就绪。
        """
        with self._lock:
            if self.is_running and self._health_check():
                self._touch()
                return A1111_URL

            logger.info("A1111 未运行，正在启动...")
            self._start()

        # 等待就绪（锁外等待，避免长时间持锁）
        if not self._wait_ready():
            raise RuntimeError(f"A1111 启动超时（{STARTUP_TIMEOUT}秒），请稍后重试")

        self._touch()
        logger.info("A1111 已就绪")
        return A1111_URL

    def stop(self):
        """停止 A1111"""
        with self._lock:
            self._cancel_shutdown_timer()
            if self.is_running:
                logger.info("正在停止 A1111...")
                self._process.terminate()
                try:
                    self._process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=5)
                self._process = None
                logger.info("A1111 已停止，内存已释放")

    def _start(self):
        """启动 A1111 进程"""
        if self.is_running:
            return

        self._process = subprocess.Popen(
            ["./venv/bin/python", "-u", "launch.py",
             "--listen", "--port", str(A1111_PORT),
             "--api", "--skip-torch-cuda-test",
             "--precision", "full", "--no-half",
             "--opt-sub-quad-attention", "--nowebui"],
            cwd=A1111_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info(f"A1111 进程已启动 (PID {self._process.pid})")

    def _health_check(self) -> bool:
        """快速检查 A1111 是否响应"""
        try:
            resp = requests.get(f"{A1111_URL}/sdapi/v1/sd-models", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def _wait_ready(self) -> bool:
        """等待 A1111 启动完成"""
        deadline = time.time() + STARTUP_TIMEOUT
        while time.time() < deadline:
            if not self.is_running:
                logger.error("A1111 进程意外退出")
                return False
            if self._health_check():
                return True
            time.sleep(5)
        return False

    def _touch(self):
        """记录最近使用时间，重置空闲关闭计时器"""
        self._last_used = time.time()
        self._cancel_shutdown_timer()
        self._shutdown_timer = threading.Timer(IDLE_SHUTDOWN, self._idle_shutdown)
        self._shutdown_timer.daemon = True
        self._shutdown_timer.start()

    def _cancel_shutdown_timer(self):
        if self._shutdown_timer:
            self._shutdown_timer.cancel()
            self._shutdown_timer = None

    def _idle_shutdown(self):
        """空闲超时后自动关闭"""
        elapsed = time.time() - self._last_used
        if elapsed >= IDLE_SHUTDOWN - 5:
            logger.info(f"A1111 空闲 {int(elapsed)}秒，自动关闭释放内存")
            self.stop()


# 全局单例
a1111_mgr = A1111Manager()
