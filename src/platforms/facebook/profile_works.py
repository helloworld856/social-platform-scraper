import os
from datetime import datetime
import re
from src.core import (
    MultiSheetXlsxWriter,
    connect_existing_chromium,
    should_stop,
    wait_if_paused,
)

def log_line(log_callback, message: str) -> None:
    if log_callback:
        log_callback(message)

def parse_date_range(start_date: str, end_date: str) -> tuple[datetime, datetime]:
    start_dt = datetime.strptime(start_date.strip(), "%Y-%m-%d")
    end_dt = datetime.strptime(end_date.strip(), "%Y-%m-%d")
    if start_dt > end_dt:
        raise ValueError("开始日期不能晚于结束日期。")
    return start_dt, end_dt

def parse_fb_time_string(time_str: str) -> datetime | None:
    text = (time_str or "").strip().lower()
    if not text:
        return None
    now = datetime.now()
    
    # 比如 "2小时前", "3 mins ago"
    match = re.search(r'(\d+)\s*(小?时|分钟|天|周|min|hr|hour|day|week|month|year)s?\s*(前|ago)?', text)
    if match:
        val = int(match.group(1))
        unit = match.group(2)
        from datetime import timedelta
        if unit in ('分钟', 'min'):
            return now - timedelta(minutes=val)
        elif unit in ('时', '小时', 'hr', 'hour'):
            return now - timedelta(hours=val)
        elif unit in ('天', 'day'):
            return now - timedelta(days=val)
        elif unit in ('周', 'week'):
            return now - timedelta(weeks=val)
        elif unit in ('month',):
            return now - timedelta(days=val*30)
        elif unit in ('year',):
            return now - timedelta(days=val*365)
    
    # 比如 "昨天 10:00", "yesterday at 10:00"
    if "昨天" in text or "yesterday" in text:
        return now - timedelta(days=1)
        
    # 比如 "3月15日", "March 15"
    match = re.search(r'(?:(?:20)?(\d{2})年)?\s*(\d{1,2})月(\d{1,2})日', text)
    if match:
        year_str, month_str, day_str = match.groups()
        year = int("20" + year_str) if year_str else now.year
        try:
            return datetime(year, int(month_str), int(day_str))
        except ValueError:
            pass
            
    # 标准格式回退
    match = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})', text)
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass
            
    return None

def in_date_range(publish_dt: datetime | None, start_dt: datetime, end_dt: datetime) -> bool:
    if not publish_dt:
        return False
    return start_dt.date() <= publish_dt.date() <= end_dt.date()


# 默认常量
PAGE_TIMEOUT_MS = 60000
SCROLL_DELAY_MS = 2000
SCROLL_PX = 800
NO_NEW_LIMIT = 5
SAVE_BATCH_SIZE = 10
COOLDOWN_MIN_SECONDS = 1.0
COOLDOWN_MAX_SECONDS = 3.0

def _get_output_path(profile_url: str) -> str:
    username = profile_url.rstrip("/").split("/")[-1].split("?")[0]
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("results", exist_ok=True)
    return os.path.join("results", f"facebook_{username}_{date_str}.xlsx")

def row_from_post(index: int, post: dict[str, str], profile_url: str) -> dict[str, str]:
    return {
        "序号": str(index),
        "类型": post.get("type", ""),
        "发布时间": post.get("published_at", ""),
        "帖子内容": post.get("content", ""),
        "媒体链接": post.get("media_links", ""),
        "浏览量(若为视频)": post.get("views", ""),
        "帖子链接": post.get("url", ""),
        "博主链接": profile_url,
    }

def extract_visible_posts(page, force_exact_time: bool, log_callback, stop_event, pause_event) -> list[dict[str, str]]:
    """提取页面上所有当前加载的文章节点并进行交互和解析"""
    # JS 探测器代码：分流处理视频和图文
    js_parser = """(articles) => {
        const results = [];
        for (const article of articles) {
            // Check if already processed
            if (article.dataset.parsed === '1') continue;
            article.dataset.parsed = '1';

            const isVideo = !!article.querySelector('video') || !!article.querySelector('div[data-video-id]');
            let content = '';
            let mediaLinks = [];
            let views = '';
            let url = '';
            
            // Extract URL (usually the time anchor)
            const timeAnchor = article.querySelector('a[role="link"][tabindex="0"]:has(span)');
            let timeStr = '';
            if (timeAnchor) {
                if (timeAnchor.href) url = timeAnchor.href;
                timeStr = timeAnchor.innerText;
            }

            if (isVideo) {
                const videoEl = article.querySelector('video');
                if (videoEl && videoEl.src) mediaLinks.push(videoEl.src);
                // content fallback
                content = article.innerText.substring(0, 500);
            } else {
                // Text/Image post
                const imgs = article.querySelectorAll('img');
                for (const img of imgs) {
                    if (img.src && !img.src.includes('emoji')) mediaLinks.push(img.src);
                }
                const textDivs = article.querySelectorAll('div[dir="auto"]');
                let texts = [];
                for (const div of textDivs) {
                    if (div.innerText) texts.push(div.innerText);
                }
                content = texts.join(' | ').substring(0, 500);
            }

            results.push({
                type: isVideo ? "video" : "text",
                content: content,
                media_links: mediaLinks.join(' | '),
                views: views,
                url: url,
                time_str: timeStr
            });
        }
        return results;
    }"""
    
    # Python 层触发 Hover
    if force_exact_time:
        try:
            # 找到所有包含链接的 article，对还未解析的时间戳进行悬浮
            articles = page.locator('div[role="article"]')
            count = articles.count()
            for i in range(count):
                if should_stop(stop_event):
                    break
                article = articles.nth(i)
                parsed = article.evaluate("el => el.dataset.time_parsed === '1'")
                if parsed:
                    continue
                
                # 寻找时间锚点
                time_anchors = article.locator('a[role="link"][tabindex="0"]')
                a_count = time_anchors.count()
                for j in range(a_count):
                    try:
                        time_anchors.nth(j).hover(timeout=1000)
                        page.wait_for_timeout(300)
                    except Exception:
                        pass
                article.evaluate("el => el.dataset.time_parsed = '1'")
        except Exception as e:
            log_line(log_callback, f"  悬浮获取时间失败: {e}")

    # 调用 JS 解析器
    posts_data = page.evaluate(js_parser, page.query_selector_all('div[role="article"]'))
    return posts_data

