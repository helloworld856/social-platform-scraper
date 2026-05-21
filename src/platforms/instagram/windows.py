from __future__ import annotations

from src.core import DEFAULT_X_CDP_URL
from src.ui.base import FieldSpec, SimpleToolWindow


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


class InstagramProfileWorksWindow(SimpleToolWindow):
    def __init__(self) -> None:
        super().__init__(
            "Instagram 作者主页作品采集",
            [
                FieldSpec(
                    "profile_urls",
                    "作者主页链接，每行一个",
                    kind="multiline",
                    placeholder="https://www.instagram.com/username/",
                    required=True,
                ),
                FieldSpec("max_works", "每个作者最多作品数", kind="int", default=10000, minimum=1, maximum=100000),
                FieldSpec("max_scrolls", "每个主页最大滚动次数", kind="int", default=160, minimum=1, maximum=5000),
            ],
            height=520,
        )

    def validate_values(self, values):
        if not _lines(values["profile_urls"]):
            raise ValueError("至少需要输入一个 Instagram 作者主页链接。")

    def run_task(self, values, log_callback, finish_callback, stop_event):
        from src.platforms.instagram.works import run_instagram_profile_works_spider

        return run_instagram_profile_works_spider(
            values["profile_urls"],
            DEFAULT_X_CDP_URL,
            int(values["max_works"]),
            int(values["max_scrolls"]),
            log_callback,
            finish_callback,
            stop_event,
        )
