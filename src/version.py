"""应用版本号定义。

优先从 git tag 读取当前版本（确保 git checkout 后版本号自动同步），
git 不可用时退回硬编码版本。

发布新版本前请修改 _FALLBACK_VERSION 并打 tag：
    git tag v{版本号} && git push origin v{版本号}
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_FALLBACK_VERSION = "1.0.0"
_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _get_version() -> str:
    """从 git tag 读取版本号，不可用时返回硬编码值。"""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            tag = result.stdout.strip().lstrip("v")
            if tag:
                return tag
    except Exception:
        pass
    return _FALLBACK_VERSION


__version__ = _get_version()
