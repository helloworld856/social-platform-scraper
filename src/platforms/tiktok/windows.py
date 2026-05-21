from __future__ import annotations

from pathlib import Path

from src.core import DEFAULT_TIKTOK_CDP_URL
from src.ui.base import FieldSpec, SimpleToolWindow


DEFAULT_START_DATE = "2025-05-06"
DEFAULT_END_DATE = "2026-05-06"


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


class TikTokKeywordWindow(SimpleToolWindow):
    def __init__(self) -> None:
        super().__init__(
            "TikTok 关键词视频基础信息",
            [
                FieldSpec("max_videos", "每个关键词最多视频数", kind="int", default=1000, minimum=1, maximum=5000),
                FieldSpec("max_candidates", "每个关键词最多检查候选数", kind="int", default=3000, minimum=1, maximum=20000),
                FieldSpec("start_date", "开始日期 YYYY-MM-DD", default=DEFAULT_START_DATE, required=True),
                FieldSpec("end_date", "结束日期 YYYY-MM-DD", default=DEFAULT_END_DATE, required=True),
                FieldSpec("keywords", "关键词，每行一个", kind="multiline", required=True),
            ],
        )

    def validate_values(self, values):
        from src.platforms.tiktok.keyword import parse_date_range

        if not _lines(values["keywords"]):
            raise ValueError("至少需要输入一个关键词。")
        parse_date_range(values["start_date"], values["end_date"])

    def run_task(self, values, log_callback, finish_callback, stop_event):
        from src.platforms.tiktok.keyword import run_tiktok_spider

        return run_tiktok_spider(
            _lines(values["keywords"]),
            int(values["max_videos"]),
            int(values["max_candidates"]),
            values["start_date"],
            values["end_date"],
            DEFAULT_TIKTOK_CDP_URL,
            log_callback,
            finish_callback,
            stop_event,
        )


class TikTokProfilesWindow(SimpleToolWindow):
    def __init__(self) -> None:
        super().__init__(
            "TikTok 博主信息提取",
            [FieldSpec("txt_path", "博主主页 TXT", kind="file", required=True)],
        )

    def validate_values(self, values):
        if not Path(values["txt_path"]).exists():
            raise ValueError("TXT 文件不存在。")

    def run_task(self, values, log_callback, finish_callback, stop_event):
        from src.platforms.tiktok.profiles import run_tiktok_profile_spider

        return run_tiktok_profile_spider(values["txt_path"], DEFAULT_TIKTOK_CDP_URL, log_callback, finish_callback, stop_event)


class TikTokProfileVideosWindow(SimpleToolWindow):
    def __init__(self) -> None:
        super().__init__(
            "TikTok 博主主页视频指标采集",
            [
                FieldSpec("txt_path", "博主主页 TXT", kind="file", required=True),
                FieldSpec("start_date", "开始日期 YYYY-MM-DD", default=DEFAULT_START_DATE, required=True),
                FieldSpec("end_date", "结束日期 YYYY-MM-DD", default=DEFAULT_END_DATE, required=True),
            ],
        )

    def validate_values(self, values):
        from src.platforms.tiktok.profile_videos import parse_date_range

        if not Path(values["txt_path"]).exists():
            raise ValueError("TXT 文件不存在。")
        parse_date_range(values["start_date"], values["end_date"])

    def run_task(self, values, log_callback, finish_callback, stop_event):
        from src.platforms.tiktok.profile_videos import run_tiktok_profile_videos_spider

        return run_tiktok_profile_videos_spider(
            values["txt_path"],
            values["start_date"],
            values["end_date"],
            DEFAULT_TIKTOK_CDP_URL,
            log_callback,
            finish_callback,
            stop_event,
        )


class TikTokContextWindow(SimpleToolWindow):
    def __init__(self) -> None:
        super().__init__(
            "TikTok 目标视频前后指标",
            [FieldSpec("txt_path", "视频链接 + 博主主页 TXT", kind="file", required=True)],
        )

    def validate_values(self, values):
        if not Path(values["txt_path"]).exists():
            raise ValueError("TXT 文件不存在。")

    def run_task(self, values, log_callback, finish_callback, stop_event):
        from src.platforms.tiktok.context import run_scraper

        return run_scraper(values["txt_path"], DEFAULT_TIKTOK_CDP_URL, log_callback, finish_callback, stop_event)


class TikTokCommentsWindow(SimpleToolWindow):
    def __init__(self) -> None:
        super().__init__(
            "TikTok 视频高赞主楼评论",
            [
                FieldSpec("max_scan_comments", "每个视频最多扫描主楼评论数", kind="int", default=500, minimum=100, maximum=10000),
                FieldSpec("txt_path", "视频链接 TXT", kind="file", required=True),
            ],
        )

    def validate_values(self, values):
        if not Path(values["txt_path"]).exists():
            raise ValueError("TXT 文件不存在。")

    def run_task(self, values, log_callback, finish_callback, stop_event):
        from src.platforms.tiktok.comments import run_tiktok_top_comments_spider

        return run_tiktok_top_comments_spider(
            values["txt_path"],
            DEFAULT_TIKTOK_CDP_URL,
            int(values["max_scan_comments"]),
            log_callback,
            finish_callback,
            stop_event,
        )
