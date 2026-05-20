# 三平台数据爬取工具

一个 PyQt 桌面工具台，用于集中启动 YouTube、TikTok、X/Twitter 三个平台的数据采集工具，以及 AIGC 判断和关键词 XLSX 合并工具。

## 启动

首次运行请先安装依赖和 Playwright 浏览器：

```bash
pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

TikTok 和 X/Twitter 工具会自动使用项目根目录下的 `user_data/` 启动 Chrome 调试浏览器。首次使用时，请在打开的浏览器中登录对应平台。

AIGC 判断工具需要提前配置 `.env`。推荐在项目根目录下创建 `.env` 并配置：

```env
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_NAME=deepseek-chat
```

同时兼容旧变量名：`API_KEY`、`BASE_URL`、`MODEL_NAME`。

## 结构

- `main.py`：项目入口。
- `src/studio/`：PyQt 主工具台、工具注册表、独立工具进程启动器。
- `src/ui/`：PyQt 工具窗口公共基类。
- `src/core/`：输出路径、XLSX 写入、数字转换、文本清洗、Chrome CDP、等待机制等公共能力。
- `src/platforms/youtube/`：YouTube 的 4 个工具。
- `src/platforms/tiktok/`：TikTok 的 4 个工具。
- `src/platforms/x_twitter/`：X/Twitter 的 4 个工具。
- `src/processing/`：AIGC 标题判断、关键词 XLSX 合并。
- `output/`：默认输出目录。

## 工具

- YouTube：关键词视频基础信息、作者信息提取、目标视频前后指标、视频高赞主楼评论。
- TikTok：关键词视频基础信息、博主信息提取、目标视频前后指标、视频高赞主楼评论。
- X/Twitter：关键词媒体推文搜索、推文作者资料提取、目标推文前后指标、推文高赞主楼评论。
- 数据处理：AIGC 标题判断、关键词 XLSX 合并。
