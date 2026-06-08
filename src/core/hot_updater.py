"""热更新模块。

点击更新提示后，通过 git fetch + checkout 切换到指定 release tag，
完成后自动重启应用。git 不可用时回退到下载 zip 解压覆盖。
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUEST_TIMEOUT = 30


def run_hot_update(tag: str, repo_owner: str, repo_name: str) -> tuple[bool, str]:
    """
    更新到指定 release tag。优先 git，不可用时下载 zip。

    Returns:
        (success, message)
    """
    # 方式一：git fetch + checkout
    success, msg = _git_checkout(tag)
    if success:
        return (True, msg)

    logger.warning("git 方式失败，尝试下载 zip：%s", msg)
    # 方式二：下载 release zip 解压覆盖
    return _download_and_extract(tag, repo_owner, repo_name)


def _git_checkout(tag: str) -> tuple[bool, str]:
    """git fetch --tags && git checkout <tag>"""
    try:
        subprocess.run(
            ["git", "fetch", "origin", "--tags"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        result = subprocess.run(
            ["git", "checkout", f"v{tag.lstrip('v')}"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            logger.info("git checkout v%s 成功", tag)
            return (True, f"已切换到 v{tag}")
        else:
            return (False, result.stderr.strip())
    except FileNotFoundError:
        return (False, "未找到 git 命令")
    except subprocess.TimeoutExpired:
        return (False, "git 操作超时")
    except Exception as e:
        return (False, str(e))


def _download_and_extract(tag: str, repo_owner: str, repo_name: str) -> tuple[bool, str]:
    """下载 release 源码 zip 并解压覆盖。"""
    zip_url = f"https://github.com/{repo_owner}/{repo_name}/archive/refs/tags/v{tag.lstrip('v')}.zip"
    logger.info("正在下载：%s", zip_url)

    try:
        resp = requests.get(zip_url, timeout=REQUEST_TIMEOUT, stream=True)
        resp.raise_for_status()
    except Exception as e:
        return (False, f"下载失败：{e}")

    # 下载到临时文件
    tmp_dir = tempfile.mkdtemp(prefix="scraper_update_")
    zip_path = os.path.join(tmp_dir, "update.zip")
    try:
        with open(zip_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        # 解压到临时目录
        extract_dir = os.path.join(tmp_dir, "extracted")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        # zip 内有一个顶层目录，找到它
        inner_dirs = [d for d in Path(extract_dir).iterdir() if d.is_dir()]
        if not inner_dirs:
            return (False, "解压后未找到源码目录")
        src_dir = inner_dirs[0]

        # 覆盖项目文件（保留 .env, user_data/, output/）
        _preserve_and_copy(src_dir, PROJECT_ROOT)

        shutil.rmtree(tmp_dir, ignore_errors=True)
        logger.info("zip 解压覆盖完成")
        return (True, f"已更新到 v{tag}")
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return (False, f"解压覆盖失败：{e}")


def _preserve_and_copy(src: Path, dst: Path) -> None:
    """将 src 目录内容覆盖到 dst，保留用户数据。"""
    preserve = {".env", "user_data", "output"}
    for item in src.iterdir():
        if item.name in preserve:
            continue
        target = dst / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def restart_app() -> None:
    """启动新进程并退出当前进程，实现自动重启。"""
    logger.info("正在重启应用…")
    subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=str(PROJECT_ROOT),
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    os._exit(0)
