from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import openpyxl
import pytest

from src.tools.calibration import STATUS_EMPTY_RESULT, load_config, main, parse_games_definition, parse_platforms, run_calibration_task


def create_mock_excel(file_path: Path, platform: str, values: list[object]) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    if platform == "x_twitter":
        sheet.title = "数据"
        sheet.append(["原始搜索词", "完整搜索语法", "序号", "推文内容", "浏览量", "点赞量", "转发量", "评论数", "发帖时间", "推文链接", "标签"])
        for index, value in enumerate(values, 1):
            sheet.append(["kw", "kw", index, "content", "1", "1", "1", "1", "2026-06-18", value, "tag"])
    else:
        sheet.title = "视频信息"
        sheet.append(["搜索词", "序号", "视频标题", "播放量", "点赞数", "发布时间", "视频链接"])
        for index, value in enumerate(values, 1):
            sheet.append(["kw", index, "title", "1", "1", "2026-06-18", value])
    file_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(file_path)
    workbook.close()


def make_track(
    *,
    platform: str = "youtube",
    language: str = "en",
    baseline_query: str = "base",
    keyword_groups: list[list[str]] | None = None,
) -> dict[str, object]:
    return {
        "platform": platform,
        "language": language,
        "baseline_query": baseline_query,
        "keyword_groups": keyword_groups or [],
    }


def make_game(*tracks: dict[str, object]) -> dict[str, object]:
    return {
        "name": "Game A",
        "tracks": list(tracks),
    }


def test_parse_platforms_keeps_unknown_for_cli_reporting():
    assert parse_platforms("youtube, unknown_platform") == ["youtube", "unknown_platform"]


def test_sample_calibration_config_uses_track_schema():
    config = load_config("config/calibration_config.json")

    assert config["platforms"] == ["youtube", "tiktok", "x_twitter"]
    assert config["x_twitter"]["x_search_tab"] == "latest"
    assert config["games"][0]["tracks"][0]["platform"] == "youtube"
    assert config["games"][0]["tracks"][0]["language"] == "en"


def test_legacy_output_file_path_creates_output_calibration_run_dir(tmp_path):
    baseline_excel = tmp_path / "baseline.xlsx"
    create_mock_excel(baseline_excel, "youtube", [])

    def mock_youtube(*args, **kwargs):
        kwargs["finish_callback"](str(baseline_excel))

    config = {
        "platforms": ["youtube"],
        "time_period": {"days": 7},
        "youtube": {"api_keys": ["key"], "max_results": 10},
        "games": [make_game(make_track(platform="youtube", language="en", baseline_query="base", keyword_groups=[["kw1"]]))],
    }

    with patch("src.tools.calibration.run_youtube_spider", side_effect=mock_youtube):
        run_dir = Path(run_calibration_task(config, str(tmp_path / "report.md")))

    assert run_dir.parent.name == "calibration"
    assert (run_dir / "reports" / "calibration_report.md").exists()


def test_baseline_empty_result_is_not_treated_as_baseline_failed(tmp_path):
    baseline_excel = tmp_path / "baseline.xlsx"
    group_excel = tmp_path / "group.xlsx"
    create_mock_excel(baseline_excel, "youtube", [])
    create_mock_excel(group_excel, "youtube", ["https://www.youtube.com/watch?v=abcdefghijk"])

    def mock_youtube(*args, **kwargs):
        keyword = kwargs["keywords_list"][0]
        kwargs["finish_callback"](str(baseline_excel if keyword == "base" else group_excel))

    config = {
        "platforms": ["youtube"],
        "time_period": {"days": 7},
        "youtube": {"api_keys": ["key"], "max_results": 10},
        "games": [make_game(make_track(platform="youtube", language="en", baseline_query="base", keyword_groups=[["kw1"]]))],
    }

    with patch("src.tools.calibration.run_youtube_spider", side_effect=mock_youtube):
        run_dir = Path(run_calibration_task(config, str(tmp_path / "output")))

    raw_baseline = json.loads(next((run_dir / "raw").rglob("baseline.json")).read_text(encoding="utf-8"))
    assert raw_baseline["status"] == STATUS_EMPTY_RESULT

    csv_text = (run_dir / "reports" / "calibration_report.csv").read_text(encoding="utf-8-sig")
    assert "BASELINE_FAILED" not in csv_text
    assert ",100.0," in csv_text


