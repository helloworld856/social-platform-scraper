import time


TITLE_SELECTORS = [
    "[data-e2e='browse-video-desc']",
    "[data-e2e='video-desc']",
    "[data-e2e='video-title']",
    "h1[data-e2e='browse-video-desc']",
    "h1[data-e2e='video-desc']",
    "h1[data-e2e='video-title']",
    "h1",
    "h2",
    "strong[data-e2e='browse-video-desc']",
]

META_SELECTORS = [
    "meta[property='og:description']",
    "meta[name='description']",
]


def clean_tiktok_title(text):
    if not text:
        return ""

    cleaned = str(text).replace("\n", " ").replace("\r", " ").strip()
    cleaned = cleaned.replace(" | TikTok", "").strip()
    cleaned = " ".join(cleaned.split())

    if cleaned.lower() in {"tiktok", "unknown", "未知", "未知标题"}:
        return ""
    return cleaned


def _extract_text_from_scope(scope, selector):
    try:
        node = scope.query_selector(selector)
        if not node:
            return ""
        if selector.startswith("meta["):
            return clean_tiktok_title(node.get_attribute("content"))
        return clean_tiktok_title(node.inner_text())
    except Exception:
        return ""


def extract_tiktok_video_title(page, retries=2, retry_delay=1.5):
    for attempt in range(retries + 1):
        for selector in TITLE_SELECTORS:
            title = _extract_text_from_scope(page, selector)
            if title:
                return title

        for selector in META_SELECTORS:
            title = _extract_text_from_scope(page, selector)
            if title:
                return title

        if attempt < retries:
            time.sleep(retry_delay)

    try:
        return clean_tiktok_title(page.title())
    except Exception:
        return "未知标题"


def resolve_tiktok_card_container(element):
    try:
        handle = element.evaluate_handle(
            "el => el.closest('[data-e2e=\"user-post-item\"], [data-e2e=\"user-post-item-list\"], article') || "
            "el.parentElement || el"
        )
        container = handle.as_element()
        return container or element
    except Exception:
        return element


def extract_tiktok_title_from_card(element):
    container = resolve_tiktok_card_container(element)

    for selector in TITLE_SELECTORS:
        title = _extract_text_from_scope(container, selector)
        if title:
            return title

    return "未知"
