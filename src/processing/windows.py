from __future__ import annotations

import time
from pathlib import Path

from src.core import build_output_path
from src.judge_aigc.config import config as aigc_config
from src.ui.base import FieldSpec, SimpleToolWindow


class JudgeAIGCWindow(SimpleToolWindow):
    def __init__(self) -> None:
        super().__init__(
            "AIGC 标题判断",
            [
                FieldSpec("input_path", "输入 TXT", kind="file", required=True),
                FieldSpec("row_limit", "每批行数", kind="int", default=aigc_config.ROW_LIMIT, minimum=1, maximum=100000),
                FieldSpec("max_workers", "当前批 AI 并发数", kind="int", default=3, minimum=1, maximum=100),
                FieldSpec("save_every_batches", "每几批保存一次", kind="int", default=aigc_config.SAVE_EVERY_BATCHES, minimum=1, maximum=100000),
            ],
            height=500,
        )

    def validate_values(self, values):
        if not Path(values["input_path"]).exists():
            raise ValueError("TXT 文件不存在。")

    def run_task(self, values, log_callback, finish_callback, stop_event):
        from src.processing.judge_aigc import judge

        output_path = build_output_path("data", f"judge_aigc_{time.strftime('%Y%m%d_%H%M%S')}.xlsx")
        log_callback(f"输出文件：{output_path}")
        if stop_event and stop_event.is_set():
            finish_callback(None)
            return None
        judge(
            values["input_path"],
            output_path,
            row_limit=int(values["row_limit"]),
            max_workers=int(values["max_workers"]),
            save_every_batches=int(values["save_every_batches"]),
            log_callback=log_callback,
            stop_event=stop_event,
        )
        log_callback(f"完成，已保存：{output_path}")
        finish_callback(output_path)
        return output_path


class XlsxMergeWindow(SimpleToolWindow):
    def __init__(self) -> None:
        super().__init__(
            "关键词 XLSX 合并",
            [
                FieldSpec("folder", "XLSX 文件夹", kind="folder", required=True),
                FieldSpec("platform", "平台前缀", kind="combo", default="tiktok", options=("youtube", "tiktok", "x")),
                FieldSpec("keyword", "文件名包含", default="keyword", required=True),
            ],
            height=500,
        )

    def validate_values(self, values):
        if not Path(values["folder"]).exists():
            raise ValueError("文件夹不存在。")

    def run_task(self, values, log_callback, finish_callback, stop_event):
        from src.processing.xlsx_merge import merge_xlsx_files

        log_callback(f"合并文件夹：{values['folder']}")
        log_callback(f"平台前缀：{values['platform']}")
        log_callback(f"文件名关键词：{values['keyword']}")
        if stop_event and stop_event.is_set():
            finish_callback(None)
            return None
        output_path, file_count, row_count = merge_xlsx_files(values["folder"], values["keyword"], values["platform"])
        log_callback(f"完成：合并 {file_count} 个文件，{row_count} 行。")
        log_callback(f"输出文件：{output_path}")
        finish_callback(output_path)
        return output_path
