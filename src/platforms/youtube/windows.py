from __future__ import annotations

from src.ui.base import FieldSpec, SimpleToolWindow
from src.ui.config_dialog import ConfigParam


DEFAULT_START_DATE = "2025-05-06"
DEFAULT_END_DATE = "2026-05-06"


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


class YouTubeKeywordWindow(SimpleToolWindow):
    tool_id = "youtube_keyword_mining"

    def __init__(self) -> None:
        super().__init__(
            "YouTube 关键词搜索",
            [
                FieldSpec("api_key", "Google API Key(s) (支持多行或导入txt)", kind="text_or_file", required=True, placeholder="支持每行填写一个API Key，耗尽自动轮询"),
                FieldSpec("limit_time", "是否限制时间？", kind="combo", options=("是", "否"), default="是"),
                FieldSpec("start_date", "开始日期 YYYY-MM-DD", default=DEFAULT_START_DATE),
                FieldSpec("end_date", "结束日期 YYYY-MM-DD", default=DEFAULT_END_DATE),
                FieldSpec("keywords", "关键词，每行一个", kind="text_or_file", required=True, placeholder="每行一个关键词"),
                FieldSpec("get_comments", "是否获取视频评论信息？", kind="combo", options=("是", "否"), default="否"),
                FieldSpec("max_comments", "最多获取评论数", kind="int", default=100, minimum=10, maximum=10000),
                FieldSpec("enable_timer", "是否开启定时重复运行？", kind="combo", options=("否", "是"), default="否"),
                FieldSpec("timer_interval_minutes", "运行间隔 (分钟)", kind="int", default=60, minimum=1, maximum=10080),
                FieldSpec("timer_max_runs", "最大运行次数", kind="int", default=3, minimum=2, maximum=10000),
            ],
            height=760,
        )
        self.bind_field_visibility("limit_time", "是", ["start_date", "end_date"])
        self.bind_field_visibility("get_comments", "是", ["max_comments"])
        self.bind_field_visibility("enable_timer", "是", ["timer_interval_minutes", "timer_max_runs"])

    def validate_values(self, values):
        from src.platforms.youtube.keyword import parse_date_range

        if not _lines(values["keywords"]):
            raise ValueError("至少需要输入一个关键词。")
        if values.get("limit_time") == "是":
            parse_date_range(values["start_date"], values["end_date"])

    def tool_config_params(self):
        return [
            ConfigParam("max_results", "最多搜索结果数", kind="int", default=5000, minimum=1, maximum=5000),
            ConfigParam(
                "youtube_search_method",
                "搜索方式",
                kind="combo",
                options=("浏览器优先（省配额）", "仅API（消耗配额）"),
                default="浏览器优先（省配额）",
                tooltip="【重要】‘浏览器优先’模式利用浏览器在后台模拟搜索获取视频链接，可节省 99% 的 YouTube API 每日配额消耗！"
            ),
            ConfigParam("youtube_search_batch_size", "搜索每页条数", kind="int", default=50, minimum=1, maximum=50),
            ConfigParam("youtube_date_chunk_days", "日期切分粒度(天)", kind="int", default=7, minimum=1, maximum=30,
                        tooltip="YouTube API 单次搜索最多返回约 500 条。开启时间过滤时，会将日期范围按此天数切分为多个小区间分别检索，绕过 500 条上限。越小越精确但消耗更多配额。"),
            ConfigParam("youtube_date_chunk_hours", "日期切分粒度(小时)，留空则使用上方天数", kind="int", default=0, minimum=0, maximum=720,
                        tooltip="若填写（如 1），则按小时切分时间区间，优先级高于上方的天数粒度。适合短时间范围内大量视频的精确采集。0 或留空表示使用天数粒度。"),
            ConfigParam("youtube_video_batch_size", "视频详情每批条数", kind="int", default=50, minimum=1, maximum=50),
            ConfigParam("youtube_browser_scroll_px", "浏览器每次滚动像素", kind="int", default=2500, minimum=500, maximum=10000, step=100),
            ConfigParam("youtube_browser_scroll_delay", "浏览器滚动间隔(秒)", kind="float", default=1.0, minimum=0.2, maximum=5.0, step=0.1, decimals=1),
            ConfigParam("youtube_browser_max_scrolls", "浏览器最大滚动次数", kind="int", default=100, minimum=10, maximum=500),
            ConfigParam("youtube_browser_page_timeout", "浏览器页面加载超时(毫秒)", kind="int", default=45000, minimum=10000, maximum=120000, step=1000),
            ConfigParam("youtube_browser_no_new_limit", "浏览器无新内容停止阈值", kind="int", default=8, minimum=2, maximum=50),
            ConfigParam("comment_top_limit", "最多输出评论数", kind="int", default=100, minimum=1, maximum=500),
        ]

    def run_task(self, values, log_callback, finish_callback, stop_event, pause_event):
        from src.platforms.youtube.keyword import run_youtube_spider

        config = {k: v for k, v in values.items() if k.startswith("youtube_") or k in ("max_results", "comment_top_limit", "enable_timer", "timer_interval_minutes", "timer_max_runs")}
        return run_youtube_spider(
            _lines(values["api_key"]),
            _lines(values["keywords"]),
            int(values.get("max_results", 5000)),
            values["limit_time"],
            values["start_date"],
            values["end_date"],
            values["get_comments"],
            int(values["max_comments"]),
            log_callback,
            finish_callback,
            stop_event,
            config=config,
            pause_event=pause_event,
        )


