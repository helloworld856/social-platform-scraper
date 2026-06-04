"""
系统日志配置模块，提供统一的控制台日志输出管理。
"""

from __future__ import annotations

import logging
import sys


# 系统日志根目录名称，用于在多模块间归集日志
LOGGER_ROOT = "crawler_tool"
_CONFIGURED = False


def setup_console_logging(level: int = logging.INFO) -> None:
    """
    初始化控制台日志配置。
    设置统一的日志格式，避免重复配置 handler。

    Args:
        level: 日志级别，默认为 logging.INFO
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    # 在非交互式或重定向环境下，sys.stdout 可能为 None，
    # 此时退避使用 sys.stderr 确保日志能够正常输出
    stream = sys.stdout or sys.stderr
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"))

    root = logging.getLogger(LOGGER_ROOT)
    root.setLevel(level)
    root.addHandler(handler)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的 Logger 实例，自动为其添加系统根日志前缀。

    Args:
        name: 模块或类的 Logger 名称

    Returns:
        logging.Logger: 包含前缀的 Logger 实例
    """
    setup_console_logging()
    # 如果传入的名称已经包含系统根日志前缀，直接使用，避免重复嵌套前缀
    if name.startswith(LOGGER_ROOT):
        return logging.getLogger(name)
    return logging.getLogger(f"{LOGGER_ROOT}.{name}")

