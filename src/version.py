"""应用版本号定义。

优先从 git tag 读取当前版本（确保 git checkout 后版本号自动同步），
git 不可用时从 config/version.json 读取。

发布新版本前：
    1. 修改 config/version.json 中的版本号
    2. git tag v{版本号} && git push origin v{版本号}
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_VERSION_JSON = _PROJECT_ROOT / "config" / "version.json"


def _get_version_from_json() -> str:
    """从 JSON 配置读取版本号。"""
    try:
        data = json.loads(_VERSION_JSON.read_text(encoding="utf-8"))
        return data.get("version", "0.0.0")
    except Exception:
        return "0.0.0"


def _get_version() -> str:
    """优先 git tag，回退 JSON。"""
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
    return _get_version_from_json()


__version__ = _get_version()