class YouTubeProfilesWindow(SimpleToolWindow):
    def __init__(self) -> None:
        super().__init__(
            "YouTube 博主信息",
            [
                FieldSpec("api_key", "Google API Key(s) (支持多行或导入txt)", kind="text_or_file", required=True, placeholder="支持每行填写一个API Key，耗尽自动轮询"),
                FieldSpec("txt_path", "博主主页链接，每行一个", kind="text_or_file", required=True, placeholder="https://www.youtube.com/@username"),
            ],
        )

    def run_task(self, values, log_callback, finish_callback, stop_event, pause_event):
        from src.platforms.youtube.profiles import run_channel_spider

        return run_channel_spider(_lines(values["api_key"]), self._text_to_tempfile(values["txt_path"]), log_callback, finish_callback, stop_event, pause_event=pause_event)


class YouTubeContextWindow(SimpleToolWindow):
    tool_id = "youtube_paired_context_metrics"

    def __init__(self) -> None:
        super().__init__(
            "YouTube 视频上下文数据",
            [
                FieldSpec("api_key", "Google API Key(s) (支持多行或导入txt)", kind="text_or_file", required=True, placeholder="支持每行填写一个API Key，耗尽自动轮询"),
                FieldSpec("txt_path", "视频链接 + 博主主页，每行一对", kind="text_or_file", required=True, placeholder="视频链接 博主主页链接"),
            ],
        )

    def tool_config_params(self):
        return [
            ConfigParam("context_size", "目标视频前后各取几条", kind="int", default=5, minimum=1, maximum=20),
            ConfigParam("max_upload_pages", "最多翻页数", kind="int", default=200, minimum=10, maximum=1000),
        ]

    def run_task(self, values, log_callback, finish_callback, stop_event, pause_event):
        from src.platforms.youtube.context import run_youtube_paired_context_spider

        config = {k: v for k, v in values.items() if k in ("context_size", "max_upload_pages")}
        return run_youtube_paired_context_spider(_lines(values["api_key"]), self._text_to_tempfile(values["txt_path"]), log_callback, finish_callback, stop_event, config=config, pause_event=pause_event)


