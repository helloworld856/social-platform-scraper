from __future__ import annotations

from datetime import datetime
import random
import re
import time
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    PlaywrightTimeoutError = TimeoutError
    sync_playwright = None

from src.core import (
    DEFAULT_X_CDP_URL,
    XlsxRowWriter,
    build_output_path,
    connect_existing_chromium,
    sanitize_csv_cell,
    should_stop,
    wait_if_paused,
)


CSV_FIELDS = ["序号", "作品ID", "作品链接", "发布时间", "作品内容", "浏览量", "评论数", "点赞数"]
PAGE_LOAD_TIMEOUT = 45000
INITIAL_LOAD_DELAY = 3.2
SCROLL_DELAY = 2.5
SCROLL_PX = 2600
NO_NEW_SCROLL_LIMIT = 8
SAVE_BATCH_SIZE = 10
COOLDOWN_MIN_SECONDS = 9.0
COOLDOWN_MAX_SECONDS = 22.0
DEFAULT_MAX_WORKS = 10000
DEFAULT_MAX_SCROLLS = 160

FACEBOOK_HOSTS = {"facebook.com", "www.facebook.com", "m.facebook.com", "web.facebook.com"}
BLOCKED_PROFILE_NAMES = {
    "ads",
    "bookmarks",
    "events",
    "friends",
    "gaming",
    "groups",
    "help",
    "marketplace",
    "messages",
    "notifications",
    "pages",
    "photo",
    "photos",
    "profile.php",
    "reel",
    "reels",
    "search",
    "stories",
    "story.php",
    "watch",
}


def log_line(log_callback, text: str):
    if log_callback:
        log_callback(text)


def clean_profile_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""
    if value.startswith("//"):
        value = "https:" + value
    if value.startswith("/"):
        value = "https://www.facebook.com" + value
    if not value.startswith("http"):
        value = "https://" + value

    parsed = urlparse(value)
    host = parsed.netloc.lower()
    if host not in FACEBOOK_HOSTS:
        return ""

    path = parsed.path.rstrip("/") or "/"
    query = parse_qs(parsed.query)
    if path == "/profile.php":
        profile_id = (query.get("id") or [""])[0].strip()
        return f"https://www.facebook.com/profile.php?id={profile_id}" if profile_id else ""

    parts = [part for part in path.split("/") if part]
    if not parts:
        return ""
    username = parts[0].strip()
    if not username or username.lower() in BLOCKED_PROFILE_NAMES:
        return ""
    return f"https://www.facebook.com/{username}"


def parse_profile_urls(text: str) -> list[str]:
    urls: list[str] = []
    seen = set()
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        url = clean_profile_url(stripped.split()[0])
        if url and url not in seen:
            urls.append(url)
            seen.add(url)
    return urls


def profile_label(profile_url: str) -> str:
    parsed = urlparse(clean_profile_url(profile_url))
    if parsed.path == "/profile.php":
        return parse_qs(parsed.query).get("id", ["profile"])[0] or "profile"
    return parsed.path.strip("/") or "profile"


def profile_section_urls(profile_url: str) -> list[str]:
    base = clean_profile_url(profile_url).rstrip("/")
    if not base:
        return []

    parsed = urlparse(base)
    if parsed.path == "/profile.php":
        query = parse_qs(parsed.query)
        profile_id = (query.get("id") or [""])[0]
        if not profile_id:
            return [base]
        return [
            f"https://www.facebook.com/profile.php?id={profile_id}",
            f"https://www.facebook.com/profile.php?id={profile_id}&sk=posts",
            f"https://www.facebook.com/profile.php?id={profile_id}&sk=reels_tab",
        ]

    return [base, f"{base}/posts", f"{base}/reels"]


