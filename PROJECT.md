# Project: Three-Zone Scraper Concurrency Safety & Config Integration Audit

## Architecture
- **Scraper Tools**: 14 Playwright-based scraper tools under `src/platforms/` (Facebook, Instagram, TikTok, X/Twitter).
- **Concurrency Management**: ThreadPoolExecutor/asyncio concurrency execution. Playwright browser and context management must be thread-safe.
- **XLSX Writing**: Safe concurrent writing to Excel via `writer_lock`.
- **Config & UI Integration**: PyQt5 UI forms -> config files -> spider parameter injection.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| 1 | Concurrency & Leak Audit | Conduct static and dynamic exploration of all 14 scrapers to identify Playwright leaks, XLSX locking issues, and hardcoded sleeps. | None | DONE |
| 2 | Code Cleanup & Config Extraction | Extract hardcoded sleeps, fix concurrency safety, ensure proper ThreadPoolExecutor cleanup, and expose config parameters. | M1 | DONE |
| 3 | Config Validation & Integration Testing | Build integration tests verifying config passing and concurrent safety; validate UI-to-spider configuration paths. | M2 | DONE |
| 4 | Final Report & Verification | Compile `audit_report.md` at the project root, run full test suite, and run Forensic Auditor. | M3 | DONE |

## Interface Contracts
- **Playwright Context**: Every scraper thread/task must manage its own Playwright instance/context locally and close it in a `finally` block.
- **XLSX Concurrent Writing**: Thread-safe operations on excel sheets using global/shared lock mechanisms.
- **Configuration Passing**: UI parameters must map cleanly to config files and pass to the runner/spider function signatures.

## Code Layout
- `src/platforms/facebook/` - Facebook scraper tools & manifest.
- `src/platforms/instagram/` - Instagram scraper tools & manifest.
- `src/platforms/tiktok/` - TikTok scraper tools & manifest.
- `src/platforms/x_twitter/` - X/Twitter scraper tools & manifest.
- `src/core/` - Core utilities including Excel writing.
- `test/` - Integration and unit tests.