class YouTubeChannelWorksWindow(SimpleToolWindow):
    tool_id = "youtube_channel_works"

    def __init__(self) -> None:
        super().__init__(
            "YouTube 博主作品采集",
            [
                FieldSpec("api_key", "Google API Key(s) (支持多行或导入txt)", kind="text_or_file", required=True, placeholder="支持每行填写一个API Key，耗尽自动轮询"),
                FieldSpec(
                    "channel_urls",
                    "博主主页链接，每行一个",
                    kind="text_or_file",
                    placeholder="https://www.youtube.com/@username",
                    required=True,
                ),
                FieldSpec("collect_target", "采集目标", kind="combo", options=("全部", "仅视频与Shorts", "仅帖子 (Posts)"), default="全部"),
                FieldSpec("limit_time", "是否限制时间？", kind="combo", options=("是", "否"), default="否"),
                FieldSpec("start_date", "开始日期 YYYY-MM-DD", default=DEFAULT_START_DATE),
                FieldSpec("end_date", "结束日期 YYYY-MM-DD", default=DEFAULT_END_DATE),
                FieldSpec("get_comments", "是否获取视频评论信息？", kind="combo", options=("是", "否"), default="否"),
                FieldSpec("max_comments", "最多获取评论数", kind="int", default=100, minimum=10, maximum=10000),
                FieldSpec("verify_video_type", "是否精确验证视频长短类型？", kind="combo", options=("是", "否"), default="是"),
                FieldSpec("verify_max_scrolls", "验证最大滚动次数", kind="int", default=20, minimum=1, maximum=500),
            ],
            height=820,
        )
        self.bind_field_visibility("limit_time", "是", ["start_date", "end_date"])
        self.bind_field_visibility("get_comments", "是", ["max_comments"])
        self.bind_field_visibility("verify_video_type", "是", ["verify_max_scrolls"])

    def validate_values(self, values):
        if not _lines(values["channel_urls"]):
            raise ValueError("至少需要输入一个 YouTube 博主主页链接。")
        if values.get("limit_time") == "是":
            from src.platforms.youtube.keyword import parse_date_range
            parse_date_range(values["start_date"], values["end_date"])

    def tool_config_params(self):
        return [
            ConfigParam("max_video_items", "最多作品数", kind="int", default=5000, minimum=1, maximum=5000),
            ConfigParam("max_post_scrolls", "帖子最大滚动次数", kind="int", default=200, minimum=1, maximum=5000),
            ConfigParam("initial_load_delay", "初始加载等待(秒)", kind="float", default=1.8, minimum=0.5, maximum=10.0, step=0.1, decimals=1),
        ]

    def run_task(self, values, log_callback, finish_callback, stop_event, pause_event):
        from src.platforms.youtube.channel_works import run_youtube_channel_works_spider

        config = {k: v for k, v in values.items() if k in ("max_video_items", "page_load_timeout", "scroll_interval", "no_new_scroll_limit", "scroll_px", "max_post_scrolls", "save_batch_size", "initial_load_delay", "verify_video_type", "verify_max_scrolls")}
        return run_youtube_channel_works_spider(
            _lines(values["api_key"]),
            values["channel_urls"],
            values.get("collect_target", "全部"),
            int(values.get("max_video_items", 5000)),
            int(values.get("max_post_scrolls", 200)),
            values["limit_time"],
            values["start_date"],
            values["end_date"],
            values["get_comments"],
            int(values["max_comments"]),
            log_callback,
            finish_callback,
            stop_event,
            config=config,
            pause_event=pause_event,
        )


class YouTubeCommentsWindow(SimpleToolWindow):
    tool_id = "youtube_top_comments"

    def __init__(self) -> None:
        super().__init__(
            "YouTube 视频数据与评论采集",
            [
                FieldSpec("api_key", "Google API Key(s) (支持多行或导入txt)", kind="text_or_file", required=True, placeholder="支持每行填写一个API Key，耗尽自动轮询"),
                FieldSpec("txt_path", "视频链接，每行一个", kind="text_or_file", required=True, placeholder="https://www.youtube.com/watch?v=xxxx"),
                FieldSpec("get_comments", "是否获取视频评论信息？", kind="combo", options=("是", "否"), default="否"),
                FieldSpec("max_scan_comments", "最多获取评论数", kind="int", default=500, minimum=100, maximum=10000),
                FieldSpec("check_type", "是否精确检测视频长短类型？", kind="combo", options=("是", "否"), default="否"),
            ],
        )
        self.bind_field_visibility("get_comments", "是", ["max_scan_comments"])

    def tool_config_params(self):
        return [
            ConfigParam("youtube_api_page_size", "评论每页条数", kind="int", default=100, minimum=1, maximum=100),
        ]

    def run_task(self, values, log_callback, finish_callback, stop_event, pause_event):
        from src.platforms.youtube.comments import run_youtube_video_metrics_spider

        config = {k: v for k, v in values.items() if k.startswith("youtube_") or k in ("comment_top_limit",)}
        return run_youtube_video_metrics_spider(
            _lines(values["api_key"]),
            self._text_to_tempfile(values["txt_path"]),
            values.get("get_comments", "否"),
            values.get("check_type", "否"),
            int(values.get("max_scan_comments", 500)),
            log_callback,
            finish_callback,
            stop_event,
            config=config,
            pause_event=pause_event,
        )
