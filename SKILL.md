---
name: 亚马逊产品研究员
description: Amazon 产品全链路深度研究助手。输入一句话（产品名/ASIN/描述），自动完成产品搜索→多产品评论采集→AI情感打标→关键词扩展→VOC痛点聚类→竞品分析→新品机会分析→输出完整交互式HTML可视化报告。覆盖8大分析阶段，一站式Amazon产品调研。
version: 1.0.0
triggers:
  - keywords: ["亚马逊分析", "Amazon产品研究", "Amazon选品", "亚马逊选品", "竞品分析", "评论分析", "关键词研究", "VOC分析", "痛点聚类", "新品机会", "Amazon research", "product research"]
  - asin_patterns: ["B0[A-Z0-9]{8}"]
  - url_patterns: ["amazon\\.[a-z.]+/dp/", "amazon\\.[a-z.]+/.*?/dp/"]
author: WorkBuddy
icon: 🛍️
skill_type: user
location: user
allowed-tools:
  - Read
  - Write
  - Bash
  - WebFetch
  - WebSearch
  - Task
---

# 🛍️ Amazon 产品研究员

> 一句话输入 → 全链路自动分析 → 完整交互式报告

---

## 核心能力

```
输入: "bluetooth earbuds noise cancelling" 或 "B0CHX1W1XY" 或 "AirPods Pro 2"
  ↓
1️⃣  智能输入解析 —— 自动识别 ASIN/产品名/URL
2️⃣  多产品评论采集 —— 主产品 + Top 5 竞品评论
3️⃣  AI 深度打标 —— 情感/痛点/卖点/场景/用户画像 (10维标注)
4️⃣  关键词研究 —— 评论词频 + Amazon Suggest 扩展 + 长尾词
5️⃣  差评深度分析 —— 根因分析 + 严重度分级 + 改进优先级
6️⃣  VOC 痛点聚类 —— 客户之声主题聚类 + 期望/需求挖掘
7️⃣  竞品分析 —— 价格/评分/评论全维度对比 + 差距分析
8️⃣  新品机会分析 —— 市场缺口/利基机会/风险评估/行动计划
  ↓
📊 输出: 交互式 HTML 可视化报告 (Chart.js 图表 + 可折叠面板)
```

---

## 使用方式

### 基本用法

```bash
# 产品名搜索
python scripts/main.py "bluetooth earbuds"

# ASIN 直接分析
python scripts/main.py B0CHX1W1XY

# 一句话描述
python scripts/main.py "best noise cancelling headphones under 100"
```

### 指定市场和AI

```bash
# 指定市场 + API Key
python scripts/main.py "kitchen knife set" --market UK --api-key sk-xxx

# 使用 DeepSeek
python scripts/main.py "smart watch" \
  --api-key sk-xxx \
  --api-base https://api.deepseek.com/v1 \
  --model deepseek-chat

# 输出到指定文件
python scripts/main.py "yoga mat" --output my_report.html

# 纯规则统计（无需API，速度更快）
python scripts/main.py "phone case" --no-ai

# 调试模式
python scripts/main.py "headphones" --debug
```

### 在 WorkBuddy 对话中调用

当用户说 "分析这个 Amazon 产品 B0CHX1W1XY" 或 "帮我研究 amazon 上的蓝牙耳机" 时，自动运行：

```bash
cd C:/Users/PC/.workbuddy/skills/amazon-product-research/scripts
python main.py "<用户输入>" --output "<输出路径>"
```

然后 `present_files` 展示生成的 HTML 报告。

---

## 环境要求

- Python 3.8+
- `pip install -r requirements.txt` (仅需 requests)
- AI 深度分析需要 OpenAI/DeepSeek 兼容 API Key（可选，无 Key 用规则统计）

---

## 报告内容详解

生成的 HTML 报告包含以下板块：

| 板块 | 内容 |
|------|------|
| 📊 分析总览 | 综合评分、评论数、情感分布、机会评分 |
| 💬 评论分析 | 评分分布图 (Chart.js)、情感饼图、打标明细表 |
| 🔴 差评深度 | 根因分析、严重度分层 (Critical/Major/Minor)、改进优先级 |
| 🔑 关键词研究 | 高频词柱状图、Amazon建议词云、长尾关键词 |
| 🎯 VOC聚类 | 客户之声主题卡片、客户期望表、未满足需求 |
| 🏪 竞品分析 | 市场概览、竞品对比表、价格/功能差距分析 |
| 💡 新品机会 | 机会评分雷达、市场缺口卡、利基机会表、风险评估 |
| 📋 行动计划 | 立即行动/短期计划/长期规划，含时间线和预期结果 |

---

## 技术架构

```
main.py (入口)
  ├── parse_input.py      # 智能输入解析 (ASIN/名称/URL识别 + Amazon搜索)
  ├── fetch_multi.py      # 多产品评论爬虫 (主产品+N竞品)
  ├── ai_analysis.py      # AI 分析引擎 (10维打标 + 差评根因 + VOC聚类)
  ├── keyword_research.py # 关键词挖掘 (评论词频 + Amazon Suggest API)
  ├── competitor.py       # 竞品分析 (搜索→对比→差距→定位)
  ├── opportunity.py      # 机会分析 (缺口→利基→风险→行动计划)
  ├── generate_report.py  # HTML报告生成 (Chart.js 交互式)
  └── utils.py            # 共享工具 (文本处理/网络/统计)
```

---

## AI 打标维度（10维）

每条评论 AI 提取以下信息：

1. `sentiment` — 情感 (positive/negative/neutral)
2. `pain_points` — 痛点列表 (最多5个)
3. `selling_points` — 卖点列表 (最多5个)
4. `use_cases` — 使用场景 (最多3个)
5. `user_profile` — 用户画像一句话
6. `improvement_suggestions` — 改进建议
7. `emotion_intensity` — 情感强度 (1-5)
8. `product_expectation` — 期望满足度 (met/exceeded/below)
9. `repurchase_intent` — 复购意愿 (likely/unlikely/unsure)
10. `summary` — 一句话摘要

---

## 注意事项

1. **网络环境**: 中国用户可能需要代理访问 Amazon，建议配合 `HTTPS_PROXY` 环境变量
2. **反爬策略**: 内置了延迟和重试机制，但大量请求仍可能触发验证码
3. **API Key**: AI 分析可选，无 Key 时自动降级为规则统计（仍然可用但深度有限）
4. **数据时效**: 报告基于采集时刻的数据，建议定期更新
5. **合规使用**: 仅用于产品研究和学习，请遵守 Amazon 服务条款

---

## 示例截图

(报告包含 Chart.js 交互式图表、可折叠面板、关键词云、竞品对比表等)

---

*Built with ❤️ by WorkBuddy | 一句话全链路 Amazon 产品研究*
