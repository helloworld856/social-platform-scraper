# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A PyQt5 desktop tool station for centralized web scraping across YouTube, TikTok, and X/Twitter, plus AIGC title classification and XLSX merging.

## Commands

```bash
# Install dependencies and Playwright browser
pip install -r requirements.txt
python -m playwright install chromium

# Launch the desktop tool station
python main.py

# Run a single tool directly (bypassing the launcher)
python -m src.studio.tool_runner --tool-id <tool_id>

# List available tool IDs
python -m src.studio.tool_runner --tool-id <id> --check
```

Tool IDs (from `src/studio/registry.py`): `youtube_keyword_mining`, `youtube_channel_profiles`, `youtube_paired_context_metrics`, `youtube_top_comments`, `tiktok_keyword_metrics`, `tiktok_profile_directory`, `tiktok_paired_context_metrics`, `tiktok_top_comments`, `x_keyword_video_search`, `x_tweet_author_profiles`, `x_paired_context_metrics`, `x_top_comments`, `judge_aigc`, `xlsx_merge`.

## Architecture

### Two-layer process model

The main window (`src/studio/qt_app.py`) launches individual tool windows as **separate QProcess** instances via `tool_runner.py`. Each tool gets its own Python process to avoid blocking the launcher. Tools communicate results via `log_callback` + `finish_callback` signals.

YouTube tools require a **Google API key** (field `api_key`). TikTok and X/Twitter tools connect to a **local Chrome via CDP** (port 9222 by default). The project auto-launches Chrome with `--remote-debugging-port=9222` and persists login state in `<workspace_root>/user_data/`.

### Platform scraping strategies

- **YouTube**: Uses `googleapiclient` (YouTube Data API v3). `src/platforms/youtube/context.py` contains the channel resolution, upload playlist pagination, and video detail fetching logic shared across YouTube tools.
- **TikTok**: Uses Playwright CDP (`connect_existing_chromium`). Two-tier approach: first tries TikTok's internal API (`/api/post/item_list/`) via `page.evaluate` fetch with `secUid`; if the API doesn't find the target video, falls back to scrolling the user's profile grid (`fallback_rows_from_profile`).
- **X/Twitter**: Uses Playwright CDP. Three-tier approach: first tries author search (`from:<handle> since:... until:...`), then profile timeline scrolling (`/with_replies`, `/media` variants), finally opens the target tweet page to reverse-lookup the author profile and re-scan.

### Shared core (`src/core/`)

| Module | Purpose |
|---|---|
| `browser.py` | Chrome CDP connection: find executable, launch with `--remote-debugging-port`, connect Playwright |
| `output.py` | Platform-specific output dirs under `output/` — maps platform names to `youtube/`, `tiktok/`, `x/` |
| `xlsx.py` | `XlsxRowWriter` — incremental XLSX writer with temp-file atomic saves via `os.replace` |
| `csv_utils.py` | Strips newlines from cell values for CSV/XLSX compatibility |
| `number_format.py` | `expand_compact_number` — converts "1.2K" → "1200", handles CJK units (万/亿) |
| `timing.py` | `should_stop`, `interruptible_sleep`, `random_cooldown` — cooperative stop-event checks |
| `tiktok_metadata.py` | DOM selectors for extracting video titles from TikTok page state |

### UI layer (`src/ui/base.py`)

`SimpleToolWindow(QWidget)` is the base for all tool windows. Subclasses define a list of `FieldSpec` (text, multiline, int, combo, file, folder) and implement `run_task(values, log_callback, finish_callback, stop_event)`. The base handles: Start/Stop buttons, worker thread management, log display, and stop-event propagation.

### Tool registry pattern

All tools are declared in `src/studio/registry.py` as `ToolSpec` dataclasses with a unique `tool_id`, `category` (YouTube/TikTok/X-Twitter/数据处理), `entrypoint` (dotted path to a QWidget class or factory), `implementation_path`, and `tags`. The launcher uses these for search, filtering, and QProcess instantiation.

### AIGC judge (`src/judge_aigc/`)

Two-stage classification: local keyword/Unicode-range detection runs first (fast, free); unresolved titles are sent to DeepSeek via LangChain LangGraph for final determination. Configured via `.env` (`DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL_NAME`). Batch processing with incremental XLSX saves and existing-row deduplication.

### pytok submodule (`src/pytok/`)

Vendored TikTok scraping library with its own dual-approach (TikTok-Api with zendriver browser fallback). This is a dependency of the broader project, not directly imported by the platform tools in `src/platforms/tiktok/` (which use Playwright directly).

## Key patterns

- All scraper entry functions (`run_*_spider`, `run_scraper`) follow the same signature: `(required_params, ..., log_callback, finish_callback, stop_event)`. They call `finish_callback(output_path)` on completion.
- Output goes to `output/<platform>/` with date-stamped filenames. Paths are built via `build_output_path(platform, filename)`.
- Input TXT files use tab-separated pairs (`video_url\tprofile_url`) or one URL per line, with `#` comment lines supported.
- Chrome user data persists in `<workspace_root>/user_data/` — first login persists across sessions.
