#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
关键词覆盖率校准工具 (Keyword Coverage Calibration Tool)

用于在 YouTube、TikTok 和 X (Twitter) 上测试不同关键词组合的搜索覆盖率，
帮助标准化跨游戏的数据采集对比。

工作流程：
1. 读取配置文件中的游戏列表、基准查询词和候选关键词组。
2. 对每个平台执行基准查询和候选关键词查询，获取去重后的链接集合。
3. 计算各关键词组相对于基准的覆盖率（Volume 和 Intersection 两个维度）。
4. 输出 Markdown 或 CSV 格式的对比报告。
"""

import os
import sys
import json
import csv
import argparse
import datetime
import openpyxl

# 将项目根目录加入 sys.path，以便导入项目内模块
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.platforms.youtube.keyword import run_youtube_spider
from src.platforms.tiktok.keyword import run_tiktok_spider
from src.platforms.x_twitter.keyword import run_x_spider


def load_config(config_path: str) -> dict:
    """加载并校验 JSON 配置文件。

    Args:
        config_path: 配置文件路径。

    Returns:
        解析后的配置字典。

    Raises:
        FileNotFoundError: 配置文件不存在。
        ValueError: 配置缺少必要的 'games' 字段或类型不对。
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # 校验：必须包含 games 列表
    if "games" not in config or not isinstance(config["games"], list):
        raise ValueError("Configuration must contain a 'games' list.")

    return config


def extract_links_from_excel(file_path: str, platform: str) -> set[str]:
    """从爬虫生成的 Excel 报告中提取去重后的链接集合。

    不同平台的 Excel 列名和 Sheet 名不同，此函数统一处理：
    - YouTube / TikTok: Sheet "视频信息"，列 "视频链接"
    - X (Twitter): Sheet "数据"，列 "推文链接"

    Args:
        file_path: Excel 文件路径。
        platform: 平台标识 ("youtube" / "tiktok" / "x_twitter")。

    Returns:
        去重后的链接字符串集合（已 strip 空白，排除空值）。
    """
    links = set()
    if not file_path or not os.path.exists(file_path):
        return links
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)

        # 根据平台确定目标 Sheet 名
        sheet_name = None
        if platform == "x_twitter":
            if "数据" in wb.sheetnames:
                sheet_name = "数据"
            elif "推文信息" in wb.sheetnames:
                sheet_name = "推文信息"
        else:
            if "视频信息" in wb.sheetnames:
                sheet_name = "视频信息"
            elif "数据" in wb.sheetnames:
                sheet_name = "数据"

        sheet = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active

        # 根据平台确定目标列名
        target_col = "推文链接" if platform == "x_twitter" else "视频链接"

        # 读取表头行，定位目标列索引
        rows_iter = sheet.iter_rows(max_row=1)
        try:
            first_row = next(rows_iter)
            headers = [cell.value for cell in first_row]
        except StopIteration:
            headers = []

        if target_col in headers:
            col_idx = headers.index(target_col) + 1
            for row in sheet.iter_rows(min_row=2, values_only=True):
                if len(row) >= col_idx:
                    val = row[col_idx - 1]
                    if val:
                        val_str = str(val).strip()
                        if val_str:
                            links.add(val_str)
        wb.close()
    except Exception as e:
        print(f"Error reading Excel file {file_path} for platform {platform}: {e}", file=sys.stderr)
    return links


def calculate_coverage(group_links: set[str], baseline_links: set[str]) -> tuple[float, float]:
    """计算关键词组相对于基准的覆盖率。

    返回两个指标：
    - Volume Coverage: 关键词组链接数 / 基准链接数（可能超过 100%）。
    - Intersection Coverage: 与基准交集的链接数 / 基准链接数。

    Args:
        group_links: 关键词组检索到的链接集合。
        baseline_links: 基准查询检索到的链接集合。

    Returns:
        (volume_ratio_pct, intersection_ratio_pct) 均为百分比，保留两位小数。
    """
    # 除零保护：基准为空时所有覆盖率均为 0
    if not baseline_links:
        return 0.0, 0.0

    volume_ratio = (len(group_links) / len(baseline_links)) * 100.0
    intersection_links = group_links.intersection(baseline_links)
    intersection_ratio = (len(intersection_links) / len(baseline_links)) * 100.0

    return round(volume_ratio, 2), round(intersection_ratio, 2)


