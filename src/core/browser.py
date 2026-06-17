"""
浏览器控制模块，负责在 Windows 环境下查找、自动启动 Chrome 进程，并通过 Playwright 的 CDP (Chrome DevTools Protocol) 接口进行连接，支持持久化用户数据以保持登录态。
"""

from __future__ import annotations

import atexit
import logging
import os
import subprocess
import time
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from src.core.app_logging import log_line

logger = logging.getLogger(__name__)

# 默认 CDP 调试接口地址
DEFAULT_X_CDP_URL = "http://localhost:9222"
DEFAULT_TIKTOK_CDP_URL = "http://localhost:9222"

# 默认的 Chrome 安装路径列表，通常用于 64 位或 32 位系统默认安装位置
DEFAULT_CHROME_PATHS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)

# 保存自动拉起的 Chrome 子进程实例，以便在退出时进行清理
_chrome_processes: list[subprocess.Popen] = []


def _cleanup_chrome():
    """
    进程退出时的清理勾子，确保自动启动的 Chrome 进程被正确终止，避免后台残留。
    """
    global _chrome_processes
    for p in _chrome_processes:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
    _chrome_processes.clear()


# 注册 Python 退出钩子
atexit.register(_cleanup_chrome)


def build_cdp_url(port_or_url: str | int) -> str:
    """
    将端口号或简写 URL 规范化为完整的 HTTP CDP 连接地址。

    Args:
        port_or_url: 端口号（如 9222）或已是完整地址

    Returns:
        str: 规范化的 HTTP 链接
    """
    value = str(port_or_url).strip()
    if not value:
        raise ValueError("CDP port or URL is required.")

    if value.startswith("http://") or value.startswith("https://"):
        return value

    return f"http://localhost:{value}"


def debug_port_from_cdp_url(port_or_url: str | int) -> str:
    """
    从给定的 CDP 端口或 URL 中解析提取出单纯的端口号。

    Args:
        port_or_url: 端口号或 CDP 链接

    Returns:
        str: 端口号或 netloc 串
    """
    cdp_url = build_cdp_url(port_or_url)
    parsed = urlparse(cdp_url)
    if parsed.port is not None:
        return str(parsed.port)
    return parsed.netloc or cdp_url


def get_workspace_root():
    """
    获取工作空间根目录。采用延迟导入以避免与 output 模块产生循环引用。
    """
    from src.core.output import get_workspace_root

    return get_workspace_root()


def get_chrome_user_data_dir() -> str:
    """
    获取 Chrome 缓存及用户登录信息的存储路径（默认存放在 workspace/user_data/ 目录下）。

    Returns:
        str: 绝对路径字符串
    """
    user_data_dir = get_workspace_root() / "user_data"
    user_data_dir.mkdir(parents=True, exist_ok=True)
    return str(user_data_dir)


def find_chrome_executable() -> str:
    """
    自动查找系统中的 Chrome 可执行文件路径。
    依次检测默认的安装路径以及用户本地应用数据目录 (LOCALAPPDATA)。

    Returns:
        str: 找到的 Chrome 路径，若均未找到则退避返回 "chrome.exe"
    """
    for path in DEFAULT_CHROME_PATHS:
        if os.path.exists(path):
            return path

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        local_chrome = os.path.join(local_app_data, "Google", "Chrome", "Application", "chrome.exe")
        if os.path.exists(local_chrome):
            return local_chrome

    return "chrome.exe"


def chrome_launch_hint(port_or_url: str | int) -> str:
    """
    生成在命令行中手动启动 Chrome 的提示命令，方便用户排查 CDP 问题。
    """
    return (
        f'"{find_chrome_executable()}" '
        f"--remote-debugging-port={debug_port_from_cdp_url(port_or_url)} "
        "--remote-allow-origins=* "
        f'--user-data-dir="{get_chrome_user_data_dir()}"'
    )


def is_cdp_available(port_or_url: str | int, timeout: float = 1.0) -> bool:
    """
    检测给定的 CDP 调试地址是否已经可用（通过请求 JSON 状态端点进行确认）。

    Args:
        port_or_url: CDP 端口或连接地址
        timeout: 超时时长（秒）

    Returns:
        bool: 是否可用
    """
    cdp_url = build_cdp_url(port_or_url).rstrip("/")
    try:
        with urlopen(f"{cdp_url}/json/version", timeout=timeout) as response:
            return response.status == 200
    except (OSError, ValueError):
        return False


def launch_chrome_for_cdp(port_or_url: str | int) -> subprocess.Popen:
    """
    以子进程的方式在后台启动带有 CDP 调试端口的 Chrome 浏览器。

    Args:
        port_or_url: 调试端口

    Returns:
        subprocess.Popen: 启动的子进程实例
    """
    global _chrome_processes
    chrome_path = find_chrome_executable()
    port = debug_port_from_cdp_url(port_or_url)
    user_data_dir = get_chrome_user_data_dir()
    
    # 清除向 Chrome 传递的环境变量中的 HTTP_PROXY 以免影响 Playwright 浏览器
    chrome_env = os.environ.copy()
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        chrome_env.pop(k, None)

    p = subprocess.Popen(
        [
            chrome_path,
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        env=chrome_env,
        # CREATE_NO_WINDOW 避免在 Windows GUI 界面下弹出黑色控制台闪窗
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    _chrome_processes.append(p)
    return p


def ensure_chrome_for_cdp(port_or_url: str | int, log_callback=None, wait_seconds: float = 12.0) -> None:
    """
    确保 Chrome CDP 调试端点已就绪。如果未就绪则自动拉起后台浏览器，并循环等待其加载就绪。

    Args:
        port_or_url: 端口或路径
        log_callback: 接收状态消息的日志回调函数
        wait_seconds: 最长等待就绪的超时时长（秒）
    """
    if is_cdp_available(port_or_url):
        return

    log_line(log_callback, "未检测到浏览器，正在自动启动 Chrome...")
    launch_chrome_for_cdp(port_or_url)

    # 循环检查 CDP 可用性，设定 12 秒上限是考虑到老旧机器上 Chrome 进程冷启动的延迟时间
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if is_cdp_available(port_or_url):
            return
        # 每隔 0.4 秒检查一次，平衡响应灵敏度与无用轮询开销
        time.sleep(0.4)

    raise RuntimeError(
        f"Chrome 未能在 {wait_seconds}s 内启动在端口 {debug_port_from_cdp_url(port_or_url)}。"
        f"请检查 Chrome 是否已安装且未被阻止。"
    )


def connect_existing_chromium(
    playwright: Any,
    port_or_url: str | int,
    *,
    context_index: int = 0,
    log_callback=None,
):
    """
    拉起（或确认）浏览器调试端口后，通过 Playwright 连接已有的 Chromium 实例。
    重用现有的上下文以避免清理已登录的会话，保留用户的 Cookies 和 Session。

    Args:
        playwright: sync_playwright 实例
        port_or_url: 端口或链接
        context_index: 获取哪一个已有的 browser context（通常为 0）
        log_callback: 日志输出回调

    Returns:
        (browser, context): Playwright 的 browser 和 context 实例
    """
    ensure_chrome_for_cdp(port_or_url, log_callback=log_callback)
    cdp_url = build_cdp_url(port_or_url)
    browser = playwright.chromium.connect_over_cdp(cdp_url)
    contexts = browser.contexts
    # 如果浏览器已有 Context 则直接复用以继承 Session 状态，否则新建一个
    context = contexts[context_index] if len(contexts) > context_index else browser.new_context()
    return browser, context

