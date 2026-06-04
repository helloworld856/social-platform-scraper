# CLAUDE.md - Project Guidelines for three-zone-scraper

## Project Overview
A `PyQt5`-based desktop application designed for social media data extraction from YouTube, TikTok, X/Twitter, Instagram, and Facebook. It includes an AIGC content validation engine (powered by `langgraph` and DeepSeek) and utilities for merging `XLSX` files based on keywords.

## Setup and Execution
- **Python Version**: 3.10+ (Recommended: 3.11 or 3.12).
- **Dependencies**: 
  ```bash
  pip install -r requirements.txt
  python -m playwright install chromium
  ```
- **Execution**: 
  ```bash
  python main.py
  ```
- **Environment Variables**: Create a `.env` file in the root directory for AIGC judgment features:
  ```env
  DEEPSEEK_API_KEY=your_api_key
  DEEPSEEK_BASE_URL=https://api.deepseek.com
  DEEPSEEK_MODEL_NAME=deepseek-chat
  ```

## Architecture and Directory Structure
- `main.py`: Application entry point.
- `src/studio/`: Core studio UI, tool registry, and subprocess launchers.
- `src/ui/`: Shared UI base classes and configuration dialogs (`config_dialog.py`).
- `src/core/`: Utility modules for `XLSX` writing, number parsing, text cleaning, Chrome CDP protocols, and waiting mechanisms.
- `src/platforms/`: Individual platform scraper implementations:
  - `youtube/`: Utilizes `google-api-python-client` with a fallback to `playwright`.
  - `tiktok/`: Powered by `playwright`.
  - `x_twitter/`: Powered by `playwright`.
  - `instagram/`: Powered by `playwright`.
  - `facebook/`: Powered by `playwright` (includes Profile Works Scraper and Keyword Search Scraper, supports optional comments extraction, custom post limit, and recent sorting).
- `src/judge_aigc/`: AI-generated content judgment engine utilizing `langchain` and `langgraph`.
- `src/processing/`: AIGC entry points and `XLSX` file merging logic.
- `user_data/`: Directory for storing persistent Playwright browser sessions/profiles.
- `output/`: Default directory for `.xlsx` export files. Contains `output/temp/` for intermediate files.

## Development Conventions
- **Code Linter & Formatter**: `ruff`.
  - `line-length = 150`.
  - Ignored rules: `E402` (module level import not at top of file), `F841` (local variable assigned but never used).
- **UI Framework**: `PyQt5`.
- **Browser Automation**: `playwright`. Persistent contexts are used to maintain user login states across sessions, storing data in `user_data/`. 
  - *Note*: Always use `with sync_playwright() as p:` and pass `p` to `connect_existing_chromium(p, DEFAULT_X_CDP_URL)` to handle browser connectivity.
- **Excel Handling**: `openpyxl`. 
  - *Note*: When using `MultiSheetXlsxWriter`, you must initialize it with a dictionary mapping sheet names to lists of headers (e.g. `{"Sheet1": ["Col1", "Col2"]}`). For single sheet simple writes, `XlsxRowWriter` takes a flat list of headers.
- **Data Input**: TXT files (one record per line). Ignore lines starting with `#` and empty lines.
- **Data Output**: Primarily `.xlsx` files written to platform-specific subdirectories inside `output/`.
- **Error Handling**: Network requests and browser automations should include retries and handle timeouts gracefully. Implement random waiting intervals during batch operations to prevent rate-limiting.
