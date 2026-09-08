"""RunPod Serverless 调用服务 (worker-sdxl)"""

import base64
import logging
import time
import requests
from typing import Optional

logger = logging.getLogger("sharehub.runpod")

RUNPOD_API_BASE = "https://api.runpod.ai/v2"


def is_runpod_available(api_key: str, endpoint_id: str) -> bool:
    """检查 RunPod 配置是否可用"""
    return bool(api_key and endpoint_id)


def call_runpod_sdxl(
    api_key: str,
    endpoint_id: str,
    prompt: str,
    negative_prompt: str = "",
    width: int = 768,
    height: int = 1024,
    steps: int = 40,
    guidance_scale: float = 5.5,
    scheduler: str = "K_EULER",
    seed: Optional[int] = None,
    timeout: int = 120,
) -> bytes:
    """
    调用 RunPod worker-sdxl 生成图片 (异步 /run + /status 轮询)

    Returns:
        PNG 图片字节数据

    Raises:
        RuntimeError: 调用失败
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "input": {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "num_inference_steps": steps,
            "guidance_scale": guidance_scale,
            "scheduler": scheduler,
            "num_images": 1,
        }
    }

    if seed is not None:
        payload["input"]["seed"] = seed

    # ── 1. 提交异步任务 (/run) ──
    run_url = f"{RUNPOD_API_BASE}/{endpoint_id}/run"
    logger.info(f"Submitting RunPod job: {width}x{height}, steps={steps}")

    resp = requests.post(run_url, json=payload, headers=headers, timeout=30)

    if resp.status_code != 200:
        error_text = resp.text[:500]
        logger.error(f"RunPod /run error {resp.status_code}: {error_text}")
        raise RuntimeError(f"RunPod API 错误 ({resp.status_code}): {error_text}")

    run_data = resp.json()
    job_id = run_data.get("id")
    status = run_data.get("status")

    if not job_id:
        logger.error(f"RunPod /run returned no job id: {run_data}")
        raise RuntimeError("RunPod 未返回任务 ID")

    logger.info(f"RunPod job submitted: id={job_id}, status={status}")

    # ── 2. 轮询任务状态 (/status) ──
    status_url = f"{RUNPOD_API_BASE}/{endpoint_id}/status/{job_id}"
    poll_interval = 2  # 秒
    deadline = time.time() + timeout

    while time.time() < deadline:
        time.sleep(poll_interval)

        try:
            status_resp = requests.get(status_url, headers=headers, timeout=15)
        except requests.RequestException as e:
            logger.warning(f"RunPod status poll error: {e}")
            continue

        if status_resp.status_code != 200:
            logger.warning(f"RunPod /status {status_resp.status_code}: {status_resp.text[:200]}")
            continue

        data = status_resp.json()
        status = data.get("status")

        if status in ("IN_QUEUE", "IN_PROGRESS"):
            continue

        if status == "COMPLETED":
            return _extract_image(data)

        if status in ("FAILED", "TIMED_OUT", "CANCELLED"):
            error = data.get("error", status)
            logger.error(f"RunPod job {job_id} failed: {error}")
            raise RuntimeError(f"RunPod 生成失败: {error}")

        # 未知状态
        logger.warning(f"RunPod job {job_id} unknown status: {status}")

    # 超时
    logger.error(f"RunPod job {job_id} timed out after {timeout}s")
    # 尝试取消
    try:
        requests.post(
            f"{RUNPOD_API_BASE}/{endpoint_id}/cancel/{job_id}",
            headers=headers, timeout=5
        )
    except Exception:
        pass
    raise RuntimeError(f"RunPod 生成超时 ({timeout}s)")


def _extract_image(data: dict) -> bytes:
    """从 RunPod 完成的响应中提取图片字节"""
    output = data.get("output")
    exec_time = data.get("executionTime", 0)

    if output is None:
        raise RuntimeError("RunPod 返回了空的 output")

    b64_str = None

    # 格式 1: output 是 dict — worker-sdxl 标准格式
    #   {"image_url": "data:image/png;base64,...", "images": [...], "seed": ...}
    if isinstance(output, dict):
        if output.get("image_url"):
            b64_str = output["image_url"]
        elif output.get("images") and len(output["images"]) > 0:
            b64_str = output["images"][0]
        elif output.get("image"):
            b64_str = output["image"]

    # 格式 2: output 是 list — 通用格式
    #   [{"image": "...", "seed": ...}]
    elif isinstance(output, list) and len(output) > 0:
        item = output[0]
        if isinstance(item, dict):
            b64_str = item.get("image") or item.get("image_url")
        elif isinstance(item, str):
            b64_str = item

    # 格式 3: output 本身是字符串 (纯 base64)
    elif isinstance(output, str):
        b64_str = output

    if not b64_str:
        logger.error(f"Cannot extract image from output: {str(output)[:300]}")
        raise RuntimeError("RunPod 返回了无法识别的图片格式")

    # 如果是 http URL，直接下载
    if b64_str.startswith("http"):
        logger.info(f"Downloading image from URL: {b64_str[:80]}...")
        img_resp = requests.get(b64_str, timeout=30)
        if img_resp.status_code != 200:
            raise RuntimeError(f"图片下载失败 ({img_resp.status_code})")
        img_bytes = img_resp.content
    else:
        # 去掉 data URI 前缀 (data:image/png;base64,...)
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        img_bytes = base64.b64decode(b64_str)

    if len(img_bytes) < 1000:
        logger.error(f"Image too small: {len(img_bytes)} bytes, raw output prefix: {str(output)[:200]}")
        raise RuntimeError("RunPod 返回的图片数据异常（太小）")

    logger.info(f"RunPod completed in {exec_time}ms, image={len(img_bytes)} bytes")
    return img_bytes


def get_user_daily_runpod_usage(conn, user_id: int) -> int:
    """获取用户今日 RunPod 已用次数"""
    row = conn.execute(
        "SELECT runpod_count FROM ai_daily_usage WHERE user_id = ? AND date = date('now')",
        (user_id,)
    ).fetchone()
    return row["runpod_count"] if row else 0


def increment_daily_runpod_usage(conn, user_id: int):
    """增加用户今日 RunPod 用量"""
    conn.execute(
        """
        INSERT INTO ai_daily_usage(user_id, date, runpod_count)
        VALUES (?, date('now'), 1)
        ON CONFLICT(user_id, date) DO UPDATE SET runpod_count = runpod_count + 1
        """,
        (user_id,)
    )


def get_user_daily_remaining(conn, user_id: int, daily_limit: int) -> int:
    """获取用户今日 RunPod 剩余次数"""
    used = get_user_daily_runpod_usage(conn, user_id)
    return max(0, daily_limit - used)
