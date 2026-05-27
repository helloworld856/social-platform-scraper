from src.studio.ui_base import SimpleToolWindow, FieldSpec
from src.platforms.facebook.profile_works import run_facebook_profile_works_spider

DEFAULT_START_DATE = "2020-01-01"
DEFAULT_END_DATE = "2026-12-31"

class FacebookProfileWorksWindow(SimpleToolWindow):
    def __init__(self, parent=None):
        super().__init__(
            "Facebook博主作品采集",
            [
                FieldSpec(
                    "profile_urls",
                    "博主主页链接，每行一个",
                    kind="text_or_file",
                    placeholder="https://www.facebook.com/username",
                    required=True,
                ),
                FieldSpec("limit_time", "是否限制时间？", kind="combo", options=("是", "否"), default="否"),
                FieldSpec("start_date", "开始日期 YYYY-MM-DD", default=DEFAULT_START_DATE),
                FieldSpec("end_date", "结束日期 YYYY-MM-DD", default=DEFAULT_END_DATE),
                FieldSpec(
                    "force_exact_time",
                    "是否强制获取精准发布时间（将显著减慢采集速度）",
                    kind="combo",
                    options=("是", "否"),
                    default="否"
                ),
            ],
            [
                ("基本设置", ["profile_urls", "limit_time", "start_date", "end_date", "force_exact_time"]),
                (
                    "高级设置 (默认即可)",
                    [
                        "max_scrolls",
                        "page_load_timeout",
                        "scroll_delay",
                        "no_new_scroll_limit",
                        "scroll_px",
                        "save_batch_size"
                    ],
                ),
            ],
            parent,
            advanced_defaults={
                "max_scrolls": 200,
                "page_load_timeout": 60000,
                "scroll_delay": 2000,
                "no_new_scroll_limit": 5,
                "scroll_px": 800,
                "save_batch_size": 10,
            }
        )

    def run_task(self, values: dict, log_callback, stop_event, pause_event):
        config = {
            k: v for k, v in values.items()
            if k in (
                "max_scrolls",
                "page_load_timeout",
                "scroll_delay",
                "no_new_scroll_limit",
                "scroll_px",
                "save_batch_size",
            )
        }
        return run_facebook_profile_works_spider(
            values["profile_urls"],
            values["limit_time"],
            values.get("start_date", DEFAULT_START_DATE),
            values.get("end_date", DEFAULT_END_DATE),
            values["force_exact_time"],
            log_callback,
            stop_event,
            pause_event,
            **config
        )
