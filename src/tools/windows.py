from __future__ import annotations

from src.ui.base import FieldSpec, SimpleToolWindow


class CalibrationToolWindow(SimpleToolWindow):
    tool_id = "keyword_coverage_calibration"

    def __init__(self) -> None:
        super().__init__(
            "关键词覆盖率校准",
            [
                FieldSpec("days", "时间范围 (过去多少天)", kind="int", default=7, minimum=1, maximum=365,
                          tooltip="设置采集范围。例如填 7，则工具会采集过去 7 天内的新增数据用于覆盖率测算。"),
                FieldSpec("youtube_api_keys", "YouTube API Keys (每行一个)", kind="multiline", placeholder="必填，用于YouTube数据采集",
                          tooltip="必填参数，由于 YouTube 限制，建议提供多个 Key 换行分隔，工具会自动轮询。\n例如：\nAIzaSyBxxx...\nAIzaSyCyyy..."),
                FieldSpec("youtube_max_results", "YouTube 每词最大采集数", kind="int", default=10, minimum=1, maximum=500,
                          tooltip="每个关键词在 YouTube 上最多采集多少条结果。设得越大测算越准，但耗时越长。"),
                FieldSpec("tiktok_max_videos", "TikTok 每词最大采集数", kind="int", default=10, minimum=1, maximum=500,
                          tooltip="每个关键词在 TikTok 上最多抓取多少个视频。"),
                FieldSpec("x_max_scrolls", "X (Twitter) 每词最大滚动数", kind="int", default=2, minimum=1, maximum=50,
                          tooltip="X (Twitter) 网页向下滚动加载的次数。每次滚动大约加载 10-15 条帖子。"),
                FieldSpec("cdp_url", "CDP 调试地址", default="http://localhost:9222",
                          tooltip="Chrome 远程调试协议 (CDP) 的接口地址。如果不清楚，请保持默认。"),
                FieldSpec("output_path", "输出报告路径", kind="text", required=True, default="output/calibration_report.md",
                          tooltip="导出报告的位置。支持填写 .md（Markdown 排版格式）或 .csv（Excel 表格格式）。"),
                
                FieldSpec("games_count", "测试游戏数量", kind="combo", options=("1", "2", "3", "4"), default="1",
                          tooltip="需要同时测算多少个游戏？选择后将动态呈现对应数量的配置面板。"),
                
                # 游戏 1 (必填)
                FieldSpec("game_name_1", "[游戏 1] 游戏名称", default="Genshin Impact",
                          tooltip="该游戏的名称，仅用于最终报告中的标题展示。"),
                FieldSpec("baseline_query_1", "[游戏 1] 基准词", default="原神",
                          tooltip="代表整个游戏大盘的搜索词（通常为官方本名）。例如：原神"),
                FieldSpec("keyword_groups_1", "[游戏 1] 测试词组", kind="multiline", placeholder="每行一个词组，组内用逗号分隔:\n原神 攻略, 原神 角色\nGenshin guide, Genshin showcase",
                          tooltip="每一行是一个测试组，组内可用英文逗号并列多个词。\n示例：\n原神 攻略, 原神 角色\n原神 兑换码"),

                # 游戏 2
                FieldSpec("game_name_2", "[游戏 2] 游戏名称", default="Honkai: Star Rail",
                          tooltip="该游戏的名称，仅用于最终报告中的标题展示。"),
                FieldSpec("baseline_query_2", "[游戏 2] 基准词", default="崩坏：星穹铁道",
                          tooltip="代表整个游戏大盘的搜索词（通常为官方本名）。例如：崩坏：星穹铁道"),
                FieldSpec("keyword_groups_2", "[游戏 2] 测试词组", kind="multiline", placeholder="星铁 攻略, 星铁 角色\nHonkai Star Rail guide",
                          tooltip="每一行是一个测试组，组内可用英文逗号并列多个词。\n示例：\n星铁 攻略, 星铁 角色\n星穹铁道 剧情"),

                # 游戏 3
                FieldSpec("game_name_3", "[游戏 3] 游戏名称", default="Zenless Zone Zero",
                          tooltip="该游戏的名称，仅用于最终报告中的标题展示。"),
                FieldSpec("baseline_query_3", "[游戏 3] 基准词", default="绝区零",
                          tooltip="代表整个游戏大盘的搜索词（通常为官方本名）。例如：绝区零"),
                FieldSpec("keyword_groups_3", "[游戏 3] 测试词组", kind="multiline", placeholder="绝区零 攻略, 绝区零 角色\nZenless Zone Zero guide",
                          tooltip="每一行是一个测试组，组内可用英文逗号并列多个词。\n示例：\n绝区零 攻略, 绝区零 角色\nZZZ guide"),

                # 游戏 4
                FieldSpec("game_name_4", "[游戏 4] 游戏名称", default="Wuthering Waves",
                          tooltip="该游戏的名称，仅用于最终报告中的标题展示。"),
                FieldSpec("baseline_query_4", "[游戏 4] 基准词", default="鸣潮",
                          tooltip="代表整个游戏大盘的搜索词（通常为官方本名）。例如：鸣潮"),
                FieldSpec("keyword_groups_4", "[游戏 4] 测试词组", kind="multiline", placeholder="鸣潮 攻略, 鸣潮 角色\nWuthering Waves guide",
                          tooltip="每一行是一个测试组，组内可用英文逗号并列多个词。\n示例：\n鸣潮 攻略, 鸣潮 角色\nWuthering Waves guide"),
            ],
            height=850,
            form_stretch=2,
        )

        # 动态控制配置字段数量
        self._bind_games_count()

    def _bind_games_count(self):
        combo = self.widgets.get("games_count")
        if not combo:
            return

        def on_changed(text: str):
            try:
                count = int(text)
            except ValueError:
                count = 1
            
            # 游戏1永远显示，动态控制游戏2到4
            for i in range(2, 5):
                visible = i <= count
                self.set_field_visible(f"game_name_{i}", visible)
                self.set_field_visible(f"baseline_query_{i}", visible)
                self.set_field_visible(f"keyword_groups_{i}", visible)

        combo.currentTextChanged.connect(on_changed)
        on_changed(combo.currentText())

    def tool_config_params(self):
        return []

    def validate_values(self, values):
        if not values.get("youtube_api_keys", "").strip():
            raise ValueError("请至少提供一个 YouTube API Key")
        games_count = int(values.get("games_count", 1))
        for i in range(1, games_count + 1):
            if not values.get(f"game_name_{i}", "").strip():
                raise ValueError(f"游戏 {i} 的名称不能为空")
            if not values.get(f"baseline_query_{i}", "").strip():
                raise ValueError(f"游戏 {i} 的基准搜索词不能为空")
            if not values.get(f"keyword_groups_{i}", "").strip():
                raise ValueError(f"游戏 {i} 的测试词组不能为空")

    def run_task(self, values, log_callback, finish_callback, stop_event, pause_event):
        from src.tools.calibration import run_calibration_task
        
        # 解析公共配置
        api_keys = [k.strip() for k in values.get("youtube_api_keys", "").split("\n") if k.strip()]
        
        games_config = []
        games_count = int(values.get("games_count", 1))
        for i in range(1, games_count + 1):
            name = values.get(f"game_name_{i}", "").strip()
            baseline = values.get(f"baseline_query_{i}", "").strip()
            kw_text = values.get(f"keyword_groups_{i}", "").strip()
            
            if not name or not baseline or not kw_text:
                raise ValueError(f"游戏 {i} 的必填字段不能为空")
                
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