def run_platform_spider(platform: str, keyword: str, start_date: str, end_date: str, platform_config: dict, days: int, stop_event=None, pause_event=None) -> set[str]:
    """在指定平台上执行单个关键词的搜索，返回去重链接集合。

    通过 finish_callback 拿到爬虫输出的 Excel 路径，再解析提取链接。
    所有平台异常（API 限流、连接中断、CAPTCHA 等）均在此处兜底，
    确保单个关键词失败不会中断整体流程。

    Args:
        platform: 平台标识 ("youtube" / "tiktok" / "x_twitter")。
        keyword: 搜索关键词。
        start_date: 起始日期字符串 (YYYY-MM-DD)。
        end_date: 结束日期字符串 (YYYY-MM-DD)。
        platform_config: 该平台的配置字典（API Key、CDP 地址等）。
        days: 时间跨度天数，供 X 平台的 slice_days 参数使用。

    Returns:
        去重后的链接集合；异常时返回空集合。
    """
    retrieved_path = None

    def finish_callback(path):
        nonlocal retrieved_path
        retrieved_path = path

    def log_callback(msg):
        # 校准模式下静默处理日志，不打印到终端
        pass

    try:
        if platform == "youtube":
            api_keys = platform_config.get("api_keys", [])
            max_results = platform_config.get("max_results", 10)

            run_youtube_spider(
                api_keys=api_keys,
                keywords_list=[keyword],
                max_results=max_results,
                limit_time_str="是",
                start_date=start_date,
                end_date=end_date,
                get_comments_str="否",
                max_comments=0,
                log_callback=log_callback,
                finish_callback=finish_callback,
                stop_event=stop_event,
                pause_event=pause_event,
                # 校准工具只走 API 模式，不启动浏览器
                config={"youtube_search_method": "仅API（消耗配额）"}
            )

        elif platform == "tiktok":
            cdp_url = platform_config.get("cdp_url", "http://localhost:9222")
            max_videos = platform_config.get("max_videos", 10)

            run_tiktok_spider(
                keywords_list=[keyword],
                max_videos=max_videos,
                max_candidates=max_videos * 3,
                limit_time_str="是",
                start_date=start_date,
                end_date=end_date,
                get_comments_str="否",
                max_comments=0,
                cdp_port_or_url=cdp_url,
                log_callback=log_callback,
                finish_callback=finish_callback,
                stop_event=stop_event,
                pause_event=pause_event
            )

        elif platform == "x_twitter":
            cdp_url = platform_config.get("cdp_url", "http://localhost:9222")
            max_scrolls = platform_config.get("max_scrolls", 2)

            adv_params = {
                "limit_time": "是",
                "start_date": start_date,
                "end_date": end_date,
                "get_comments": "否",
                "max_comments": 0,
                "lang": "any"
            }

            run_x_spider(
                keywords_list=[keyword],
                adv_params=adv_params,
                port=cdp_url,
                log_callback=log_callback,
                finish_callback=finish_callback,
                stop_event=stop_event,
                pause_event=pause_event,
                config={
                    "max_scrolls": max_scrolls,
                    "cooldown_min": 2.0,
                    "cooldown_max": 4.0,
                    "no_new_scroll_limit": 2,
                    "slice_days": days,
                    "max_parallel_tabs": 1
                }
            )
        else:
            print(f"Unknown platform: {platform}", file=sys.stderr)
            return set()

    except Exception as e:
        # 兜底：任何异常（限流、网络错误等）都不中断整体流程
        print(f"Exception raised running spider for platform {platform}, keyword '{keyword}': {e}", file=sys.stderr)
        return set()

    # 从爬虫输出的 Excel 中提取链接
    if retrieved_path:
        return extract_links_from_excel(retrieved_path, platform)

    return set()


def generate_reports(results: dict, output_path: str):
    """根据校准结果生成报告文件。

    支持两种格式（根据 output_path 后缀自动判断）：
    - .csv: 生成 CSV 表格，含 BOM 头以兼容 Excel 打开中文。
    - 其他: 生成 Markdown 格式的可读报告。

    Args:
        results: 校准结果字典，结构为 {游戏名: {baseline_query, platforms: {平台: {baseline_count, groups: [...]}}}}。
        output_path: 输出文件路径。
    """
    # 确保输出目录存在
    parent_dir = os.path.dirname(output_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    is_csv = output_path.lower().endswith(".csv")

    if is_csv:
        # CSV 格式输出
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Game", "Platform", "Baseline Query", "Baseline Count",
                "Keyword Group", "Group Count", "Intersection Count",
                "Volume Coverage (%)", "Intersection Coverage (%)"
            ])
            for game_name, game_data in results.items():
                baseline_query = game_data["baseline_query"]
                for platform, plat_data in game_data["platforms"].items():
                    baseline_cnt = plat_data["baseline_count"]
                    for grp in plat_data["groups"]:
                        grp_keywords = ", ".join(grp["keywords"])
                        writer.writerow([
                            game_name, platform, baseline_query, baseline_cnt,
                            grp_keywords, grp["group_count"], grp["intersection_count"],
                            grp["volume_coverage"], grp["intersection_coverage"]
                        ])
    else:
        # Markdown 格式输出
        md_lines = []
        md_lines.append("# Keyword Coverage Calibration Report")
        md_lines.append(f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md_lines.append("")

        for game_name, game_data in results.items():
            md_lines.append(f"## Game: {game_name}")
            md_lines.append(f"- **Baseline Query**: `{game_data['baseline_query']}`")
            md_lines.append("")

            for platform, plat_data in game_data["platforms"].items():
                md_lines.append(f"### Platform: {platform.upper()}")
                md_lines.append(f"- **Baseline Total Scraped**: {plat_data['baseline_count']}")
                md_lines.append("")
                md_lines.append("| Group Index | Keyword Combination | Group Count | Intersection | Volume Coverage | Intersection Coverage |")
                md_lines.append("|:---:|:---|:---:|:---:|:---:|:---:|")

                for idx, grp in enumerate(plat_data["groups"], 1):
                    grp_keywords = ", ".join([f"`{k}`" for k in grp["keywords"]])
                    md_lines.append(
                        f"| {idx} | {grp_keywords} | {grp['group_count']} | {grp['intersection_count']} | "
                        f"{grp['volume_coverage']}% | {grp['intersection_coverage']}% |"
                    )
                md_lines.append("")
            md_lines.append("---")
            md_lines.append("")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))