def normalize_work_url(href: str) -> str:
    value = (href or "").strip().replace("\\/", "/").replace("\\u002F", "/")
    if not value:
        return ""
    if value.startswith("//"):
        value = "https:" + value
    if value.startswith("/"):
        value = "https://www.facebook.com" + value
    if not value.startswith("http"):
        return ""

    parsed = urlparse(value)
    if parsed.netloc.lower() not in FACEBOOK_HOSTS:
        return ""

    path = re.sub(r"/+", "/", parsed.path)
    query = parse_qs(parsed.query)
    keep_query: dict[str, str] = {}
    for key in ("story_fbid", "id", "fbid", "v"):
        value_list = query.get(key)
        if value_list and value_list[0]:
            keep_query[key] = value_list[0]

    if path == "/permalink.php" and keep_query.get("story_fbid"):
        return urlunparse(("https", "www.facebook.com", path, "", urlencode(keep_query), ""))
    if path == "/story.php" and keep_query.get("story_fbid"):
        return urlunparse(("https", "www.facebook.com", path, "", urlencode(keep_query), ""))
    if path == "/photo.php" and keep_query.get("fbid"):
        return urlunparse(("https", "www.facebook.com", path, "", urlencode({"fbid": keep_query["fbid"]}), ""))
    if path == "/watch/" and keep_query.get("v"):
        return urlunparse(("https", "www.facebook.com", path, "", urlencode({"v": keep_query["v"]}), ""))

    if re.search(r"^/(?:[^/]+/)?(?:posts|videos|photos|reel|reels)/(?:[^/]+/)?[A-Za-z0-9_.:-]+", path, re.I):
        return urlunparse(("https", "www.facebook.com", path.rstrip("/"), "", "", ""))

    return ""


