# 项目贡献规范 (Contributing Guidelines)

感谢你对本项目的关注并愿意贡献代码！为了保证代码库的质量与一致性，请在提交代码前仔细阅读以下规范。

## 1. 分支管理与 PR 提交

- 请从 `main` 分支拉取最新的代码，并基于最新代码创建独立的 feature 或是 bugfix 分支。
- **需求与 Issue 拆解**：在着手解决 Issue 时，需先针对 Issue 描述进行合理的任务拆解。在创建 PR 时，必须基于拆解出的清单，明确标示本次 PR 已经修复/实现的部分，以及哪些细分子项尚未修复（或留待后续 PR 解决）。
- 提交 PR (Pull Request) 时，请务必使用项目内置的 Pull Request 模板，详细填写变更说明、关联 Issue 以及测试情况。
- 提交信息 (Commit Message) 需保持清晰客观，建议使用规范的格式 `<type>: <description>`。如果是修复或逻辑变更，建议注明「原逻辑」和「新逻辑」。

## 2. 代码风格与规范

本项目主要使用 Python 语言开发，强制使用 `ruff` 进行静态代码分析。

- **静态检查**：提交前必须在项目根目录运行 `ruff check .` 并确保所有检查通过。
- **注释与文档**：
  - 核心逻辑、复杂的正则表达式、多线程通信机制等，**必须**配备清晰的中文注释说明。
  - 所有核心模块的函数与类，必须包含中文 Docstring 说明其用途。
- **命名规范**：遵循 Python 的 PEP 8 规范，变量与函数名必须使用能够清晰表达意图的英文，严禁使用拼音或无意义缩写。

## 3. 爬虫核心 API 使用原则

在新增或修改 `src/platforms/` 下的爬虫脚本时，必须使用 `src.core` 中提供的核心组件：

- **任务状态控制 (必须)**：
  - 在循环或耗时操作中，**必须**使用 `should_stop(stop_event)` 定期检查用户是否请求了终止任务。
  - 在每一次核心操作（如翻页、提取元素）前，建议使用 `wait_if_paused(pause_event, stop_event)` 来响应用户界面的“暂停/恢复”操作。
- **延时与防风控**：
  - **严禁**使用原生的 `time.sleep`（会导致多线程阻塞且无法响应终止指令）。必须使用 `interruptible_sleep(duration, stop_event)`。
  - 在请求间隙请使用 `random_cooldown(log_callback, stop_event, min_sec, max_sec)` 来模拟人类随机停顿。
- **文件保存**：
  - 采集结果或其他本地文件的路径构建，**必须**统一调用 `build_output_path(platform, filename)`，禁止硬编码绝对路径。
- **敏感信息**：
  - 绝对禁止在代码库中硬编码账户密码、Cookie、Token 或任何个人隐私信息。

## 4. 工具注册规范

当新增一款数据采集工具时：
- 必须在该平台目录下（如 `src/platforms/tiktok/`）为新脚本创建配套的 `*.manifest.json` 文件。
- 该 JSON 文件应包含工具的 `id`、`name`、`description` 及其所需的输入 `config` 定义，以保证程序启动时主界面 UI 能自动生成对应表单。

## 5. 本地测试标准

发起 PR 前，请自行在本地完成以下验证工作：

1. **语法规范检测**：
   ```bash
   ruff check .
   ```
2. **单元测试与 UI 测试**：
   ```bash
   python test/test_visibility.py
   pytest
   ```
3. **冒烟测试**：
   在带界面的模式下手动运行 `python main.py`，选中你修改的工具，完成一次基础工作流，确保日志输出正常，并且能够成功生成最终数据表文件。
