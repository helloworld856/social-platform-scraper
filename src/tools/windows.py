from __future__ import annotations

from src.ui.base import FieldSpec, SimpleToolWindow


class CalibrationToolWindow(SimpleToolWindow):
    tool_id = "keyword_coverage_calibration"

    def __init__(self) -> None:
        super().__init__(
            "关键词覆盖率校准",
            [
                FieldSpec("game_name", "游戏名称", default="Genshin Impact"),
                FieldSpec("baseline_query", "基准搜索词 (Baseline)", default="原神"),
                FieldSpec("keyword_groups", "测试词组", kind="multiline", placeholder="每行一个词组，组内用逗号分隔，例如:\n原神 攻略, 原神 角色\nGenshin guide, Genshin showcase"),
                FieldSpec("days", "时间范围 (过去多少天)", kind="int", default=7, minimum=1, maximum=365),
                FieldSpec("youtube_api_keys", "YouTube API Keys (每行一个)", kind="multiline", placeholder="必填，用于YouTube数据采集"),
                FieldSpec("youtube_max_results", "YouTube 每词最大采集数", kind="int", default=10, minimum=1, maximum=500),
                FieldSpec("tiktok_max_videos", "TikTok 每词最大采集数", kind="int", default=10, minimum=1, maximum=500),
                FieldSpec("x_max_scrolls", "X (Twitter) 每词最大滚动数", kind="int", default=2, minimum=1, maximum=50),
                FieldSpec("cdp_url", "CDP 调试地址", default="http://localhost:9222"),
                FieldSpec("output_path", "输出报告路径", kind="text_or_file", required=True, default="output/calibration_report.md"),
            ],
            height=700,
        )

    def tool_config_params(self):
        return []

    def validate_values(self, values):
        if not values.get("game_name", "").strip():
            raise ValueError("游戏名称不能为空")
        if not values.get("baseline_query", "").strip():
            raise ValueError("基准搜索词不能为空")
        if not values.get("keyword_groups", "").strip():
            raise ValueError("测试词组不能为空")
        if not values.get("youtube_api_keys", "").strip():
            raise ValueError("请至少提供一个 YouTube API Key")

    def run_task(self, values, log_callback, finish_callback, stop_event, pause_event):
        from src.tools.calibration import run_calibration_task
        
        # 组装配置
        api_keys = [k.strip() for k in values.get("youtube_api_keys", "").split("\n") if k.strip()]
        kw_lines = [line.strip() for line in values.get("keyword_groups", "").split("\n") if line.strip()]
        groups = []
        for line in kw_lines:
            groups.append([k.strip() for k in line.split(",") if k.strip()])
            
        config = {
            "time_period": {
                "days": int(values.get("days", 7))
            },
            "youtube": {
                "api_keys": api_keys,
                "max_results": int(values.get("youtube_max_results", 10))
            },
            "tiktok": {
                "cdp_url": values.get("cdp_url", "http://localhost:9222"),
                "max_videos": int(values.get("tiktok_max_videos", 10))
            },
            "x_twitter": {
                "cdp_url": values.get("cdp_url", "http://localhost:9222"),
                "max_scrolls": int(values.get("x_max_scrolls", 2))
            },
            "games": [
                {
                    "name": values.get("game_name", ""),
                    "baseline_query": values.get("baseline_query", ""),
                    "keyword_groups": groups
                }
            ]
        }

        output_path = values["output_path"]
        
        try:
            # 核心业务逻辑
            run_calibration_task(config, output_path, log_callback, stop_event, pause_event)
            
            # 通知 UI 任务完成并生成了报告
            if not stop_event.is_set():
                finish_callback(output_path)
        except Exception as e:
            log_callback(f"执行异常: {e}")
            raise
