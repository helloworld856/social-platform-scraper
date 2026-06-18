# 关键词覆盖率校准工具 - 配置规范指南

校准工具的配置通过 JSON 文件进行控制（默认路径为 `config/calibration_config.json`）。该文件分为三个主要部分：**时间配置**、**平台配置**、以及**游戏关键词规则配置**。

## 完整配置示例

```json
{
  "time_period": {
    "days": 7
  },
  "youtube": {
    "api_keys": ["YOUR_YOUTUBE_API_KEY"],
    "max_results": 10
  },
  "tiktok": {
    "cdp_url": "http://localhost:9222",
    "max_videos": 10
  },
  "x_twitter": {
    "cdp_url": "http://localhost:9222",
    "max_scrolls": 2
  },
  "games": [
    {
      "name": "Genshin Impact",
      "baseline_query": "原神",
      "keyword_groups": [
        ["原神 攻略", "原神 角色"],
        ["Genshin Impact guide", "Genshin Impact showcase"]
      ]
    }
  ]
}
```

---

## 字段详细说明

### 1. 时间配置 (`time_period`)
定义爬虫检索数据的时间范围。
* **支持两种写法**：
  * **按天数自动计算 (推荐)**：
    * `"days": 7` （表示自动检索过去 7 天的数据，结束时间为工具运行的当前时间）。
  * **显式指定起止日期**：
    * `"start_date": "2024-01-01"`
    * `"end_date": "2024-01-07"`

### 2. 平台配置
针对三大平台的运行时参数控制。
* **`youtube`**：
  * `"api_keys"` (列表): YouTube Data V3 API Key 数组。由于使用 "仅API" 模式运行，此项**必须填写有效 Key**，留空会报错。
  * `"max_results"` (数字): 每个关键词在 YouTube 上最多采集多少条数据。
* **`tiktok`**：
  * `"cdp_url"` (字符串): 连接 CDP 调试协议的地址，默认 `"http://localhost:9222"`。
  * `"max_videos"` (数字): 每个关键词最多采集多少视频。
* **`x_twitter`**：
  * `"cdp_url"` (字符串): 同上。
  * `"max_scrolls"` (数字): 最大滚动加载次数。

### 3. 游戏配置 (`games`)
定义需要对比覆盖率的游戏和关键词组合列表，工具将依次遍历处理。
* **`name`** (字符串): 游戏名称（仅用于最终报告展示）。
* **`baseline_query`** (字符串): 基准查询词。通常是官方全名，它的搜索结果数量将作为 100% 分母计算其余组合的相对覆盖率。
* **`keyword_groups`** (二维数组): 要测试的组合列表。
  * 每个子数组（例如 `["原神 攻略", "原神 角色"]`）作为一个**组合（Group）**。
  * 组合内所有关键词检索出的链接会被**合并并去重**，最终以此去重集合计算该组合的覆盖率。
  * *目的：探查诸如 “中文主词+外文主词” 的总覆盖率。*

## 运行逻辑机制
1. 工具首先使用 `baseline_query` 进行一次查询，获取基础结果池 (Baseline Pool)。
2. 然后针对每个 Keyword Group 内的每个词进行独立查询，并将返回链接合并。
3. 最后输出**两项覆盖率指标**：
   * **Volume Coverage（总覆盖率）**：关键词组链接总数 / 基准链接数。该值可能超过 100%（因为可能搜出一些不包含基准词的拓展数据）。
   * **Intersection Coverage（交集覆盖率）**：关键词组提取到的链接中，**有多少条同样存在于基准结果池中**，除以基准链接数。该值最高为 100%，反映的是对基准数据的“捕获”能力。
