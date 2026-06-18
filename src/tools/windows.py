from __future__ import annotations

from src.ui.base import FieldSpec, SimpleToolWindow


class CalibrationToolWindow(SimpleToolWindow):
    tool_id = "keyword_coverage_calibration"

    def __init__(self) -> None:
        super().__init__(
            "关键词覆盖率校准",
            [
                FieldSpec("days", "时间范围 (过去多少天)", kind="int", default=7, minimum=1, maximum=365),
                FieldSpec("youtube_api_keys", "YouTube API Keys (每行一个)", kind="multiline", placeholder="必填，用于YouTube数据采集"),
                FieldSpec("youtube_max_results", "YouTube 每词最大采集数", kind="int", default=10, minimum=1, maximum=500),
                FieldSpec("tiktok_max_videos", "TikTok 每词最大采集数", kind="int", default=10, minimum=1, maximum=500),
                FieldSpec("x_max_scrolls", "X (Twitter) 每词最大滚动数", kind="int", default=2, minimum=1, maximum=50),
                FieldSpec("cdp_url", "CDP 调试地址", default="http://localhost:9222"),
                FieldSpec("output_path", "输出报告路径", kind="text_or_file", required=True, default="output/calibration_report.md"),
                
                # 游戏 1 (必填)
                FieldSpec("game_name_1", "[游戏 1] 游戏名称", default="Genshin Impact"),
                FieldSpec("baseline_query_1", "[游戏 1] 基准词", default="原神"),
                FieldSpec("keyword_groups_1", "[游戏 1] 测试词组", kind="multiline", placeholder="每行一个词组，组内用逗号分隔:\n原神 攻略, 原神 角色\nGenshin guide, Genshin showcase"),

                # 游戏 2
                FieldSpec("game_name_2", "[游戏 2] 游戏名称", default="Honkai: Star Rail", placeholder="留空则忽略"),
                FieldSpec("baseline_query_2", "[游戏 2] 基准词", default="崩坏：星穹铁道"),
                FieldSpec("keyword_groups_2", "[游戏 2] 测试词组", kind="multiline", placeholder="留空则忽略\n星铁 攻略, 星铁 角色\nHonkai Star Rail guide"),

                # 游戏 3
                FieldSpec("game_name_3", "[游戏 3] 游戏名称", default="Zenless Zone Zero", placeholder="留空则忽略"),
                FieldSpec("baseline_query_3", "[游戏 3] 基准词", default="绝区零"),
                FieldSpec("keyword_groups_3", "[游戏 3] 测试词组", kind="multiline", placeholder="留空则忽略\n绝区零 攻略, 绝区零 角色\nZenless Zone Zero guide"),

                # 游戏 4
                FieldSpec("game_name_4", "[游戏 4] 游戏名称", default="Wuthering Waves", placeholder="留空则忽略"),
                FieldSpec("baseline_query_4", "[游戏 4] 基准词", default="鸣潮"),
                FieldSpec("keyword_groups_4", "[游戏 4] 测试词组", kind="multiline", placeholder="留空则忽略\n鸣潮 攻略, 鸣潮 角色\nWuthering Waves guide"),
            ],
            height=850,
        )

    def tool_config_params(self):
        return []

    def validate_values(self, values):
        if not values.get("game_name_1", "").strip():
            raise ValueError("游戏 1 的名称不能为空")
        if not values.get("baseline_query_1", "").strip():
            raise ValueError("游戏 1 的基准搜索词不能为空")
        if not values.get("keyword_groups_1", "").strip():
            raise ValueError("游戏 1 的测试词组不能为空")
        if not values.get("youtube_api_keys", "").strip():
            raise ValueError("请至少提供一个 YouTube API Key")

    def run_task(self, values, log_callback, finish_callback, stop_event, pause_event):
        from src.tools.calibration import run_calibration_task
        
        # 解析公共配置
        api_keys = [k.strip() for k in values.get("youtube_api_keys", "").split("\n") if k.strip()]
        
        games_config = []
        for i in range(1, 5):
            name = values.get(f"game_name_{i}", "").strip()
            baseline = values.get(f"baseline_query_{i}", "").strip()
            kw_text = values.get(f"keyword_groups_{i}", "").strip()
            
            # 如果名称为空或词组为空，则跳过该游戏
            if not name or not baseline or not kw_text:
                continue
                
            kw_lines = [line.strip() for line in kw_text.split("\n") if line.strip()]
            groups = []
            for line in kw_lines:
                groups.append([k.strip() for k in line.split(",") if k.strip()])
                
            games_config.append({
                "name": name,
                "baseline_query": baseline,
                "keyword_groups": groups
            })
            
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
            "games": games_config
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
