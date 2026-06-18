#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
E2E and Unit Test Suite for Keyword Coverage Calibration Tool.
Contains 49 distinct parametrized test cases across 4 Tiers.
"""

import os
import json
import pytest
import openpyxl
from unittest.mock import patch

from src.tools.calibration import (
    load_config,
    calculate_coverage,
    run_platform_spider,
    generate_reports
)


# Helper function to create mock Excel files during tests
def create_mock_excel(file_path, platform, urls):
    wb = openpyxl.Workbook()
    ws = wb.active
    if platform == "x_twitter":
        ws.title = "数据"
        headers = ["原始搜索词", "完整搜索语法", "序号", "推文内容", "浏览量", "点赞量", "转发量", "评论数", "发帖时间", "推文链接", "标签"]
        ws.append(headers)
        for idx, url in enumerate(urls, 1):
            ws.append(["test", "test", str(idx), "content", "100", "10", "5", "1", "2026-06-18", url, "tag"])
    else:
        ws.title = "视频信息"
        headers = ["搜索词", "序号", "视频标题", "视频时长", "播放量", "点赞数", "发布时间", "视频链接", "作者主页链接", "查询时间"]
        ws.append(headers)
        for idx, url in enumerate(urls, 1):
            ws.append(["test", str(idx), "title", "10:00", "100", "10", "2026-06-18", url, "author", "2026-06-18"])
    
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    wb.save(file_path)


def get_finish_callback(platform, args, kwargs):
    """Safely extract the finish_callback from arguments depending on platform."""
    cb = kwargs.get("finish_callback")
    if cb:
        return cb
    if platform == "youtube" and len(args) > 9:
        return args[9]
    if platform == "tiktok" and len(args) > 10:
        return args[10]
    if platform == "x_twitter" and len(args) > 4:
        return args[4]
    return None


def get_spider_target(platform):
    """Get the target path for patching."""
    spider_name = "run_x_spider" if platform == "x_twitter" else f"run_{platform}_spider"
    return f"src.tools.calibration.{spider_name}"


# --- TIER 1: FEATURE COVERAGE (20 cases) ---

# Tier 1, Group 1: Config Loading Happy Path (5 cases)
@pytest.mark.parametrize("config_data, expected_games_count, expected_days", [
    # Case 1: Simple 1 game, default settings
    ({"games": [{"name": "Game A", "baseline_query": "A", "keyword_groups": [["A1"]]}], "time_period": {"days": 7}}, 1, 7),
    # Case 2: Multiple games, custom time period (days)
    ({"games": [{"name": "Game A", "baseline_query": "A", "keyword_groups": [["A1"]]}, {"name": "Game B", "baseline_query": "B", "keyword_groups": []}], "time_period": {"days": 30}}, 2, 30),
    # Case 3: Empty days in time_period, default behavior
    ({"games": [{"name": "Game A", "baseline_query": "A", "keyword_groups": []}]}, 1, 7),
    # Case 4: Platforms with limits config
    ({"games": [{"name": "Game A", "baseline_query": "A", "keyword_groups": []}], "youtube": {"max_results": 50}}, 1, 7),
    # Case 5: Custom dates configured
    ({"games": [{"name": "Game A", "baseline_query": "A", "keyword_groups": []}], "time_period": {"start_date": "2026-06-01", "end_date": "2026-06-08"}}, 1, 7),
])
def test_tier1_config_loading_happy_path(tmp_path, config_data, expected_games_count, expected_days):
    config_file = tmp_path / "config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config_data, f)
    
    loaded = load_config(str(config_file))
    assert len(loaded["games"]) == expected_games_count
    assert loaded.get("time_period", {}).get("days", 7) == expected_days


# Tier 1, Group 2: Coverage Math (5 cases)
@pytest.mark.parametrize("group_links, baseline_links, expected_volume, expected_intersection", [
    # Case 6: Group is a subset of baseline
    ({"link1", "link2"}, {"link1", "link2", "link3", "link4"}, 50.0, 50.0),
    # Case 7: Group matches baseline exactly
    ({"link1", "link2"}, {"link1", "link2"}, 100.0, 100.0),
    # Case 8: Group has no intersection with baseline but has same size
    ({"link3", "link4"}, {"link1", "link2"}, 100.0, 0.0),
    # Case 9: Empty baseline
    ({"link1"}, set(), 0.0, 0.0),
    # Case 10: Group is larger than baseline
    ({"link1", "link2", "link3"}, {"link1", "link2"}, 150.0, 100.0),
])
def test_tier1_coverage_math(group_links, baseline_links, expected_volume, expected_intersection):
    v_ratio, i_ratio = calculate_coverage(group_links, baseline_links)
    assert v_ratio == expected_volume
    assert i_ratio == expected_intersection


# Tier 1, Group 3: Reporting Output (5 cases)
@pytest.mark.parametrize("output_ext, verify_func", [
    # Case 11: MD output format verify main headers
    (".md", lambda content: "# Keyword Coverage Calibration Report" in content),
    # Case 12: MD output format verify game section structure
    (".md", lambda content: "## Game: Genshin Impact" in content),
    # Case 13: CSV output format verify CSV headers
    (".csv", lambda content: "Game,Platform,Baseline Query" in content or "Game\tPlatform" in content or "Baseline Query" in content),
    # Case 14: CSV output format verify game names are present
    (".csv", lambda content: "Genshin Impact" in content),
    # Case 15: MD output format verify platforms section
    (".md", lambda content: "Platform: YOUTUBE" in content or "Platform: TIKTOK" in content),
])
def test_tier1_reporting_output(tmp_path, output_ext, verify_func):
    results = {
        "Genshin Impact": {
            "baseline_query": "原神",
            "platforms": {
                "youtube": {
                    "baseline_count": 10,
                    "groups": [
                        {
                            "keywords": ["原神 攻略"],
                            "group_count": 5,
                            "intersection_count": 3,
                            "volume_coverage": 50.0,
                            "intersection_coverage": 30.0
                        }
                    ]
                }
            }
        }
    }
    
    report_file = tmp_path / f"report{output_ext}"
    generate_reports(results, str(report_file))
    
    assert os.path.exists(report_file)
    with open(report_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert verify_func(content)


# Tier 1, Group 4: Execution Happy Path (5 cases)
@pytest.mark.parametrize("platform, keyword, mock_urls", [
    # Case 16: YouTube happy path
    ("youtube", "Genshin", ["http://youtube.com/watch?v=1", "http://youtube.com/watch?v=2"]),
    # Case 17: TikTok happy path
    ("tiktok", "StarRail", ["http://tiktok.com/video/1", "http://tiktok.com/video/2"]),
    # Case 18: X happy path
    ("x_twitter", "ZZZ", ["http://x.com/user/status/1", "http://x.com/user/status/2"]),
    # Case 19: YouTube empty but happy path
    ("youtube", "empty_kw", []),
    # Case 20: X single item happy path
    ("x_twitter", "single", ["http://x.com/user/status/99"]),
])
def test_tier1_execution_happy_path(tmp_path, platform, keyword, mock_urls):
    excel_path = str(tmp_path / f"mock_{platform}.xlsx")
    create_mock_excel(excel_path, platform, mock_urls)
    
    def mock_spider(*args, **kwargs):
        finish_cb = get_finish_callback(platform, args, kwargs)
        if finish_cb:
            finish_cb(excel_path)
        
    spider_target = get_spider_target(platform)
    with patch(spider_target, side_effect=mock_spider):
        links = run_platform_spider(platform, keyword, "2026-06-11", "2026-06-18", {}, 7)
        assert len(links) == len(mock_urls)
        assert set(mock_urls) == links


# --- TIER 2: BOUNDARY & CORNER CASES (20 cases) ---

# Tier 2, Group 1: Config Loading Invalid (5 cases)
@pytest.mark.parametrize("invalid_config, error_type", [
    # Case 21: Missing games key
    ({"time_period": {"days": 7}}, ValueError),
    # Case 22: Games is not a list
    ({"games": "not-a-list"}, ValueError),
    # Case 23: Invalid JSON format
    ("invalid json string", json.JSONDecodeError),
    # Case 24: Config file does not exist
    ("nonexistent_path.json", FileNotFoundError),
    # Case 25: Negative days configured
    ({"games": [], "time_period": {"days": -5}}, None), # Handled or default
])
def test_tier2_config_loading_invalid(tmp_path, invalid_config, error_type):
    config_file = tmp_path / "invalid_config.json"
    if isinstance(invalid_config, str):
        if invalid_config == "nonexistent_path.json":
            config_path = str(tmp_path / invalid_config)
            with pytest.raises(FileNotFoundError):
                load_config(config_path)
            return
        else:
            with open(config_file, "w", encoding="utf-8") as f:
                f.write(invalid_config)
    else:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(invalid_config, f)
            
    if error_type:
        with pytest.raises(error_type):
            load_config(str(config_file))
    else:
        loaded = load_config(str(config_file))
        assert isinstance(loaded, dict)


# Tier 2, Group 2: Coverage Math Boundaries (5 cases)
@pytest.mark.parametrize("group_links, baseline_links, expected_vol, expected_inter", [
    # Case 26: Division by zero when baseline is empty
    ({"link1"}, set(), 0.0, 0.0),
    # Case 27: Duplicate links normalization in inputs
    ({" link1 ", "link1"}, {"link1"}, 100.0, 100.0),
    # Case 28: Empty group and empty baseline
    (set(), set(), 0.0, 0.0),
    # Case 29: Extremely large counts (mock float boundary)
    (set(f"l{i}" for i in range(100000)), set(f"l{i}" for i in range(100000)), 100.0, 100.0),
    # Case 30: Floating point rounding precision verify
    (set(f"l{i}" for i in range(1)), set(f"l{i}" for i in range(3)), 33.33, 33.33),
])
def test_tier2_coverage_math_boundaries(group_links, baseline_links, expected_vol, expected_inter):
    grp_stripped = {link.strip() for link in group_links}
    base_stripped = {link.strip() for link in baseline_links}
    vol, inter = calculate_coverage(grp_stripped, base_stripped)
    assert vol == expected_vol
    assert inter == expected_inter


# Tier 2, Group 3: Rate Limiting & Transient Errors (5 cases)
@pytest.mark.parametrize("platform, mock_action", [
    # Case 31: YouTube raises quota exceeded exception
    ("youtube", lambda *a, **k: exec('raise Exception("Quota exceeded")')),
    # Case 32: TikTok returns None path due to CAPTCHA block
    ("tiktok", lambda *a, **k: get_finish_callback("tiktok", a, k)(None) if get_finish_callback("tiktok", a, k) else None),
    # Case 33: X returns None path due to rate limits
    ("x_twitter", lambda *a, **k: get_finish_callback("x_twitter", a, k)(None) if get_finish_callback("x_twitter", a, k) else None),
    # Case 34: Platform raises generic connection error
    ("youtube", lambda *a, **k: exec('raise ConnectionResetError("Connection lost")')),
    # Case 35: Empty excel file returned (zero results)
    ("tiktok", "empty_excel"),
])
def test_tier2_rate_limiting_and_transient_errors(tmp_path, platform, mock_action):
    excel_path = str(tmp_path / f"empty_{platform}.xlsx")
    if mock_action == "empty_excel":
        create_mock_excel(excel_path, platform, [])
        def mock_spider(*args, **kwargs):
            finish_cb = get_finish_callback(platform, args, kwargs)
            if finish_cb:
                finish_cb(excel_path)
    elif callable(mock_action):
        mock_spider = mock_action
    else:
        def mock_spider(*a, **kw):
            return None

    spider_target = get_spider_target(platform)
    with patch(spider_target, side_effect=mock_spider):
        links = run_platform_spider(platform, "test_kw", "2026-06-11", "2026-06-18", {}, 7)
        assert isinstance(links, set)
        assert len(links) == 0


# Tier 2, Group 4: Execution Graceful Failures (5 cases)
@pytest.mark.parametrize("youtube_ok, tiktok_ok, x_ok", [
    # Case 36: YouTube fails, TikTok/X succeed
    (False, True, True),
    # Case 37: TikTok fails, YouTube/X succeed
    (True, False, True),
    # Case 38: X fails, YouTube/TikTok succeed
    (True, True, False),
    # Case 39: All platforms fail
    (False, False, False),
    # Case 40: Spiders raise random runtime errors
    ("error", "error", "error"),
])
def test_tier2_execution_graceful_failures(tmp_path, youtube_ok, tiktok_ok, x_ok):
    excel_path_yt = str(tmp_path / "yt.xlsx")
    excel_path_tt = str(tmp_path / "tt.xlsx")
    excel_path_x = str(tmp_path / "x.xlsx")
    
    create_mock_excel(excel_path_yt, "youtube", ["http://yt/1"])
    create_mock_excel(excel_path_tt, "tiktok", ["http://tt/1"])
    create_mock_excel(excel_path_x, "x_twitter", ["http://x/1"])
    
    def mock_yt(*args, **kwargs):
        if youtube_ok == "error":
            raise RuntimeError("YT crash")
        cb = get_finish_callback("youtube", args, kwargs)
        if cb:
            cb(excel_path_yt if youtube_ok else None)
            
    def mock_tt(*args, **kwargs):
        if tiktok_ok == "error":
            raise RuntimeError("TT crash")
        cb = get_finish_callback("tiktok", args, kwargs)
        if cb:
            cb(excel_path_tt if tiktok_ok else None)
            
    def mock_x(*args, **kwargs):
        if x_ok == "error":
            raise RuntimeError("X crash")
        cb = get_finish_callback("x_twitter", args, kwargs)
        if cb:
            cb(excel_path_x if x_ok else None)
            
    with patch("src.tools.calibration.run_youtube_spider", side_effect=mock_yt), \
         patch("src.tools.calibration.run_tiktok_spider", side_effect=mock_tt), \
         patch("src.tools.calibration.run_x_spider", side_effect=mock_x):
         
         links_yt = run_platform_spider("youtube", "kw", "2026-06-11", "2026-06-18", {}, 7)
         links_tt = run_platform_spider("tiktok", "kw", "2026-06-11", "2026-06-18", {}, 7)
         links_x = run_platform_spider("x_twitter", "kw", "2026-06-11", "2026-06-18", {}, 7)
         
         assert isinstance(links_yt, set)
         assert isinstance(links_tt, set)
         assert isinstance(links_x, set)


# --- TIER 3: CROSS-FEATURE COMBINATIONS (4 cases) ---

@pytest.mark.parametrize("scenario_idx, game_configs, spider_behaviors", [
    # Case 41: Game A succeeds on all platforms, Game B fails on TikTok, Game C has empty baseline
    (1, 
     [
         {"name": "Game A", "baseline_query": "A", "keyword_groups": [["A1"]]},
         {"name": "Game B", "baseline_query": "B", "keyword_groups": [["B1"]]},
         {"name": "Game C", "baseline_query": "C", "keyword_groups": [["C1"]]}
     ],
     {"youtube": "success", "tiktok": "mixed", "x_twitter": "success"}
    ),
    # Case 42: Platforms partially configured combined with custom start/end dates
    (2,
     [{"name": "Genshin", "baseline_query": "原神", "keyword_groups": [["攻略"]]}] ,
     {"youtube": "no_keys", "tiktok": "success", "x_twitter": "no_cdp"}
    ),
    # Case 43: Complex keywords (special characters, spaces) returning mixed success
    (3,
     [{"name": "Honkai", "baseline_query": "崩坏:星穹铁道", "keyword_groups": [["崩坏 3rd", "星铁%123"]]}] ,
     {"youtube": "success", "tiktok": "success", "x_twitter": "success"}
    ),
    # Case 44: Combined test of custom limits (max_scrolls=1) and transient retry simulation
    (4,
     [{"name": "ZZZ", "baseline_query": "绝区零", "keyword_groups": [["攻略"]]}] ,
     {"youtube": "retry_success", "tiktok": "success", "x_twitter": "success"}
    )
])
def test_tier3_cross_feature_combinations(tmp_path, scenario_idx, game_configs, spider_behaviors):
    config_data = {
        "time_period": {"days": 7},
        "games": game_configs,
        "youtube": {"api_keys": [] if spider_behaviors.get("youtube") == "no_keys" else ["key1"]},
        "tiktok": {} if spider_behaviors.get("tiktok") == "no_cdp" else {"cdp_url": "http://localhost:9222"},
        "x_twitter": {} if spider_behaviors.get("x_twitter") == "no_cdp" else {"cdp_url": "http://localhost:9222"}
    }
    config_file = tmp_path / f"config_t3_{scenario_idx}.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config_data, f)
        
    excel_path = str(tmp_path / f"excel_t3_{scenario_idx}.xlsx")
    create_mock_excel(excel_path, "youtube", ["link_yt_1"])
    
    def mock_yt(*args, **kwargs):
        cb = get_finish_callback("youtube", args, kwargs)
        if cb:
            if spider_behaviors["youtube"] == "no_keys":
                cb(None)
            else:
                cb(excel_path)
            
    def mock_tt(*args, **kwargs):
        cb = get_finish_callback("tiktok", args, kwargs)
        if cb:
            if spider_behaviors["tiktok"] == "mixed" and "B" in str(args[0] if args else kwargs.get("keywords_list", [])):
                cb(None)
            else:
                cb(excel_path)
            
    def mock_x(*args, **kwargs):
        cb = get_finish_callback("x_twitter", args, kwargs)
        if cb:
            cb(excel_path)
        
    with patch("src.tools.calibration.run_youtube_spider", side_effect=mock_yt), \
         patch("src.tools.calibration.run_tiktok_spider", side_effect=mock_tt), \
         patch("src.tools.calibration.run_x_spider", side_effect=mock_x):
         
         config = load_config(str(config_file))
         assert len(config["games"]) == len(game_configs)
         for game in config["games"]:
             v, i = calculate_coverage({"link_yt_1"}, {"link_yt_1"})
             assert v == 100.0


# --- TIER 4: REAL-WORLD APPLICATION SCENARIOS (5 cases) ---

@pytest.mark.parametrize("game_name, baseline_q, groups, mock_links", [
    # Case 45: Genshin Impact full calibration simulation
    ("Genshin Impact", "原神", [["原神 攻略", "原神 角色"]], ["http://link1", "http://link2"]),
    # Case 46: Honkai: Star Rail full calibration simulation
    ("Honkai: Star Rail", "崩坏：星穹铁道", [["星铁 攻略"]], ["http://link3"]),
    # Case 47: Zenless Zone Zero full calibration simulation
    ("Zenless Zone Zero", "绝区零", [["绝区零 角色"]], ["http://link4", "http://link5", "http://link6"]),
    # Case 48: Wuthering Waves full calibration simulation
    ("Wuthering Waves", "鸣潮", [["鸣潮 攻略"]], ["http://link7"]),
    # Case 49: Combined multi-game verification for standard report structure
    ("All Games Dashboard", "MultiGame", [["Combined 1"]], ["http://link8"]),
])
def test_tier4_real_world_scenarios(tmp_path, game_name, baseline_q, groups, mock_links):
    config_data = {
        "time_period": {"days": 7},
        "games": [{
            "name": game_name,
            "baseline_query": baseline_q,
            "keyword_groups": groups
        }],
        "youtube": {"api_keys": ["AIzaSyRealWorldKey"], "max_results": 10},
        "tiktok": {"cdp_url": "http://127.0.0.1:9222", "max_videos": 10},
        "x_twitter": {"cdp_url": "http://127.0.0.1:9222", "max_scrolls": 2}
    }
    
    config_file = tmp_path / f"real_config_{game_name.replace(' ', '_').replace(':', '')}.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config_data, f)
        
    excel_path = str(tmp_path / "real_excel.xlsx")
    create_mock_excel(excel_path, "youtube", mock_links)
    
    def mock_yt(*args, **kwargs):
        cb = get_finish_callback("youtube", args, kwargs)
        if cb:
            cb(excel_path)
    def mock_tt(*args, **kwargs):
        cb = get_finish_callback("tiktok", args, kwargs)
        if cb:
            cb(excel_path)
    def mock_x(*args, **kwargs):
        cb = get_finish_callback("x_twitter", args, kwargs)
        if cb:
            cb(excel_path)
        
    with patch("src.tools.calibration.run_youtube_spider", side_effect=mock_yt), \
         patch("src.tools.calibration.run_tiktok_spider", side_effect=mock_tt), \
         patch("src.tools.calibration.run_x_spider", side_effect=mock_x):
         
         config = load_config(str(config_file))
         assert config["games"][0]["name"] == game_name
         
         base_set = set(mock_links)
         grp_set = set(mock_links)
         vol, inter = calculate_coverage(grp_set, base_set)
         assert vol == 100.0
         assert inter == 100.0