def run_calibration_task(config: dict, output_path: str, log_callback=None, stop_event=None, pause_event=None):
    """
    分离出的核心执行逻辑，供 GUI 或 main() 调用。
    """
    from src.core.timing import should_stop, wait_if_paused

    time_period = config.get("time_period", {})
    days_raw = time_period.get("days", 7)
    try:
        days = int(days_raw)
    except (ValueError, TypeError) as e:
        if log_callback: log_callback(f"Invalid days value in config (must be integer): {e}")
        raise ValueError(f"Invalid days value: {e}")

    if "start_date" in time_period and "end_date" in time_period:
        start_date_str = time_period["start_date"]
        end_date_str = time_period["end_date"]
    else:
        end_dt = datetime.datetime.now()
        start_dt = end_dt - datetime.timedelta(days=days)
        start_date_str = start_dt.strftime("%Y-%m-%d")
        end_date_str = end_dt.strftime("%Y-%m-%d")

    msg = f"Calibration period: {start_date_str} to {end_date_str} ({days} days)"
    print(msg)
    if log_callback: log_callback(msg)

    platforms = ["youtube", "tiktok", "x_twitter"]
    results = {}

    for game in config.get("games", []):
        if should_stop(stop_event): break
        wait_if_paused(pause_event, stop_event)

        game_name = game["name"]
        baseline_query = game["baseline_query"]
        keyword_groups = game.get("keyword_groups", [])

        msg = f"\nProcessing game: {game_name}"
        print(msg)
        if log_callback: log_callback(msg)
        
        results[game_name] = {
            "baseline_query": baseline_query,
            "platforms": {}
        }

        for platform in platforms:
            if should_stop(stop_event): break
            wait_if_paused(pause_event, stop_event)

            platform_config = config.get(platform, {})
            msg = f"  Running searches on platform: {platform}"
            print(msg)
            if log_callback: log_callback(msg)

            # 第一步：执行基准查询，获取基准链接集合
            baseline_links = run_platform_spider(
                platform=platform,
                keyword=baseline_query,
                start_date=start_date_str,
                end_date=end_date_str,
                platform_config=platform_config,
                days=days,
                stop_event=stop_event,
                pause_event=pause_event
            )

            results[game_name]["platforms"][platform] = {
                "baseline_count": len(baseline_links),
                "groups": []
            }

            # 第二步：遍历每个关键词组，合并组内所有关键词的链接
            for grp in keyword_groups:
                if should_stop(stop_event): break
                wait_if_paused(pause_event, stop_event)

                group_links = set()
                for kw in grp:
                    if should_stop(stop_event): break
                    wait_if_paused(pause_event, stop_event)

                    kw_links = run_platform_spider(
                        platform=platform,
                        keyword=kw,
                        start_date=start_date_str,
                        end_date=end_date_str,
                        platform_config=platform_config,
                        days=days,
                        stop_event=stop_event,
                        pause_event=pause_event
                    )
                    group_links.update(kw_links)

                # 第三步：计算覆盖率
                volume_cov, inter_cov = calculate_coverage(group_links, baseline_links)

                results[game_name]["platforms"][platform]["groups"].append({
                    "keywords": grp,
                    "group_count": len(group_links),
                    "intersection_count": len(group_links.intersection(baseline_links)),
                    "volume_coverage": volume_cov,
                    "intersection_coverage": inter_cov
                })

    if not should_stop(stop_event):
        # 生成校准报告
        generate_reports(results, output_path)
        msg = f"\nSuccessfully generated calibration report at {output_path}"
        print(msg)
        if log_callback: log_callback(msg)

    # 兼容 GUI：最终写入 finish_callback (可选) 可以在 GUI 包装层处理，此处仅负责逻辑
    return output_path


def main():
    """校准工具主入口：解析命令行参数 → 加载配置 → 逐游戏逐平台执行查询 → 生成报告。"""
    parser = argparse.ArgumentParser(description="Keyword Coverage Calibration Tool")
    parser.add_argument("--config", type=str, default="config/calibration_config.json", help="Path to configuration file")
    parser.add_argument("--output", type=str, default="output/calibration_report.md", help="Path to output report file")

    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Failed to load config: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        run_calibration_task(config, args.output)
    except Exception as e:
        print(f"Calibration failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