def test_main_handles_string_days_and_invalid_days(tmp_path):
    valid_config = tmp_path / "valid.json"
    invalid_config = tmp_path / "invalid.json"
    valid_config.write_text(
        json.dumps(
            {
                "games": [
                    {
                        "name": "Game A",
                        "tracks": [make_track(platform="youtube", language="en", baseline_query="base", keyword_groups=[])],
                    }
                ],
                "time_period": {"days": "7"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    invalid_config.write_text(
        json.dumps(
            {
                "games": [
                    {
                        "name": "Game A",
                        "tracks": [make_track(platform="youtube", language="en", baseline_query="base", keyword_groups=[])],
                    }
                ],
                "time_period": {"days": "seven"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with (
        patch.object(sys, "argv", ["calibration.py", "--config", str(valid_config)]),
        patch("src.tools.calibration.run_calibration_task") as mock_run,
    ):
        main()
        mock_run.assert_called_once()

    with patch.object(sys, "argv", ["calibration.py", "--config", str(invalid_config)]):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1


def test_window_validation_skips_youtube_key_when_youtube_track_is_not_active():
    pytest.importorskip("PyQt5")
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from src.tools.windows import CalibrationToolWindow

    window = CalibrationToolWindow()
    values = {
        "days": 7,
        "platforms": "tiktok, x_twitter",
        "youtube_api_keys": "",
        "youtube_max_results": 10,
        "tiktok_max_videos": 10,
        "x_max_scrolls": 2,
        "x_search_tab": "latest",
        "cdp_url": "http://localhost:9222",
        "output_path": "output/calibration",
        "games_definition": json.dumps(
            [
                make_game(
                    make_track(platform="tiktok", language="ja", baseline_query="原神", keyword_groups=[["原神 攻略"]]),
                    make_track(platform="x_twitter", language="en", baseline_query="Genshin Impact", keyword_groups=[["genshin build"]]),
                )
            ],
            ensure_ascii=False,
        ),
    }
    window.validate_values(values)
    assert app is not None


def test_window_validation_rejects_when_selected_platforms_match_no_tracks():
    pytest.importorskip("PyQt5")
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from src.tools.windows import CalibrationToolWindow

    window = CalibrationToolWindow()
    values = {
        "days": 7,
        "platforms": "x_twitter",
        "youtube_api_keys": "",
        "youtube_max_results": 10,
        "tiktok_max_videos": 10,
        "x_max_scrolls": 2,
        "x_search_tab": "latest",
        "cdp_url": "http://localhost:9222",
        "output_path": "output/calibration",
        "games_definition": json.dumps(
            [make_game(make_track(platform="youtube", language="en", baseline_query="Genshin Impact", keyword_groups=[["genshin build"]]))],
            ensure_ascii=False,
        ),
    }

    with pytest.raises(ValueError, match="track 不匹配"):
        window.validate_values(values)
    assert app is not None


def test_games_editor_widget_emits_track_definition_json():
    pytest.importorskip("PyQt5")
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from src.tools.windows import CalibrationToolWindow

    window = CalibrationToolWindow()
    editor = window.widgets["games_definition"]
    serialized = editor.text()
    parsed = parse_games_definition(serialized)

    assert parsed[0]["name"] == "Genshin Impact"
    assert parsed[0]["tracks"][0]["platform"] == "youtube"
    assert parsed[0]["tracks"][0]["language"] == "en"
    assert parsed[0]["tracks"][0]["keyword_groups"][0] == ["Genshin guide", "Genshin build"]
    assert app is not None


def test_calibration_window_persists_main_form_values(tmp_path, monkeypatch):
    pytest.importorskip("PyQt5")
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    import src.core.config_store as config_store
    from src.tools.windows import CalibrationToolWindow

    monkeypatch.setattr(config_store, "get_config_dir", lambda: tmp_path)

    first_window = CalibrationToolWindow()
    first_window.widgets["days"].setValue(30)
    first_window.widgets["platforms"].setText("youtube, x_twitter")
    first_window.widgets["youtube_api_keys"].setPlainText("key-a\nkey-b")
    first_window.widgets["output_path"].setText("output/custom_calibration")
    first_window.widgets["games_definition"].setText(
        json.dumps(
            [make_game(make_track(platform="youtube", language="en", baseline_query="Zenless Zone Zero", keyword_groups=[["zzz build"]]))],
            ensure_ascii=False,
        )
    )
    values = first_window.collect_values()
    assert values is not None
    first_window._save_form_values(values)

    second_window = CalibrationToolWindow()
    assert second_window.widgets["days"].value() == 30
    assert second_window.widgets["platforms"].text() == "youtube, x_twitter"
    assert second_window.widgets["youtube_api_keys"].toPlainText() == "key-a\nkey-b"
    assert second_window.widgets["output_path"].text() == "output/custom_calibration"

    parsed = parse_games_definition(second_window.widgets["games_definition"].text())
    assert parsed[0]["tracks"][0]["baseline_query"] == "Zenless Zone Zero"
    assert app is not None