def extract_work_id(work_url: str) -> str:
    parsed = urlparse(work_url)
    query = parse_qs(parsed.query)
    for key in ("story_fbid", "fbid", "v"):
        value = (query.get(key) or [""])[0]
        if value:
            return value

    patterns = [
        r"/reel/([^/?#]+)",
        r"/reels/([^/?#]+)",
        r"/posts/([^/?#]+)",
        r"/videos/([^/?#]+)",
        r"/photos/(?:[^/]+/)?([^/?#]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, parsed.path, re.I)
        if match:
            return match.group(1)
    return ""


def normalize_metric_text(text: str) -> str:
    value = re.sub(r"\s+", " ", text or "").strip()
    if not value:
        return ""
    match = re.search(r"(\d[\d,.]*(?:\.\d+)?\s*(?:K|M|B|万|萬|亿|億)?)", value, re.I)
    return match.group(1).strip() if match else ""


def format_facebook_time(raw_time: str) -> str:
    value = (raw_time or "").strip()
    if not value:
        return ""
    if value.isdigit():
        number = int(value)
        if number > 100000000000:
            number = number // 1000
        try:
            return datetime.fromtimestamp(number).strftime("%Y-%m-%d %H:%M:%S")
        except (OverflowError, OSError, ValueError):
            return value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value


FACEBOOK_NAV_TEXTS = {
    "home",
    "watch",
    "marketplace",
    "groups",
    "gaming",
    "menu",
    "notifications",
    "messenger",
    "messages",
    "profile",
    "friends",
    "search",
}


def clean_facebook_content_text(text: str) -> str:
    lines = []
    for line in (text or "").splitlines():
        value = re.sub(r"\s+", " ", line).strip()
        if not value:
            continue
        if value.lower() in FACEBOOK_NAV_TEXTS:
            continue
        lines.append(value)
    return "\n".join(lines).strip()


def build_content(text: str, media_type: str) -> str:
    cleaned = clean_facebook_content_text(text)
    media_type = (media_type or "").lower()

    if media_type == "video":
        title = cleaned.splitlines()[0].strip() if cleaned else ""
        return f"{title}[视频]" if title else "[视频]"

    placeholders = []
    if media_type in {"image", "photo", "carousel"}:
        placeholders.append("[图片]")
    if media_type == "mixed":
        placeholders.extend(["[图片]", "[视频]"])

    if cleaned and placeholders:
        return cleaned + "\n" + "".join(placeholders)
    if cleaned:
        return cleaned
    return "".join(placeholders) if placeholders else ""


def extract_visible_work_links(page) -> list[dict[str, str]]:
    return page.evaluate(
        """() => {
            const results = [];
            const seen = new Set();
            const normalize = href => {
                if (!href) return '';
                href = String(href).replaceAll('\\\\/', '/').replaceAll('\\u002F', '/');
                try {
                    const url = new URL(href, location.origin);
                    if (!/(^|\\.)facebook\\.com$/i.test(url.hostname)) return '';
                    const query = url.searchParams;
                    if (url.pathname === '/permalink.php' && query.get('story_fbid')) {
                        return `https://www.facebook.com/permalink.php?story_fbid=${query.get('story_fbid')}${query.get('id') ? `&id=${query.get('id')}` : ''}`;
                    }
                    if (url.pathname === '/story.php' && query.get('story_fbid')) {
                        return `https://www.facebook.com/story.php?story_fbid=${query.get('story_fbid')}${query.get('id') ? `&id=${query.get('id')}` : ''}`;
                    }
                    if (url.pathname === '/photo.php' && query.get('fbid')) {
                        return `https://www.facebook.com/photo.php?fbid=${query.get('fbid')}`;
                    }
                    if (url.pathname === '/watch/' && query.get('v')) {
                        return `https://www.facebook.com/watch/?v=${query.get('v')}`;
                    }
                    if (/\\/(posts|videos|photos|reel|reels)\\//i.test(url.pathname)) {
                        return `https://www.facebook.com${url.pathname.replace(/\\/$/, '')}`;
                    }
                } catch (error) {}
                return '';
            };
            const detectType = (href, node) => {
                const lower = href.toLowerCase();
                if (lower.includes('/reel/') || lower.includes('/reels/') || lower.includes('/videos/') || lower.includes('/watch/')) return 'video';
                if (lower.includes('/photo')) return 'image';
                const root = node ? (node.closest('[role="article"], article, div') || node) : null;
                if (!root) return '';
                if (root.querySelector('video, a[href*="/reel/"], a[href*="/watch/"], a[href*="/videos/"]')) return 'video';
                if (root.querySelector('img, a[href*="/photo"]')) return 'image';
                return '';
            };
            const add = (href, node = null) => {
                href = normalize(href);
                if (!href || seen.has(href)) return;
                seen.add(href);
                results.push({ link: href, mediaType: detectType(href, node) });
            };
            for (const link of document.querySelectorAll('a[href]')) {
                const href = link.getAttribute('href') || link.href || '';
                if (/(\\/posts\\/|\\/videos\\/|\\/photos\\/|\\/reel\\/|\\/reels\\/|\\/watch\\/|story_fbid=|fbid=)/i.test(href)) {
                    add(href, link);
                }
            }
            return results;
        }"""
    )


def facebook_page_debug_info(page) -> dict[str, str | int]:
    return page.evaluate(
        """() => ({
            url: location.href,
            title: document.title || '',
            bodyText: (document.body ? document.body.innerText : '').slice(0, 240),
            linkCount: document.querySelectorAll('a').length,
            articleCount: document.querySelectorAll('[role="article"], article').length,
        })"""
    )


def collect_section_work_links(page, section_url: str, max_works: int, max_scrolls: int, log_callback, stop_event=None, pause_event=None, page_timeout=None, scroll_delay=None, scroll_px=None, no_new_limit=None) -> list[dict[str, str]]:
    if page_timeout is None:
        page_timeout = PAGE_LOAD_TIMEOUT
    if scroll_delay is None:
        scroll_delay = SCROLL_DELAY
    if scroll_px is None:
        scroll_px = SCROLL_PX
    if no_new_limit is None:
        no_new_limit = NO_NEW_SCROLL_LIMIT

    page.goto(section_url, wait_until="domcontentloaded", timeout=page_timeout)
    time.sleep(INITIAL_LOAD_DELAY)

    works: list[dict[str, str]] = []
    seen = set()
    no_new_count = 0
    log_line(log_callback, f"  打开页面：{section_url}")

    for scroll_index in range(max(1, int(max_scrolls or DEFAULT_MAX_SCROLLS))):
        if should_stop(stop_event) or len(works) >= max_works:
            break
        if wait_if_paused(pause_event, stop_event):
            break

        added = 0
        for item in extract_visible_work_links(page):
            link = normalize_work_url(item.get("link", ""))
            work_id = extract_work_id(link)
            if not link or not work_id or link in seen:
                continue
            seen.add(link)
            works.append({"id": work_id, "link": link, "media_type": item.get("mediaType", "")})
            added += 1
            if len(works) >= max_works:
                break

        if added:
            log_line(log_callback, f"    滚动 {scroll_index + 1}/{max_scrolls}：新增 {added} 条，当前页面累计 {len(works)} 条。")
            no_new_count = 0
        else:
            no_new_count += 1
            if scroll_index == 0:
                info = facebook_page_debug_info(page)
                log_line(
                    log_callback,
                    f"    首次扫描未发现作品链接：url={info.get('url')} title={info.get('title')} "
                    f"links={info.get('linkCount')} articles={info.get('articleCount')}",
                )
            if no_new_count >= no_new_limit:
                break

        page.evaluate(f"window.scrollBy(0, {scroll_px})")
        time.sleep(scroll_delay)

    return works


def collect_profile_work_links(page, profile_url: str, max_works: int, max_scrolls: int, log_callback, stop_event=None, pause_event=None, page_timeout=None, scroll_delay=None, scroll_px=None, no_new_limit=None) -> list[dict[str, str]]:
    urls = profile_section_urls(profile_url)
    if not urls:
        raise ValueError(f"无效的 Facebook 作者主页链接：{profile_url}")

    max_works = max(1, int(max_works or DEFAULT_MAX_WORKS))
    max_scrolls = max(1, int(max_scrolls or DEFAULT_MAX_SCROLLS))
    merged: list[dict[str, str]] = []
    seen_ids = set()

    for section_url in urls:
        if should_stop(stop_event) or len(merged) >= max_works:
            break
        try:
            section_items = collect_section_work_links(page, section_url, max_works - len(merged), max_scrolls, log_callback, stop_event, pause_event, page_timeout=page_timeout, scroll_delay=scroll_delay, scroll_px=scroll_px, no_new_limit=no_new_limit)
        except PlaywrightTimeoutError:
            log_line(log_callback, f"  跳过页面：加载超时 {section_url}")
            continue

        for item in section_items:
            work_id = item.get("id", "")
            if not work_id or work_id in seen_ids:
                continue
            seen_ids.add(work_id)
            merged.append(item)
            if len(merged) >= max_works:
                break

    return merged


def extract_detail_from_page(page, fallback_media_type: str) -> dict[str, str]:
    return page.evaluate(
        """({ fallbackMediaType }) => {
            const text = node => node ? (node.innerText || node.textContent || '').trim() : '';
            const meta = name => {
                const node = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
                return node ? (node.getAttribute('content') || '').trim() : '';
            };
            const bodyText = document.body ? (document.body.innerText || '') : '';
            const navTexts = new Set([
                'home',
                'watch',
                'marketplace',
                'groups',
                'gaming',
                'menu',
                'notifications',
                'messenger',
                'messages',
                'profile',
                'friends',
                'search',
            ]);
            const cleanLines = value => (value || '')
                .split('\\n')
                .map(line => line.trim())
                .filter(Boolean)
                .filter(line => !navTexts.has(line.toLowerCase()))
                .filter(line => !/^(Like|Comment|Share|Send|Follow|See more|See less|All reactions:|赞|评论|分享|发送|关注|查看更多|收起)$/i.test(line));
            const visibleTextCandidates = () => {
                const selectors = [
                    '[data-ad-comet-preview="message"]',
                    '[data-ad-preview="message"]',
                    '[data-testid="post_message"]',
                    '[role="article"] div[dir="auto"]',
                    'article div[dir="auto"]',
                ];
                const values = [];
                for (const selector of selectors) {
                    for (const node of document.querySelectorAll(selector)) {
                        const value = cleanLines(text(node)).join('\\n').trim();
                        if (value && value.length > 1 && value.length < 5000) values.push(value);
                    }
                }
                values.sort((a, b) => b.length - a.length);
                return values;
            };
            const extractByRegex = (patterns, source = bodyText) => {
                for (const pattern of patterns) {
                    const match = source.match(pattern);
                    if (match && match[1]) return match[1].trim();
                }
                return '';
            };
            const html = document.documentElement ? document.documentElement.innerHTML : '';
            const textCandidates = visibleTextCandidates();
            let contentText = textCandidates[0] || meta('og:description') || meta('description') || '';
            contentText = contentText
                .replace(/^Facebook\\s*:\\s*/i, '')
                .replace(/\\s+\\|\\s+Facebook$/i, '')
                .trim();

            let mediaType = fallbackMediaType || '';
            const path = location.pathname.toLowerCase();
            const mediaRoot = document.querySelector('[role="article"], article') || document.querySelector('[role="main"]') || document;
            if (path.includes('/reel') || path.includes('/videos') || path.includes('/watch')) {
                mediaType = 'video';
            } else if (path.includes('/photo')) {
                mediaType = mediaType || 'image';
            } else if (!mediaType && mediaRoot.querySelector('video')) {
                mediaType = 'video';
            } else if (!mediaType && mediaRoot.querySelector('a[href*="photo.php"], img[src*="fbcdn"]')) {
                mediaType = mediaType || 'image';
            }

            const publishedAt = (
                meta('article:published_time') ||
                extractByRegex([/"publish_time"\\s*:\\s*([0-9]+)/, /"creation_time"\\s*:\\s*([0-9]+)/], html) ||
                (() => {
                    const abbr = document.querySelector('abbr[data-utime]');
                    if (abbr) return abbr.getAttribute('data-utime') || '';
                    const time = document.querySelector('time[datetime]');
                    if (time) return time.getAttribute('datetime') || '';
                    const labelled = Array.from(document.querySelectorAll('a[aria-label], span[aria-label]'))
                        .map(node => node.getAttribute('aria-label') || '')
                        .find(value => /\\d{4}|at|上午|下午|昨天|前|May|June|Jan|Feb|Mar|Apr|Jul|Aug|Sep|Oct|Nov|Dec/i.test(value));
                    return labelled || '';
                })()
            );

            const attrTexts = Array.from(document.querySelectorAll('[aria-label], [title]'))
                .flatMap(node => [node.getAttribute('aria-label') || '', node.getAttribute('title') || ''])
                .filter(Boolean);
            const metaTexts = [
                meta('og:description'),
                meta('description'),
                meta('twitter:description'),
            ].filter(Boolean);
            const metricText = [bodyText, ...attrTexts, ...metaTexts].join('\\n');
            const lines = cleanLines(metricText);
            const findMetricLine = patterns => {
                for (const line of lines) {
                    if (patterns.some(pattern => pattern.test(line))) return line;
                }
                return '';
            };
            const numberPattern = '([0-9][0-9,.]*\\\\s*(?:K|M|B|万|萬|亿|億)?)';
            const findMetricByLabels = labels => {
                const labelPattern = labels.join('|');
                const afterNumber = new RegExp(`${numberPattern}\\\\s*(?:${labelPattern})`, 'i');
                const beforeNumber = new RegExp(`(?:${labelPattern})[^0-9]{0,24}${numberPattern}`, 'i');
                for (const source of [metricText, ...lines]) {
                    const afterMatch = source.match(afterNumber);
                    if (afterMatch && afterMatch[1]) return afterMatch[1];
                    const beforeMatch = source.match(beforeNumber);
                    if (beforeMatch && beforeMatch[1]) return beforeMatch[1];
                }
                return '';
            };
            const views = (
                extractByRegex([/"play_count"\\s*:\\s*([0-9]+)/, /"video_view_count"\\s*:\\s*([0-9]+)/, /"view_count"\\s*:\\s*([0-9]+)/, /"views_count"\\s*:\\s*([0-9]+)/, /"viewCount"\\s*:\\s*([0-9]+)/, /"video_view_count"\\s*:\\s*{[^}]*"count"\\s*:\\s*([0-9]+)/], html) ||
                findMetricByLabels(['views?', 'plays?', '播放', '观看', '次观看'])
            );
            const comments = (
                extractByRegex([/"comment_count"\\s*:\\s*([0-9]+)/, /"comments_count"\\s*:\\s*([0-9]+)/, /"total_comment_count"\\s*:\\s*([0-9]+)/, /"comment_count"\\s*:\\s*{[^}]*"total_count"\\s*:\\s*([0-9]+)/, /"comments"\\s*:\\s*{[^}]*"count"\\s*:\\s*([0-9]+)/], html) ||
                findMetricByLabels(['comments?', 'replies?', '评论', '留言', '則留言', '条留言'])
            );
            const likes = (
                extractByRegex([/"reaction_count"\\s*:\\s*([0-9]+)/, /"like_count"\\s*:\\s*([0-9]+)/, /"top_reactions"\\s*:[\\s\\S]{0,300}?"reaction_count"\\s*:\\s*([0-9]+)/, /"reaction_count"\\s*:\\s*{[^}]*"count"\\s*:\\s*([0-9]+)/, /"i18n_reaction_count"\\s*:\\s*"([^"]+)"/], html) ||
                findMetricByLabels(['reactions?', 'likes?', '赞', '讚'])
            );

            return { contentText, mediaType, publishedAt, views, comments, likes };
        }""",
        {"fallbackMediaType": fallback_media_type or ""},
    )


def enrich_work_detail(page, work: dict[str, str], page_timeout=None) -> dict[str, str]:
    if page_timeout is None:
        page_timeout = PAGE_LOAD_TIMEOUT
    page.goto(work["link"], wait_until="domcontentloaded", timeout=page_timeout)
    time.sleep(INITIAL_LOAD_DELAY)
    detail = extract_detail_from_page(page, work.get("media_type", ""))
    media_type = detail.get("mediaType") or work.get("media_type", "")
    return {
        "id": work.get("id", ""),
        "link": work.get("link", ""),
        "published_at": format_facebook_time(detail.get("publishedAt", "")),
        "content": build_content(detail.get("contentText", ""), media_type),
        "views": normalize_metric_text(detail.get("views", "")),
        "comments": normalize_metric_text(detail.get("comments", "")),
        "likes": normalize_metric_text(detail.get("likes", "")),
    }


def row_from_work(index: int, work: dict[str, str]) -> dict[str, str]:
    return {
        "序号": str(index),
        "作品ID": sanitize_csv_cell(work.get("id", "")),
        "作品链接": sanitize_csv_cell(work.get("link", "")),
        "发布时间": sanitize_csv_cell(work.get("published_at", "")),
        "作品内容": sanitize_csv_cell(work.get("content", "")),
        "浏览量": sanitize_csv_cell(work.get("views", "")),
        "评论数": sanitize_csv_cell(work.get("comments", "")),
        "点赞数": sanitize_csv_cell(work.get("likes", "")),
    }


def cooldown_after_batch(batch_count: int, log_callback, stop_event=None, cooldown_min=None, cooldown_max=None):
    if cooldown_min is None:
        cooldown_min = COOLDOWN_MIN_SECONDS
    if cooldown_max is None:
        cooldown_max = COOLDOWN_MAX_SECONDS
    if batch_count <= 0:
        return
    seconds = random.uniform(cooldown_min, cooldown_max)
    log_line(log_callback, f"    已保存 {batch_count} 条，随机等待 {seconds:.1f} 秒。")
    deadline = time.time() + seconds
    while time.time() < deadline:
        if should_stop(stop_event):
            break
        time.sleep(min(0.5, deadline - time.time()))


def run_facebook_profile_works_spider(
    profile_urls_text: str,
    cdp_port_or_url: str = DEFAULT_X_CDP_URL,
    max_works: int = DEFAULT_MAX_WORKS,
    max_scrolls: int = DEFAULT_MAX_SCROLLS,
    log_callback=None,
    finish_callback=None,
    stop_event=None,
    config=None,
    pause_event=None,
):
    if config is None:
        config = {}
    page_timeout_val = int(config.get("page_load_timeout", PAGE_LOAD_TIMEOUT))
    scroll_delay_val = float(config.get("scroll_delay", SCROLL_DELAY))
    scroll_px_val = int(config.get("scroll_px", SCROLL_PX))
    no_new_limit_val = int(config.get("no_new_scroll_limit", NO_NEW_SCROLL_LIMIT))
    save_batch_val = int(config.get("save_batch_size", SAVE_BATCH_SIZE))
    cooldown_min_val = float(config.get("cooldown_min", COOLDOWN_MIN_SECONDS))
    cooldown_max_val = float(config.get("cooldown_max", COOLDOWN_MAX_SECONDS))
    max_scrolls = int(config.get("max_scrolls", max_scrolls))

    completed_path = None
    page = None
    try:
        if sync_playwright is None:
            log_line(log_callback, "缺少依赖：playwright。请先安装 requirements.txt 中的依赖。")
            return

        profile_urls = parse_profile_urls(profile_urls_text)
        if not profile_urls:
            log_line(log_callback, "未读取到有效的 Facebook 作者主页链接。")
            return

        output_path = build_output_path("facebook", f"facebook_profile_works_{time.strftime('%Y%m%d')}.xlsx")
        writer = XlsxRowWriter(output_path, CSV_FIELDS)
        serial_number = 1

        with sync_playwright() as playwright:
            log_line(log_callback, "正在连接本地 Chrome，请确认已登录 Facebook。")
            try:
                _, context = connect_existing_chromium(playwright, cdp_port_or_url, log_callback=log_callback)
            except Exception as exc:
                log_line(log_callback, f"无法连接浏览器：{exc}")
                log_line(log_callback, "连接失败：请确认 Chrome 已打开，并已登录 Facebook。")
                return

            page = context.new_page()

            for profile_index, profile_url in enumerate(profile_urls, 1):
                if should_stop(stop_event):
                    log_line(log_callback, "任务已停止。")
                    break
                if wait_if_paused(pause_event, stop_event):
                    break

                label = profile_label(profile_url)
                log_line(log_callback, f"[{profile_index}/{len(profile_urls)}] 读取作者主页：{profile_url}")
                pending_rows = []
                written_count = 0
                try:
                    links = collect_profile_work_links(page, profile_url, max_works, max_scrolls, log_callback, stop_event, pause_event, page_timeout=page_timeout_val, scroll_delay=scroll_delay_val, scroll_px=scroll_px_val, no_new_limit=no_new_limit_val)
                    log_line(log_callback, f"  {label} 共收集到 {len(links)} 条作品链接，开始读取详情。")
                    for item_index, work in enumerate(links, 1):
                        if should_stop(stop_event):
                            break
                        if wait_if_paused(pause_event, stop_event):
                            break
                        try:
                            detail = enrich_work_detail(page, work, page_timeout=page_timeout_val)
                            pending_rows.append(row_from_work(serial_number, detail))
                            serial_number += 1
                            log_line(log_callback, f"    [{item_index}/{len(links)}] 完成：{work['link']}")
                            if len(pending_rows) >= save_batch_val:
                                writer.writerows(pending_rows)
                                writer.save()
                                written_count += len(pending_rows)
                                pending_rows.clear()
                                cooldown_after_batch(written_count, log_callback, stop_event, cooldown_min=cooldown_min_val, cooldown_max=cooldown_max_val)
                        except PlaywrightTimeoutError:
                            log_line(log_callback, f"    跳过：作品详情页加载超时：{work['link']}")
                        except Exception as exc:
                            log_line(log_callback, f"    跳过：{work['link']}：{exc}")

                    if pending_rows:
                        writer.writerows(pending_rows)
                        writer.save()
                        written_count += len(pending_rows)
                        pending_rows.clear()
                    log_line(log_callback, f"  完成 {label}：写入 {written_count} 条。")
                except Exception as exc:
                    log_line(log_callback, f"  跳过：{exc}")

        completed_path = output_path
        writer.save()
        log_line(log_callback, f"完成，已保存：{output_path}")
    finally:
        try:
            if page and not page.is_closed():
                page.close()
        except Exception:
            pass
        if finish_callback:
            finish_callback(completed_path)
