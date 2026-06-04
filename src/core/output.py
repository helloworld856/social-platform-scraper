"""
文件输出路径管理模块，提供规范化的工作空间、输出文件夹路径解析，支持针对不同平台分类存放。
"""

from __future__ import annotations

from pathlib import Path

# 社交平台别名与子目录映射关系，统一合并为规范名称（例如 twitter 和 x_platform 统一归入 x）
PLATFORM_DIRS = {
    "youtube": "youtube",
    "tiktok": "tiktok",
    "x": "x",
    "x_platform": "x",
    "twitter": "x",
    "data": "data",
}


def get_workspace_root() -> Path:
    """
    自动推导项目的根目录（即包含 requirements.txt 和 main.py 的那级目录）。
    """
    # __file__ 是 src/core/output.py，parents[2] 代表向上跳三级（0: core, 1: src, 2: 项目根目录）
    root = Path(__file__).resolve().parents[2]
    if not (root / "requirements.txt").exists() and not (root / "main.py").exists():
        raise RuntimeError(f"Workspace root not found at {root}")
    return root


def get_output_root() -> Path:
    """
    获取或创建统一输出文件的根目录（工作空间下的 output 目录）。
    """
    output_root = get_workspace_root() / "output"
    output_root.mkdir(parents=True, exist_ok=True)
    return output_root


def get_platform_output_dir(platform: str) -> Path:
    """
    根据平台标识获取或创建其对应的专属输出子目录。

    Args:
        platform: 平台名（如 'tiktok', 'youtube' 等）

    Returns:
        Path: 对应的 Path 对象
    """
    # 路径安全防护：防止恶意传入包含 '..' 或斜杠的文件名，绕过限定范围实施路径穿越攻击
    if ".." in platform or "/" in platform or "\\" in platform:
        raise ValueError(f"Invalid platform name: {platform}")
    folder_name = PLATFORM_DIRS.get(platform, platform)
    output_dir = get_output_root() / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def build_output_path(platform: str, filename: str) -> str:
    """
    构造完整的数据输出文件存储路径（绝对路径字符串）。

    Args:
        platform: 平台名
        filename: 目标文件名

    Returns:
        str: 拼接后的绝对文件路径
    """
    return str(get_platform_output_dir(platform) / filename)

