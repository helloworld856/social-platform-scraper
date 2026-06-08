"""热更新模块。

点击更新提示后，通过 git pull 拉取最新代码，
完成后自动重启应用。
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_hot_update() -> tuple[bool, str]:
    """
    执行 git pull 拉取最新代码。

    在项目根目录执行 git pull origin main，
    返回 (成功与否, 消息)。
    """
    try:
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            output = result.stdout.strip() or "代码已是最新。"
            logger.info("git pull 成功：%s", output)
            return (True, output)
        else:
            error = result.stderr.strip()
            logger.error("git pull 失败：%s", error)
            return (False, f"更新失败：{error}")
    except FileNotFoundError:
        msg = "未找到 git 命令，请确认 git 已安装并添加到 PATH。"
        logger.error(msg)
        return (False, msg)
    except subprocess.TimeoutExpired:
        msg = "git pull 超时（60 秒），请检查网络连接。"
        logger.error(msg)
        return (False, msg)
    except Exception as e:
        msg = f"更新异常：{e}"
        logger.error(msg)
        return (False, msg)


def restart_app() -> None:
    """启动新进程并退出当前进程，实现自动重启。"""
    logger.info("正在重启应用…")
    # 用当前 Python 解释器启动 main.py（新进程脱离父进程独立运行）
    subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=str(PROJECT_ROOT),
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    # 退出当前进程
    os._exit(0)
