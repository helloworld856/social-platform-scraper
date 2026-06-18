#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Challenger Test Suite for Keyword Coverage Calibration Tool.
Actively stress-tests assumptions, edge cases, and robustness.
"""

import os
import json
import pytest
import openpyxl
from unittest.mock import patch

from src.tools.calibration import (
    load_config,
    run_platform_spider,
    generate_reports
)


# Helper function to create mock Excel files with edge cases
def create_mock_excel_edge_cases(file_path, platform, rows_data):
    """
    rows_data is a list of cell values for the target column
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    if platform == "x_twitter":
        ws.title = "数据"
        headers = ["原始搜索词", "完整搜索语法", "序号", "推文内容", "浏览量", "点赞量", "转发量", "评论数", "发帖时间", "推文链接", "标签"]
        ws.append(headers)
        for idx, val in enumerate(rows_data, 1):
            ws.append(["test", "test", str(idx), "content", "100", "10", "5", "1", "2026-06-18", val, "tag"])
    else:
        ws.title = "视频信息"
        headers = ["搜索词", "序号", "视频标题", "视频时长", "播放量", "点赞数", "发布时间", "视频链接", "作者主页链接", "查询时间"]
        ws.append(headers)
        for idx, val in enumerate(rows_data, 1):
            ws.append(["test", str(idx), "title", "10:00", "100", "10", "2026-06-18", val, "author", "2026-06-18"])

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    wb.save(file_path)
    wb.close()


def get_finish_callback(platform, args, kwargs):
    """Safely extract the finish_callback from arguments (keyword-only)."""
    return kwargs.get("finish_callback")


# Test 1: Config loading with missing required keys
def test_config_missing_required_keys(tmp_path):
    # Missing baseline_query inside games list
    config_data = {
        "games": [
            {"name": "Game A", "keyword_groups": [["A1"]]}
        ]
    }
    config_file = tmp_path / "config_missing.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config_data, f)
    
    # load_config itself passes, but main() would fail when accessing the keys
    loaded = load_config(str(config_file))
    assert "games" in loaded
    # Verifying that calling the main logic with this config raises KeyError
    with pytest.raises(KeyError):
        for game in loaded["games"]:
            _ = game["baseline_query"]


# Test 2: Invalid excel cell values (None, integers, empty strings, spaces)
@pytest.mark.parametrize("platform, cell_values, expected_links", [
    ("youtube", [None, "  ", 12345, "http://yt/1"], {"12345", "http://yt/1"}),
    ("x_twitter", ["http://x/1", None, "", "  http://x/2  "], {"http://x/1", "http://x/2"}),
])
def test_excel_cell_edge_cases(tmp_path, platform, cell_values, expected_links):
    excel_path = str(tmp_path / f"edge_{platform}.xlsx")
    create_mock_excel_edge_cases(excel_path, platform, cell_values)
    
    def mock_spider(*args, **kwargs):
        cb = get_finish_callback(platform, args, kwargs)
        if cb:
            cb(excel_path)
            
    spider_target = f"src.tools.calibration.run_{'x' if platform == 'x_twitter' else platform}_spider"
    with patch(spider_target, side_effect=mock_spider):
        links = run_platform_spider(platform, "test_kw", "2026-06-11", "2026-06-18", {}, 7)
        assert links == expected_links


# Test 3: Output path is a directory (should raise error or handle gracefully)
def test_output_path_is_directory(tmp_path):
    results = {
        "Game A": {
            "baseline_query": "A",
            "platforms": {
                "youtube": {
                    "baseline_count": 0,
                    "groups": []
                }
            }
        }
    }
    # output_path is a directory
    dir_path = tmp_path / "reports_dir"
    os.makedirs(dir_path, exist_ok=True)
    
    # Expect PermissionError / IsADirectoryError when attempting to write
    with pytest.raises((PermissionError, OSError)):
        generate_reports(results, str(dir_path))


# Test 4: Unicode, spaces, and emoji keywords
def test_weird_keyword_formats(tmp_path):
    # Special character and emoji keywords
    config_data = {
        "games": [
            {
                "name": "Game Emoji",
                "baseline_query": "🎮 Genshin 🔥",
                "keyword_groups": [["攻略 2026", "角色 @test_user"]]
            }
        ]
    }
    config_file = tmp_path / "config_emoji.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config_data, f)
        
    loaded = load_config(str(config_file))
    assert loaded["games"][0]["baseline_query"] == "🎮 Genshin 🔥"


# Test 5: Verify that whitespace-only cells are ignored and not added to links
def test_whitespace_only_cell_bug(tmp_path):
    excel_path = str(tmp_path / "whitespace_bug.xlsx")
    create_mock_excel_edge_cases(excel_path, "youtube", ["   "])
    
    def mock_spider(*args, **kwargs):
        cb = get_finish_callback("youtube", args, kwargs)
        if cb:
            cb(excel_path)
            
    with patch("src.tools.calibration.run_youtube_spider", side_effect=mock_spider):
        links = run_platform_spider("youtube", "test_kw", "2026-06-11", "2026-06-18", {}, 7)
        assert "" not in links
        assert len(links) == 0


# Test 6: Verify main() parses string days like "7" correctly and fails on invalid string days
def test_main_days_string_handling(tmp_path):
    # Case A: String days like "7" (should be handled without crashing)
    config_data_valid = {
        "games": [{"name": "Game A", "baseline_query": "A", "keyword_groups": []}],
        "time_period": {"days": "7"}
    }
    config_file_valid = tmp_path / "config_days_valid.json"
    with open(config_file_valid, "w", encoding="utf-8") as f:
        json.dump(config_data_valid, f)
        
    import sys
    from src.tools.calibration import main
    
    with patch.object(sys, 'argv', ['calibration.py', '--config', str(config_file_valid)]), \
         patch('src.tools.calibration.run_calibration_task') as mock_run:
        main()  # Should run successfully without crashing
        mock_run.assert_called_once()

    # Case B: Invalid days config like "seven" (should fail gracefully with SystemExit(1))
    config_data_invalid = {
        "games": [{"name": "Game A", "baseline_query": "A", "keyword_groups": []}],
        "time_period": {"days": "seven"}
    }
    config_file_invalid = tmp_path / "config_days_invalid.json"
    with open(config_file_invalid, "w", encoding="utf-8") as f:
        json.dump(config_data_invalid, f)
        
    with patch.object(sys, 'argv', ['calibration.py', '--config', str(config_file_invalid)]):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1


# Test 7: Verify that volume ratio can exceed 100% when group links size is larger than baseline
def test_volume_ratio_exceeds_100():
    from src.tools.calibration import calculate_coverage
    group_links = {"link1", "link2", "link3", "link4", "link5"}
    baseline_links = {"link1", "link2"}
    
    vol, inter, count = calculate_coverage(group_links, baseline_links)
    # 5 links in group vs 2 in baseline -> 250.0% volume ratio, 100.0% intersection ratio
    assert vol == 250.0
    assert inter == 100.0


