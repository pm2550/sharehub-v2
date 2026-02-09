"""媒体文件处理服务"""

import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
from fastapi import HTTPException, UploadFile


def get_file_extension(filename: str) -> str:
    """获取文件扩展名（小写）"""
    return Path(filename).suffix.lower() if filename else ""


def validate_media_file(filename: str, content_type: str) -> Tuple[str, str]:
    """
    验证媒体文件类型

    Args:
        filename: 文件名
        content_type: Content-Type

    Returns:
        (media_type, extension) - ('image'或'video', 文件扩展名)

    Raises:
        HTTPException: 不支持的文件类型
    """
    ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    ALLOWED_VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v"}

    ext = get_file_extension(filename)
    ctype = (content_type or "").lower()

    if ext in ALLOWED_IMAGE_EXT or ctype.startswith("image/"):
        return "image", ext
    elif ext in ALLOWED_VIDEO_EXT or ctype.startswith("video/"):
        return "video", ext
    else:
        raise HTTPException(
            status_code=400,
            detail="Only common image/video formats are supported"
        )


async def validate_and_read_upload(
    file: UploadFile, max_size_mb: int, allowed_extensions: set
) -> Tuple[bytes, str]:
    """
    验证并读取上传文件

    Args:
        file: 上传文件
        max_size_mb: 最大文件大小（MB）
        allowed_extensions: 允许的扩展名集合

    Returns:
        (文件内容, 文件扩展名)

    Raises:
        HTTPException: 文件不合法
    """
    ext = get_file_extension(file.filename or "")

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, detail=f"不支持的文件类型: {ext}"
        )

    # 分块读取，检查大小
    max_bytes = max_size_mb * 1024 * 1024
    chunks = []
    total = 0

    while True:
        chunk = await file.read(1024 * 1024)  # 1MB chunks
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413, detail=f"文件大小超过限制 ({max_size_mb}MB)"
            )
        chunks.append(chunk)

    return b"".join(chunks), ext


def save_media_file(content: bytes, ext: str, media_dir: str, subdir: str = "originals") -> str:
    """
    保存媒体文件

    Args:
        content: 文件内容
        ext: 文件扩展名
        media_dir: 媒体目录
        subdir: 子目录名

    Returns:
        相对路径（相对于media_dir）
    """
    filename = f"{uuid.uuid4().hex}{ext}"
    rel_path = f"{subdir}/{filename}"
    full_path = os.path.join(media_dir, rel_path)

    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    with open(full_path, "wb") as f:
        f.write(content)

    return rel_path


def generate_thumbnails(original_path: str, media_dir: str, sizes: dict = None) -> dict:
    """
    生成缩略图

    Args:
        original_path: 原图完整路径
        media_dir: 媒体目录
        sizes: 尺寸字典，例如 {"sm": (300, 300), "md": (600, 600)}

    Returns:
        {size_key: relative_path} 字典
    """
    if sizes is None:
        sizes = {"sm": (300, 300), "md": (600, 600)}

    try:
        img = Image.open(original_path)
        img = img.convert("RGB")  # 转换为RGB（去除透明通道）

        stem = uuid.uuid4().hex
        thumbs = {}

        for key, size in sizes.items():
            thumb = img.copy()
            thumb.thumbnail(size, Image.Resampling.LANCZOS)

            rel_path = f"thumbnails/{stem}_{key}.webp"
            full_path = os.path.join(media_dir, rel_path)

            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            thumb.save(full_path, "WEBP", quality=82)

            thumbs[key] = rel_path

        return thumbs

    except Exception as e:
        # 缩略图生成失败不应阻塞上传
        print(f"Warning: Failed to generate thumbnails: {e}")
        return {}


def strip_exif(image_path: str):
    """
    清除图片EXIF数据（保护隐私）

    Args:
        image_path: 图片完整路径
    """
    try:
        img = Image.open(image_path)
        # 清除EXIF的方式：重新保存时不带EXIF
        data = list(img.getdata())
        image_without_exif = Image.new(img.mode, img.size)
        image_without_exif.putdata(data)
        image_without_exif.save(image_path)
    except Exception as e:
        # EXIF清除失败不应阻塞上传
        print(f"Warning: Failed to strip EXIF: {e}")


def get_video_duration(input_path: str) -> float:
    """
    获取视频时长（秒）

    Returns:
        视频时长秒数，失败返回 0
    """
    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        return 0

    cmd = [
        ffprobe_bin,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        str(input_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if proc.returncode == 0:
            import json
            info = json.loads(proc.stdout)
            return float(info.get("format", {}).get("duration", 0))
    except Exception:
        pass
    return 0


def transcode_video(input_path: str, output_path: str):
    """
    转码视频为兼容格式 (H.264 + AAC)

    Args:
        input_path: 输入视频路径
        output_path: 输出视频路径

    Raises:
        HTTPException: FFmpeg不可用或转码失败
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise HTTPException(
            status_code=500, detail="服务器未安装 ffmpeg，无法处理视频"
        )

    input_path = str(input_path)
    output_path = str(output_path)
    tmp_out = output_path + ".tmp.mp4"

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", input_path,
        "-map", "0:v:0",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-c:a", "aac",
        "-b:a", "128k",
        tmp_out,
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        if os.path.exists(tmp_out):
            os.unlink(tmp_out)
        err = (proc.stderr or proc.stdout or "ffmpeg failed").strip()
        raise HTTPException(
            status_code=400, detail=f"视频转码失败: {err[-500:]}"
        )

    # 成功，替换为最终文件
    shutil.move(tmp_out, output_path)


def delete_media_file(media_dir: str, rel_path: str):
    """
    删除媒体文件

    Args:
        media_dir: 媒体目录
        rel_path: 相对路径
    """
    if not rel_path:
        return

    full_path = os.path.join(media_dir, rel_path)
    if os.path.exists(full_path):
        try:
            os.unlink(full_path)
        except Exception as e:
            print(f"Warning: Failed to delete file {full_path}: {e}")
