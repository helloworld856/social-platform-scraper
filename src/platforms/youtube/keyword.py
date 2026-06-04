# -*- coding: utf-8 -*-
"""YouTube 关键词搜索采集核心模块。

本模块提供基于关键词的 YouTube 视频挖掘逻辑，
支持“仅API（消耗配额）”模式和“浏览器优先（模拟搜索省配额）”模式。
浏览器优先模式利用 Playwright 打开搜索结果页面，并通过向下滚动模拟拉取大量视频 ID，
之后再批量请求 API 接口获取视频指标，从而节省 99% 的 API 每日配额消耗。
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build

from src.core import XlsxRowWriter, MultiSheetXlsxWriter, build_output_path, sanitize_csv_rows, should_stop, wait_if_paused
from src.platforms.youtube.comments import fetch_top_level_comments, format_youtube_datetime

# Excel 输出表头字段定义
CSV_FIELDS = [
    "搜索词",
    "序号",
    "视频标题",
    "视频时长",
    "播放量",
    "点赞数",
    "发布时间",
    "视频链接",
    "作者主页链接",
]

# 默认时间限制窗口：最近一年
DEFAULT_START_DATE = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
DEFAULT_END_DATE = datetime.now().strftime("%Y-%m-%d")


def parse_date_range(start_date: str, end_date: str) -> tuple[datetime, datetime]:
    """解析以 "YYYY-MM-DD" 格式指定的日期字符串，并返回带有时区信息的 datetime 元组。"""
    start_dt = datetime.strptime(start_date.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt = datetime.strptime(end_date.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if start_dt > end_dt:
        raise ValueError("开始日期不能晚于结束日期")
    return start_dt, end_dt


def youtube_rfc3339(dt: datetime) -> str:
    """将 datetime 时间对象格式化为 YouTube API 支持的 RFC3339 字符串（Z 结尾）。"""
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def format_youtube_duration(iso_duration: str) -> str:
    """将 YouTube 返回的 ISO 8601 时长格式转换为标准时间格式（HH:MM:SS）。"""
    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?",
        iso_duration or "",
    )
    if not match:
        return ""

    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0) + days * 24
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def chunked(values: list[str], size: int) -> list[list[str]]:
    """将列表数据分块，便于批次处理。"""
    return [values[index:index + size] for index in range(0, len(values), size)]


def safe_filename_part(value: str) -> str:
    """将关键词清理并转换为可用于文件名的安全标识字串，防止非法路径字符引发报错。"""
    cleaned = re.sub(r'[\\/*?:"<>|]', "", value or "").strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:80] or "keyword"


def iter_search_video_id_batches(youtube, keyword: str, max_results: int, limit_time_bool: bool, start_dt: datetime | None, end_dt: datetime | None, log_callback, stop_event=None, pause_event=None, batch_size: int = 50):
    """【API模式】分页向 API 接口发起 search 检索，生成当前批次的视频 ID 列表。

    此方式会消耗较多的 YouTube 每日 API 配额（每次搜索消费 100 quota 单位）。

    Yields:
        list[str]: 批次视频 ID 列表。
    """
    seen_video_ids: set[str] = set()
    next_page_token = None

    while len(seen_video_ids) < max_results:
        if should_stop(stop_event):
            log_callback("任务已停止。")
            break
        if wait_if_paused(pause_event, stop_event):
            break

        params = {
            "part": "id",
            "q": keyword,
            "type": "video",
            "order": "relevance",
            "maxResults": min(batch_size, max_results - len(seen_video_ids)),
            "pageToken": next_page_token,
        }
        if limit_time_bool and start_dt and end_dt:
            params["publishedAfter"] = youtube_rfc3339(start_dt)
            params["publishedBefore"] = youtube_rfc3339(end_dt + timedelta(days=1))
            
        response = youtube.search().list(**params).execute()

        batch_ids: list[str] = []
        for item in response.get("items", []):
            if should_stop(stop_event):
                break
            video_id = item.get("id", {}).get("videoId", "")
            if video_id and video_id not in seen_video_ids:
                batch_ids.append(video_id)
                seen_video_ids.add(video_id)

        if batch_ids:
            log_callback(f"  {keyword}: 已找到 {len(seen_video_ids)} 个日期范围内的视频")
            yield batch_ids

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break


def fetch_video_rows(youtube, keyword: str, video_ids: list[str], stop_event=None, pause_event=None, batch_size: int = 50) -> list[dict]:
    """批量获取指定视频 ID 的详情指标（播放量、点赞数等），封装为导出格式。"""
    rows: list[dict] = []
    for ids in chunked(video_ids, batch_size):
        if should_stop(stop_event):
            break
        if wait_if_paused(pause_event, stop_event):
            break
        response = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=",".join(ids),
            maxResults=50,
        ).execute()

        for item in response.get("items", []):
            if should_stop(stop_event):
                break
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            content = item.get("contentDetails", {})
            video_id = item.get("id", "")
            channel_id = snippet.get("channelId", "")
            rows.append(
                {
                    "搜索词": keyword,
                    "序号": "",
                    "视频标题": snippet.get("title", ""),
                    "视频时长": format_youtube_duration(content.get("duration", "")),
                    "播放量": stats.get("viewCount", ""),
                    "点赞数": stats.get("likeCount", ""),
                    "发布时间": format_youtube_datetime(snippet.get("publishedAt", "")),
                    "视频链接": f"https://www.youtube.com/watch?v={video_id}",
                    "作者主页链接": f"https://www.youtube.com/channel/{channel_id}" if channel_id else "",
                }
            )
    return rows


def collect_video_ids_with_playwright(page, keyword: str, max_results: int, log_callback, stop_event=None, pause_event=None) -> list[str]:
    """【浏览器优先模式】利用无头浏览器访问搜索页面并滚动，动态拦截解析页面上的所有视频链接。

    此方式不消耗任何 Google API 搜索配额，是极度省配额的首选加载方案。

    Args:
        page: Playwright 页面实例。
        keyword: 搜索关键词。
        max_results: 预期搜集数上限。
        log_callback: 日志通知。
        stop_event: 中断事件。
        pause_event: 暂停事件。

    Returns:
        list[str]: 抓取去重后的视频 ID 列表。
    """
    from src.core import interruptible_sleep
    import urllib.parse

    log_callback(f"  [浏览器优先] 搜索关键词：{keyword}...")
    video_ids: list[str] = []
    seen = set()

    try:
        encoded_kw = urllib.parse.quote(keyword)
        url = f"https://www.youtube.com/results?search_query={encoded_kw}"
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        
        if interruptible_sleep(2.0, stop_event):
            return []

        try:
            # 尝试等待视频元素渲染
            page.wait_for_selector('ytd-video-renderer, ytd-reel-item-renderer', timeout=15000)
        except Exception:
            log_callback("  [浏览器优先] 未能即时等待到视频卡片，尝试直接向下滚动解析。")

        no_new_count = 0
        scroll_delay = 1.0
        scroll_px = 2500
        
        target_collect_limit = max_results
        
        log_callback(f"  [浏览器优先] 开始滚动加载视频链接 (目标收集量: {target_collect_limit})...")
        
        # 允许最大滚动 100 轮
        for scroll_index in range(100):
            if should_stop(stop_event):
                break
            if wait_if_paused(pause_event, stop_event):
                break

            # 从 DOM 树里提取所有 watch 和 shorts 链接对应的视频 ID
            current_ids = page.evaluate("""() => {
                const ids = [];
                for (const a of document.querySelectorAll('a[href*="/watch?v="], a[href*="/shorts/"]')) {
                    const href = a.getAttribute('href') || '';
                    const match = href.match(/(?:v=|\\/shorts\\/)([A-Za-z0-9_-]{6,})/);
                    if (match && match[1]) {
                        ids.push(match[1]);
                    }
                }
                return ids;
            }""")
            
            added = 0
            for vid in current_ids:
                if vid not in seen:
                    seen.add(vid)
                    video_ids.append(vid)
                    added += 1

            if added > 0:
                log_callback(f"    第 {scroll_index + 1} 次滚动：新增 {added} 条，已累计 {len(video_ids)} 条。")
                no_new_count = 0
            else:
                no_new_count += 1
                # 连续 8 次未搜集到新链接，认为列表内容已拉取到底
                if no_new_count >= 8:
                    log_callback("    连续 8 次无新增链接，判定已加载到底。")
                    break

            if len(video_ids) >= target_collect_limit:
                log_callback(f"    已收集到 {len(video_ids)} 条链接，已达到目标数量。")
                break

            # 向下滚动预设像素值以触发懒加载
            page.evaluate(f"window.scrollBy(0, {scroll_px})")
            if interruptible_sleep(scroll_delay, stop_event):
                break

    except Exception as e:
        log_callback(f"  [浏览器优先] Playwright 采集过程异常：{e}")

    return video_ids


def run_youtube_spider(api_key, keywords_list, max_results, limit_time_str, start_date, end_date, get_comments_str, max_comments, log_callback, finish_callback, stop_event=None, config=None, pause_event=None):
    """运行 YouTube 关键词视频采集与评论导出任务的主驱动函数。

    Args:
        api_key: API Key。
        keywords_list: 关键词列表（行划分）。
        max_results: 每个词的最大搜集数量。
        limit_time_str: 是否限制发布时间窗口（"是"/"否"）。
        start_date: 开始日期 "YYYY-MM-DD"。
        end_date: 结束日期 "YYYY-MM-DD"。
        get_comments_str: 是否获取评论信息。
        max_comments: 每个视频提取的最大扫描评论数。
        log_callback: 日志通知。
        finish_callback: 结束通知。
        stop_event: 中断事件。
        config: 高阶环境配置字典。
        pause_event: 暂停事件。
    """
    if config is None:
        config = {}
    search_batch_size = int(config.get("youtube_search_batch_size", 50))
    video_batch_size = int(config.get("youtube_video_batch_size", 50))
    comment_top_limit = int(config.get("comment_top_limit", 100))
    search_method = config.get("youtube_search_method", "浏览器优先（省配额）")
    use_browser = (search_method == "浏览器优先（省配额）")

    output_path = None
    output_paths: list[str] = []
    playwright_context = None
    browser = None
    try:
        limit_time_bool = limit_time_str == "`是"
        get_comments_bool = get_comments_str == "是"
        start_dt, end_dt = None, None
        if limit_time_bool:
            start_dt, end_dt = parse_date_range(start_date, end_date)

        youtube = build("youtube", "v3", developerKey=api_key)
        run_stamp = time.strftime("%Y%m%d_%H%M%S")

        # 尝试使用无头浏览器连接环境，获取视频链接
        if use_browser:
            from playwright.sync_api import sync_playwright
            from src.core import connect_existing_chromium, DEFAULT_X_CDP_URL
            try:
                playwright_context = sync_playwright().start()
                browser, _ = connect_existing_chromium(playwright_context, DEFAULT_X_CDP_URL, log_callback=log_callback)
                log_callback("  [浏览器优先] Chromium 已连接。")
            except Exception as e:
                log_callback(f"  [浏览器优先] 浏览器启动失败 ({e})，将使用 API 模式。")
                use_browser = False

        for index, keyword in enumerate(keywords_list, 1):
            if should_stop(stop_event):
                log_callback("任务已停止。")
                break
            if wait_if_paused(pause_event, stop_event):
                break
            output_path = build_output_path(
                "youtube",
                f"youtube_keyword_{safe_filename_part(keyword)}_{run_stamp}.xlsx",
            )
            output_paths.append(output_path)

            if get_comments_bool:
                comment_fields = ["序号", "视频链接", "评论的点赞量", "评论内容", "评论发布时间"]
                writer = MultiSheetXlsxWriter(output_path, {"视频信息": CSV_FIELDS, "评论信息": comment_fields})
            else:
                writer = XlsxRowWriter(output_path, CSV_FIELDS)
            serial_number = 1
            log_callback(f"[{index}/{len(keywords_list)}] 搜索关键词：{keyword}")
            log_callback(f"  输出文件：{output_path}")
            if limit_time_bool:
                log_callback(f"  日期范围：{start_date} 至 {end_date}")
            else:
                log_callback("  日期范围：不限时间")
            
            all_video_ids = []
            
            # 浏览器模式优先搜集
            if use_browser and browser:
                page = None
                try:
                    page = browser.new_page()
                    all_video_ids = collect_video_ids_with_playwright(page, keyword, max_results, log_callback, stop_event, pause_event)
                    if not all_video_ids:
                        log_callback("  [浏览器优先] 未获取到任何视频 ID，将 Fallback 自动切换到 API 模式。")
                except Exception as e:
                    log_callback(f"  [浏览器优先] 模式失败 ({e})，将 Fallback 自动切换到 API 模式。")
                finally:
                    if page:
                        try:
                            page.close()
                        except Exception:
                            pass
            
            # 若浏览器模式未返回 ID 或获取失败，兜底切换至 API 搜索模式
            if not all_video_ids:
                log_callback("  使用 API 搜索模式获取视频 ID 列表中...")
                try:
                    for batch_ids in iter_search_video_id_batches(youtube, keyword, max_results, limit_time_bool, start_dt, end_dt, log_callback, stop_event, pause_event, search_batch_size):
                        all_video_ids.extend(batch_ids)
                        if len(all_video_ids) >= max_results:
                            break
                except Exception as exc:
                    log_callback(f"  API 搜索失败: {exc}")
                    
            written_count = 0
            log_callback(f"  共获取到 {len(all_video_ids)} 个待查询的视频 ID，开始分批获取详情并写入...")
            
            for chunk_ids in chunked(all_video_ids, video_batch_size):
                if should_stop(stop_event):
                    break
                if wait_if_paused(pause_event, stop_event):
                    break
                
                rows = fetch_video_rows(youtube, keyword, chunk_ids, stop_event, pause_event, video_batch_size)
                
                # 针对浏览器模式获取的 ID，在 API 获取详细信息后在本地执行时间筛选过滤
                if limit_time_bool and start_dt and end_dt:
                    filtered_rows = []
                    for r in rows:
                        pub_str = r.get("发布时间", "")
                        if pub_str:
                            try:
                                pub_dt = datetime.strptime(pub_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                                if start_dt <= pub_dt <= end_dt:
                                    filtered_rows.append(r)
                            except Exception:
                                filtered_rows.append(r)
                    rows = filtered_rows
                
                if written_count + len(rows) > max_results:
                    rows = rows[:max_results - written_count]
                
                if not rows:
                    continue
                    
                for row in rows:
                    row["序号"] = str(serial_number)
                    
                    if get_comments_bool:
                        try:
                            video_id = (row["视频链接"].split("v=")[1] if "v=" in row["视频链接"] else "").split("&")[0]
                            comments = fetch_top_level_comments(youtube, video_id, max_comments, log_callback, stop_event, pause_event)
                            comments.sort(key=lambda item: item["like_count"], reverse=True)
                            for comment in comments[:comment_top_limit]:
                                comment_row = {
                                    "序号": row["序号"],
                                    "视频链接": row["视频链接"],
                                    "评论的点赞量": str(comment["like_count"]),
                                    "评论内容": comment["text"],
                                    "评论发布时间": comment.get("published_at", "")
                                }
                                writer.writerow("评论信息", comment_row)
                        except Exception as exc:
                            log_callback(f"    提取评论失败：{exc}")
                            
                    serial_number += 1
                
                if get_comments_bool:
                    for r in rows:
                        writer.writerow("视频信息", r)
                else:
                    writer.writerows(sanitize_csv_rows(rows))
                
                written_count += len(rows)
                log_callback(f"  已写入 {written_count} 条视频")
                
                if written_count >= max_results:
                    break
                    
            writer.save()
            log_callback(f"  写入完成，共 {written_count} 条视频")
 
        log_callback("完成，已按关键词分别保存：")
        for path in output_paths:
            log_callback(f"  {path}")
    except Exception as exc:
        log_callback(f"运行失败：{exc}")
        output_path = None
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        if playwright_context:
            try:
                playwright_context.stop()
            except Exception:
                pass
        finish_callback(output_paths[-1] if output_paths else output_path)
