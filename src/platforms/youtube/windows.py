from __future__ import annotations

from pathlib import Path

from src.ui.base import FieldSpec, SimpleToolWindow


DEFAULT_START_DATE = "2025-05-06"
DEFAULT_END_DATE = "2026-05-06"


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


class YouTubeKeywordWindow(SimpleToolWindow):
    def __init__(self) -> None:
        super().__init__(
            "YouTube 关键词视频基础信息",
            [
                FieldSpec("api_key", "Google API Key", required=True),
                FieldSpec("max_results", "每个关键词最多视频数", kind="int", default=1000, minimum=1, maximum=5000),
                FieldSpec("start_date", "开始日期 YYYY-MM-DD", default=DEFAULT_START_DATE, required=True),
                FieldSpec("end_date", "结束日期 YYYY-MM-DD", default=DEFAULT_END_DATE, required=True),
                FieldSpec("keywords", "关键词，每行一个", kind="multiline", required=True),
            ],
        )

    def validate_values(self, values):
        from src.platforms.youtube.keyword import parse_date_range

        if not _lines(values["keywords"]):
            raise ValueError("至少需要输入一个关键词。")
        parse_date_range(values["start_date"], values["end_date"])

    def run_task(self, values, log_callback, finish_callback, stop_event):
        from src.platforms.youtube.keyword import run_youtube_spider

        return run_youtube_spider(
            values["api_key"],
            _lines(values["keywords"]),
            int(values["max_results"]),
            values["start_date"],
            values["end_date"],
            log_callback,
            finish_callback,
            stop_event,
        )


class YouTubeProfilesWindow(SimpleToolWindow):
    def __init__(self) -> None:
        super().__init__(
            "YouTube 作者信息提取",
            [
                FieldSpec("api_key", "Google API Key", required=True),
                FieldSpec("txt_path", "作者主页 TXT", kind="file", required=True),
            ],
        )

    def validate_values(self, values):
        if not Path(values["txt_path"]).exists():
            raise ValueError("TXT 文件不存在。")

    def run_task(self, values, log_callback, finish_callback, stop_event):
        from src.platforms.youtube.profiles import run_channel_spider

        return run_channel_spider(values["api_key"], values["txt_path"], log_callback, finish_callback, stop_event)


class YouTubeContextWindow(SimpleToolWindow):
    def __init__(self) -> None:
        super().__init__(
            "YouTube 目标视频前后指标",
            [
                FieldSpec("api_key", "Google API Key", required=True),
                FieldSpec("txt_path", "视频链接 + 博主主页 TXT", kind="file", required=True),
            ],
        )

    def validate_values(self, values):
        if not Path(values["txt_path"]).exists():
            raise ValueError("TXT 文件不存在。")

    def run_task(self, values, log_callback, finish_callback, stop_event):
        from src.platforms.youtube.context import run_youtube_paired_context_spider

        return run_youtube_paired_context_spider(values["api_key"], values["txt_path"], log_callback, finish_callback, stop_event)


class YouTubeCommentsWindow(SimpleToolWindow):
    def __init__(self) -> None:
        super().__init__(
            "YouTube 视频高赞主楼评论",
            [
                FieldSpec("api_key", "Google API Key", required=True),
                FieldSpec("max_scan_comments", "每个视频最多扫描主楼评论数", kind="int", default=500, minimum=100, maximum=10000),
                FieldSpec("txt_path", "视频链接 TXT", kind="file", required=True),
            ],
        )

    def validate_values(self, values):
        if not Path(values["txt_path"]).exists():
            raise ValueError("TXT 文件不存在。")

    def run_task(self, values, log_callback, finish_callback, stop_event):
        from src.platforms.youtube.comments import run_youtube_top_comments_spider

        return run_youtube_top_comments_spider(
            values["api_key"],
            values["txt_path"],
            int(values["max_scan_comments"]),
            log_callback,
            finish_callback,
            stop_event,
        )
