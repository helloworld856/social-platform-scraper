from __future__ import annotations

from src.ui.base import FieldSpec, SimpleToolWindow
from src.ui.config_dialog import ConfigParam


class CalibrationToolWindow(SimpleToolWindow):
    tool_id = "keyword_coverage_calibration"

    def __init__(self) -> None:
        super().__init__(
            "关键词覆盖率校准",
            [
                FieldSpec("config_path", "配置文件路径", kind="text_or_file", required=True, default="config/calibration_config.json"),
                FieldSpec("output_path", "输出报告路径", kind="text_or_file", required=True, default="output/calibration_report.md"),
            ],
            height=400,
        )

    def tool_config_params(self):
        # 校准工具的具体配置已经在配置文件中定义，如果有全局覆盖的需求可以加在这里
        # 这里暂时为空，如果需要可以加入额外的配置项
        return []

    def validate_values(self, values):
        import os
        if not os.path.exists(values["config_path"]):
            raise ValueError(f"配置文件不存在: {values['config_path']}")

    def run_task(self, values, log_callback, finish_callback, stop_event, pause_event):
        from src.tools.calibration import load_config, run_calibration_task
        
        config = load_config(values["config_path"])
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