def collect_profile_works(page, profile_url: str, max_scrolls: int, limit_time_bool: bool, start_dt, end_dt, force_exact_time: bool,
                          log_callback, stop_event, pause_event, page_timeout, scroll_delay_val, no_new_limit, scroll_px_val, writer):
    
    log_line(log_callback, f"开始抓取主页: {profile_url}")
    page.goto(profile_url, timeout=page_timeout)
    page.wait_for_timeout(3000)
    
    seen_urls = set()
    no_new_count = 0
    total_written = 0

    for scroll_idx in range(max_scrolls):
        if should_stop(stop_event):
            break
        if wait_if_paused(pause_event, stop_event):
            break

        log_line(log_callback, f"滚动第 {scroll_idx + 1}/{max_scrolls} 次...")
        
        posts = extract_visible_posts(page, force_exact_time, log_callback, stop_event, pause_event)
        
        added = 0
        for p in posts:
            url = p.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            
            time_str = p.get("time_str", "")
            if limit_time_bool and start_dt and end_dt:
                publish_dt = parse_fb_time_string(time_str)
                p["published_at"] = time_str if not publish_dt else publish_dt.strftime("%Y-%m-%d %H:%M")
                if not publish_dt:
                    log_line(log_callback, f"      警告：无法解析 Facebook 时间（{time_str}），为防止误杀予以放行。")
                elif not in_date_range(publish_dt, start_dt, end_dt):
                    if publish_dt.date() < start_dt.date():
                        # Too old, maybe we should stop scrolling if we hit many old posts, but for now just skip
                        log_line(log_callback, f"      跳过：发布时间超出范围（{publish_dt.strftime('%Y-%m-%d')}）。")
                    else:
                        log_line(log_callback, f"      跳过：发布时间不在范围内（{publish_dt.strftime('%Y-%m-%d')}）。")
                    continue
            else:
                p["published_at"] = time_str

            row = row_from_post(total_written + 1, p, profile_url)
            writer.writerow("帖子内容", row)
            added += 1
            total_written += 1
            
        writer.save()
            
        if added == 0:
            no_new_count += 1
            if no_new_count >= no_new_limit:
                log_line(log_callback, f"连续 {no_new_limit} 次滚动没有新内容，结束采集。")
                break
        else:
            no_new_count = 0
            
        page.evaluate(f"window.scrollBy(0, {scroll_px_val});")
        page.wait_for_timeout(scroll_delay_val)
        
    log_line(log_callback, f"完成 {profile_url}，总计写入 {total_written} 条。")

def run_facebook_profile_works_spider(profile_urls_text: str, limit_time_str: str, start_date_str: str, end_date_str: str, force_exact_time_str: str,
                                      log_callback, stop_event, pause_event, **config) -> str:
    urls = [u.strip() for u in profile_urls_text.splitlines() if u.strip()]
    if not urls:
        return "未提供任何主页链接"
    
    limit_time_bool = (limit_time_str == "是")
    force_exact_time = (force_exact_time_str == "是")
    start_dt = None
    end_dt = None
    if limit_time_bool:
        start_dt, end_dt = parse_date_range(start_date_str, end_date_str)
    
    page_timeout = int(config.get("page_load_timeout", PAGE_TIMEOUT_MS))
    scroll_delay_val = int(config.get("scroll_delay", SCROLL_DELAY_MS))
    scroll_px_val = int(config.get("scroll_px", SCROLL_PX))
    no_new_limit = int(config.get("no_new_scroll_limit", NO_NEW_LIMIT))
    max_scrolls = int(config.get("max_scrolls", 200))
    save_batch_size = int(config.get("save_batch_size", SAVE_BATCH_SIZE))
    
    try:
        browser, playwright_context, sync_playwright = connect_existing_chromium()
        if not browser:
            log_line(log_callback, "无法连接到本地浏览器，请确保以调试模式启动 Chrome。")
            return "浏览器连接失败"
            
        page = browser.contexts[0].new_page()
        
        for url in urls:
            if should_stop(stop_event):
                break
            output_path = _get_output_path(url)
            writer = MultiSheetXlsxWriter(output_path, ["帖子内容"])
            try:
                collect_profile_works(page, url, max_scrolls, limit_time_bool, start_dt, end_dt, force_exact_time,
                                      log_callback, stop_event, pause_event, page_timeout, scroll_delay_val, no_new_limit, scroll_px_val, writer)
            except Exception as e:
                log_line(log_callback, f"抓取 {url} 时发生错误: {e}")
            finally:
                writer.save()
                
        page.close()
        browser.close()
        if playwright_context:
            playwright_context.stop()
        
        return "采集全部完成"
    except Exception as e:
        return f"运行异常: {e}"
