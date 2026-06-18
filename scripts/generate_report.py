#!/usr/bin/env python3
"""
一站式 Amazon 产品研究 HTML 报告生成器
整合：产品概览、评论分析、关键词研究、VOC聚类、竞品分析、新品机会
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from utils import format_number, format_price, clean_text


def generate_full_report(
    product_data: Dict,
    tagged_reviews: List[Dict],
    keyword_data: Dict,
    voc_data: Dict,
    competitor_data: Dict,
    opportunity_data: Dict,
    negative_analysis: Dict = None,
    output_path: str = "amazon_product_research.html",
) -> str:
    """
    生成全链路 HTML 报告
    """
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 计算统计数据
    total_reviews = len(tagged_reviews)
    primary_product = product_data.get("primary_product", {})
    products = product_data.get("products", {})
    primary_asin = product_data.get("primary_asin", "")
    search_query = product_data.get("search_query", "")
    
    # 评分分布
    rating_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    positive = negative = neutral = 0
    for item in tagged_reviews:
        r = item["review"]
        rating = int(r.get("rating", 0))
        if rating in rating_dist:
            rating_dist[rating] += 1
        s = item["tags"].get("sentiment", "neutral")
        if s == "positive":
            positive += 1
        elif s == "negative":
            negative += 1
        else:
            neutral += 1
    
    total = max(sum(rating_dist.values()), 1)
    avg_rating = sum(k * v for k, v in rating_dist.items()) / total
    
    # 构建 HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Amazon 产品深度研究报告 - {_safe(primary_product.get('title', 'Product Analysis'))}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #333; line-height: 1.6; }}
.container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}

/* Header */
.header {{ background: linear-gradient(135deg, #232f3e 0%, #37475a 100%); color: white; padding: 40px 30px; border-radius: 16px; margin-bottom: 24px; }}
.header h1 {{ font-size: 28px; margin-bottom: 8px; }}
.header .subtitle {{ opacity: 0.85; font-size: 14px; }}
.header .product-info {{ display: flex; align-items: center; gap: 20px; margin-top: 20px; }}
.header .product-info img {{ width: 120px; height: 120px; object-fit: contain; background: white; border-radius: 8px; padding: 8px; }}
.header .product-info .meta {{ font-size: 14px; }}
.header .product-info .meta span {{ display: inline-block; margin-right: 16px; opacity: 0.9; }}
.header .product-info .meta .price {{ font-size: 24px; font-weight: 700; opacity: 1; }}

/* Nav */
.nav {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 24px; position: sticky; top: 0; background: #f5f7fa; padding: 12px 0; z-index: 100; }}
.nav a {{ padding: 8px 16px; background: white; border-radius: 20px; text-decoration: none; color: #555; font-size: 13px; font-weight: 500; border: 1px solid #e0e0e0; transition: all 0.2s; }}
.nav a:hover {{ background: #232f3e; color: white; border-color: #232f3e; }}

/* Section */
.section {{ background: white; border-radius: 12px; padding: 28px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
.section h2 {{ font-size: 20px; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 2px solid #ff9900; color: #232f3e; display: flex; align-items: center; gap: 8px; }}
.section h3 {{ font-size: 16px; margin: 16px 0 8px; color: #444; }}

/* Stats Grid */
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 20px; }}
.stat-card {{ background: #f8f9fb; border-radius: 10px; padding: 20px; text-align: center; border: 1px solid #eee; }}
.stat-card .value {{ font-size: 28px; font-weight: 700; color: #232f3e; }}
.stat-card .label {{ font-size: 12px; color: #888; margin-top: 4px; text-transform: uppercase; }}
.stat-card.orange {{ border-color: #ff9900; }}
.stat-card.green {{ border-color: #4caf50; }}
.stat-card.red {{ border-color: #f44336; }}

/* Charts */
.chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }}
.chart-container {{ position: relative; height: 300px; }}
@media (max-width: 768px) {{ .chart-row {{ grid-template-columns: 1fr; }} }}

/* Tables */
table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 14px; }}
th {{ background: #f0f2f5; padding: 10px 12px; text-align: left; font-weight: 600; color: #555; border-bottom: 2px solid #ddd; }}
td {{ padding: 10px 12px; border-bottom: 1px solid #eee; }}
tr:hover {{ background: #fafbfc; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
.badge-p0 {{ background: #ffebee; color: #c62828; }}
.badge-p1 {{ background: #fff3e0; color: #e65100; }}
.badge-p2 {{ background: #e8f5e9; color: #2e7d32; }}
.badge-positive {{ background: #e8f5e9; color: #2e7d32; }}
.badge-negative {{ background: #ffebee; color: #c62828; }}
.badge-neutral {{ background: #f5f5f5; color: #757575; }}

/* Cards */
.card-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
.card {{ background: #f8f9fb; border-radius: 10px; padding: 16px; border: 1px solid #eee; }}
.card h4 {{ font-size: 14px; color: #232f3e; margin-bottom: 8px; }}
.card p {{ font-size: 13px; color: #666; line-height: 1.5; }}

/* Keywords */
.keyword-cloud {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }}
.keyword-tag {{ padding: 5px 12px; border-radius: 16px; font-size: 12px; background: #e3f2fd; color: #1565c0; font-weight: 500; }}
.keyword-tag.pain {{ background: #ffebee; color: #c62828; }}
.keyword-tag.sell {{ background: #e8f5e9; color: #2e7d32; }}

/* Competitor */
.comp-card {{ display: flex; align-items: center; gap: 16px; padding: 16px; background: #f8f9fb; border-radius: 10px; margin-bottom: 12px; border: 1px solid #eee; }}
.comp-card img {{ width: 64px; height: 64px; object-fit: contain; background: white; border-radius: 6px; }}
.comp-card .comp-info {{ flex: 1; }}
.comp-card .comp-info .comp-title {{ font-weight: 600; margin-bottom: 4px; }}
.comp-card .comp-info .comp-meta {{ font-size: 13px; color: #666; }}
.comp-card .comp-rank {{ font-size: 24px; font-weight: 700; color: #ff9900; min-width: 40px; text-align: center; }}

/* Priorities */
.priority-list {{ list-style: none; }}
.priority-list li {{ padding: 10px 12px; margin: 6px 0; background: #f8f9fb; border-radius: 8px; border-left: 4px solid #ddd; font-size: 14px; }}
.priority-list li.p0 {{ border-left-color: #f44336; }}
.priority-list li.p1 {{ border-left-color: #ff9800; }}
.priority-list li.p2 {{ border-left-color: #4caf50; }}

/* Footer */
.footer {{ text-align: center; padding: 30px; color: #999; font-size: 12px; }}

/* Collapsible */
.collapsible {{ cursor: pointer; user-select: none; }}
.collapsible::after {{ content: ' ▼'; font-size: 12px; color: #999; }}
.collapsed::after {{ content: ' ▶'; }}
.collapse-content {{ display: block; }}
.collapse-content.hidden {{ display: none; }}
</style>
</head>
<body>

<div class="container">

<!-- Header -->
<div class="header">
    <h1>🛍️ Amazon 产品深度研究报告</h1>
    <div class="subtitle">一句话输入 · 全链路分析 · 生成时间: {now}</div>
    <div class="product-info">
        <img src="{_safe(primary_product.get('image_url', ''))}" alt="Product" onerror="this.style.display='none'">
        <div class="meta">
            <div style="font-size:18px;font-weight:600;margin-bottom:8px;">{_safe(primary_product.get('title', search_query))}</div>
            <span>ASIN: {primary_asin}</span>
            <span class="price">{_safe(primary_product.get('price', 'N/A'))}</span>
            <span>⭐ {primary_product.get('rating', '-')}</span>
            <span>📝 {format_number(primary_product.get('total_reviews', 0))} reviews</span>
            <br>
            <span>市场: {product_data.get('market', 'US')}</span>
            <span>搜索词: "{search_query}"</span>
        </div>
    </div>
</div>

<!-- Nav -->
<div class="nav">
    <a href="#overview">📊 总览</a>
    <a href="#reviews">💬 评论分析</a>
    <a href="#negative">🔴 差评深度</a>
    <a href="#keywords">🔑 关键词研究</a>
    <a href="#voc">🎯 VOC聚类</a>
    <a href="#competitors">🏪 竞品分析</a>
    <a href="#opportunity">💡 新品机会</a>
    <a href="#action">📋 行动计划</a>
</div>

<!-- Section 1: Overview -->
<div class="section" id="overview">
    <h2>📊 分析总览</h2>
    <div class="stats-grid">
        <div class="stat-card orange">
            <div class="value">{avg_rating:.1f} ⭐</div>
            <div class="label">综合评分</div>
        </div>
        <div class="stat-card">
            <div class="value">{format_number(total_reviews)}</div>
            <div class="label">分析评论数</div>
        </div>
        <div class="stat-card green">
            <div class="value">{positive * 100 // max(total, 1)}%</div>
            <div class="label">正面评论</div>
        </div>
        <div class="stat-card red">
            <div class="value">{negative * 100 // max(total, 1)}%</div>
            <div class="label">负面评论</div>
        </div>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card">
            <div class="value">{format_number(len(keyword_data.get('high_frequency_keywords', [])))}</div>
            <div class="label">关键词提取</div>
        </div>
        <div class="stat-card">
            <div class="value">{format_number(len(competitor_data.get('competitors', [])))}</div>
            <div class="label">竞品分析</div>
        </div>
        <div class="stat-card orange">
            <div class="value">{opportunity_data.get('opportunity_scores', {}).get('overall_score', '-')}/10</div>
            <div class="label">机会评分</div>
        </div>
        <div class="stat-card">
            <div class="value">{len(opportunity_data.get('niche_opportunities', []))}</div>
            <div class="label">利基机会</div>
        </div>
    </div>
</div>

<!-- Section 2: Reviews -->
<div class="section" id="reviews">
    <h2>💬 评论分析</h2>
    <div class="chart-row">
        <div>
            <h3>评分分布</h3>
            <div class="chart-container">
                <canvas id="ratingChart"></canvas>
            </div>
        </div>
        <div>
            <h3>情感分布</h3>
            <div class="chart-container">
                <canvas id="sentimentChart"></canvas>
            </div>
        </div>
    </div>
    {_render_tagged_reviews_table(tagged_reviews[:20])}
</div>

<!-- Section 3: Negative Review Deep Dive -->
<div class="section" id="negative">
    <h2>🔴 差评深度分析</h2>
    {_render_negative_analysis(negative_analysis, tagged_reviews)}
</div>

<!-- Section 4: Keywords -->
<div class="section" id="keywords">
    <h2>🔑 关键词研究与扩展</h2>
    <div class="chart-row">
        <div>
            <h3>高频关键词 TOP20</h3>
            <div class="chart-container">
                <canvas id="keywordChart"></canvas>
            </div>
        </div>
        <div>
            <h3>Amazon 搜索建议</h3>
            <div class="keyword-cloud">
                {_render_keyword_cloud(keyword_data.get('amazon_suggest_keywords', []))}
            </div>
            <h3 style="margin-top:20px;">长尾关键词机会</h3>
            <div class="keyword-cloud">
                {_render_keyword_cloud(keyword_data.get('long_tail_keywords', []), 'keyword-tag')}
            </div>
        </div>
    </div>
    {_render_recommended_keywords(keyword_data.get('recommended_keywords', {}))}
</div>

<!-- Section 5: VOC -->
<div class="section" id="voc">
    <h2>🎯 VOC 客户之声聚类</h2>
    {_render_voc_clusters(voc_data)}
</div>

<!-- Section 6: Competitors -->
<div class="section" id="competitors">
    <h2>🏪 竞品分析</h2>
    {_render_market_overview(competitor_data.get('market_overview', {}))}
    {_render_competitors_table(competitor_data.get('competitors', []), competitor_data.get('competitive_position', {}))}
    {_render_gap_analysis(competitor_data.get('gap_analysis', {}))}
</div>

<!-- Section 7: Opportunity -->
<div class="section" id="opportunity">
    <h2>💡 新品机会分析</h2>
    {_render_opportunity_scores(opportunity_data.get('opportunity_scores', {}))}
    {_render_market_gaps(opportunity_data.get('market_gaps', []))}
    {_render_niche_opportunities(opportunity_data.get('niche_opportunities', []))}
    {_render_risk_assessment(opportunity_data.get('risk_assessment', {}))}
</div>

<!-- Section 8: Action Plan -->
<div class="section" id="action">
    <h2>📋 行动计划</h2>
    {_render_action_plan(opportunity_data.get('action_plan', {}))}
</div>

<div class="footer">
    <p>Generated by Amazon Product Research Skill · WorkBuddy AI</p>
    <p>报告基于真实评论数据和 AI 分析生成，仅供参考</p>
</div>

</div>

<script>
// Rating Distribution Chart
new Chart(document.getElementById('ratingChart'), {{
    type: 'bar',
    data: {{
        labels: ['1★', '2★', '3★', '4★', '5★'],
        datasets: [{{
            label: '评论数',
            data: [{rating_dist[1]}, {rating_dist[2]}, {rating_dist[3]}, {rating_dist[4]}, {rating_dist[5]}],
            backgroundColor: ['#ef5350', '#ff7043', '#ffca28', '#66bb6a', '#43a047'],
            borderRadius: 6,
        }}]
    }},
    options: {{ responsive: true, maintainAspectRatio: false,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{ y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }} }}
    }}
}});

// Sentiment Distribution Chart
new Chart(document.getElementById('sentimentChart'), {{
    type: 'doughnut',
    data: {{
        labels: ['正面', '负面', '中性'],
        datasets: [{{
            data: [{positive}, {negative}, {neutral}],
            backgroundColor: ['#43a047', '#ef5350', '#90a4ae'],
            borderWidth: 0,
        }}]
    }},
    options: {{ responsive: true, maintainAspectRatio: false,
        plugins: {{ legend: {{ position: 'bottom' }} }}
    }}
}});

// Keywords Chart
new Chart(document.getElementById('keywordChart'), {{
    type: 'bar',
    data: {{
        labels: {json.dumps([w for w, _ in keyword_data.get('high_frequency_keywords', [])[:15]])},
        datasets: [{{
            label: '出现频率',
            data: {json.dumps([c for _, c in keyword_data.get('high_frequency_keywords', [])[:15]])},
            backgroundColor: '#42a5f5',
            borderRadius: 4,
        }}]
    }},
    options: {{ 
        indexAxis: 'y',
        responsive: true, maintainAspectRatio: false,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{ x: {{ beginAtZero: true }} }}
    }}
}});

// Collapsible sections
document.querySelectorAll('.collapsible').forEach(el => {{
    el.addEventListener('click', () => {{
        el.classList.toggle('collapsed');
        const content = el.nextElementSibling;
        if (content) content.classList.toggle('hidden');
    }});
}});
</script>

</body>
</html>"""
    
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return output_path


def _safe(text):
    """安全处理文本"""
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _render_tagged_reviews_table(tagged_reviews: List[Dict]) -> str:
    """渲染评论表格"""
    if not tagged_reviews:
        return "<p>暂无评论数据</p>"
    
    rows = ""
    for item in tagged_reviews[:20]:
        r = item["review"]
        t = item["tags"]
        sentiment = t.get("sentiment", "neutral")
        badge_class = f"badge-{sentiment}"
        
        rows += f"""<tr>
            <td>{r.get('rating', '-')}★</td>
            <td><span class="badge {badge_class}">{sentiment}</span></td>
            <td>{_safe(r.get('title', ''))[:50]}</td>
            <td>{_safe(t.get('summary', ''))}</td>
            <td>{_safe(', '.join(t.get('pain_points', [])[:3]))}</td>
            <td>{_safe(', '.join(t.get('selling_points', [])[:3]))}</td>
        </tr>"""
    
    return f"""<div class="collapsible"><h3>评论打标明细 (前20条)</h3></div>
    <div class="collapse-content">
    <table>
        <tr><th>评分</th><th>情感</th><th>标题</th><th>摘要</th><th>痛点</th><th>卖点</th></tr>
        {rows}
    </table>
    </div>"""


def _render_negative_analysis(negative_analysis: Dict, tagged_reviews: List[Dict]) -> str:
    """渲染差评分析"""
    if not negative_analysis:
        # 简单统计
        negative_count = sum(1 for item in tagged_reviews if item["tags"].get("sentiment") == "negative")
        return f"""<div class="stats-grid">
            <div class="stat-card red"><div class="value">{negative_count}</div><div class="label">差评总数</div></div>
        </div>
        <p>差评深度分析需要 API Key 支持，当前仅显示基础统计</p>"""
    
    root_causes = negative_analysis.get("root_causes", [])
    rows = ""
    for rc in root_causes:
        severity = rc.get("severity", "minor")
        severity_color = "red" if severity == "critical" else "orange" if severity == "major" else "green"
        rows += f"""<tr>
            <td style="color:{severity_color};font-weight:600;">{severity.upper()}</td>
            <td>{_safe(rc.get('cause', ''))}</td>
            <td>{rc.get('frequency', 0)}</td>
            <td>{_safe(', '.join(rc.get('examples', [])[:2]))}</td>
        </tr>"""
    
    improvement_rows = ""
    for ip in negative_analysis.get("improvement_priority", [])[:5]:
        improvement_rows += f"""<tr>
            <td>{_safe(ip.get('issue', ''))}</td>
            <td>{_safe(ip.get('impact', ''))}</td>
            <td>{_safe(ip.get('solution', ''))}</td>
            <td><span class="badge badge-{'p0' if ip.get('effort') == 'low' else 'p1' if ip.get('effort') == 'medium' else 'p2'}">{ip.get('effort', '-')}</span></td>
        </tr>"""
    
    severity = negative_analysis.get("severity_breakdown", {})
    trend = negative_analysis.get("sentiment_trend", "stable")
    
    return f"""<div class="stats-grid">
        <div class="stat-card red"><div class="value">{severity.get('critical', 0)}</div><div class="label">严重问题</div></div>
        <div class="stat-card orange"><div class="value">{severity.get('major', 0)}</div><div class="label">主要问题</div></div>
        <div class="stat-card"><div class="value">{severity.get('minor', 0)}</div><div class="label">次要问题</div></div>
        <div class="stat-card"><div class="value">{trend}</div><div class="label">情感趋势</div></div>
    </div>
    
    <h3>🔍 根因分析</h3>
    <table>
        <tr><th>严重度</th><th>根因</th><th>频率</th><th>典型评论</th></tr>
        {rows}
    </table>
    
    <h3>📋 改进优先级</h3>
    <table>
        <tr><th>问题</th><th>影响</th><th>解决方案</th><th>难度</th></tr>
        {improvement_rows}
    </table>"""


def _render_keyword_cloud(keywords: List[str], css_class: str = "keyword-tag") -> str:
    """渲染关键词云"""
    if not keywords:
        return "<p>暂无关键词数据</p>"
    return "\n".join(f'<span class="{css_class}">{_safe(kw)}</span>' for kw in keywords[:25])


def _render_recommended_keywords(recommended: Dict) -> str:
    """渲染推荐关键词"""
    html = ""
    for category, kws in recommended.items():
        if not kws:
            continue
        items = "".join(
            f'<tr><td>{_safe(kw.get("keyword", kw.get("word", str(kw))))}</td><td>{kw.get("frequency", kw.get("type", "-"))}</td></tr>'
            for kw in kws[:10]
        )
        html += f"""<h3>{category}</h3>
        <table><tr><th>关键词</th><th>来源/频率</th></tr>{items}</table>"""
    
    return html or "<p>暂无推荐关键词</p>"


def _render_voc_clusters(voc_data: Dict) -> str:
    """渲染 VOC 聚类"""
    clusters = voc_data.get("clusters", [])
    if not clusters:
        return "<p>VOC 聚类需要 API Key 支持</p>"
    
    html = '<div class="card-grid">'
    for c in clusters:
        sentiment = c.get("sentiment", "neutral")
        emoji = "😊" if sentiment == "positive" else "😟" if sentiment == "negative" else "😐"
        html += f"""<div class="card">
            <h4>{emoji} {_safe(c.get('theme', 'Unknown'))}</h4>
            <p><strong>提及次数:</strong> {c.get('mentions', 0)}</p>
            <p><strong>洞察:</strong> {_safe(c.get('insight', ''))}</p>
            <p><strong>建议行动:</strong> {_safe(c.get('action', ''))}</p>
            <p style="font-size:11px;color:#999;">{_safe(', '.join(c.get('key_quotes', [])[:3]))}</p>
        </div>"""
    html += '</div>'
    
    # Customer expectations
    expectations = voc_data.get("customer_expectations", [])
    if expectations:
        html += '<h3>客户期望</h3><table><tr><th>期望</th><th>重要性</th><th>满足程度</th></tr>'
        for e in expectations:
            html += f'<tr><td>{_safe(e.get("expectation", ""))}</td><td>{e.get("importance", "-")}</td><td>{e.get("gap", "-")}</td></tr>'
        html += '</table>'
    
    # Unmet needs
    unmet = voc_data.get("unmet_needs", [])
    if unmet:
        html += '<h3>未满足的需求</h3><ul>'
        for n in unmet:
            html += f'<li>{_safe(n)}</li>'
        html += '</ul>'
    
    return html


def _render_market_overview(overview: Dict) -> str:
    """渲染市场概览"""
    if not overview:
        return ""
    
    return f"""<div class="stats-grid">
        <div class="stat-card"><div class="value">{_safe(overview.get('avg_price', 'N/A'))}</div><div class="label">市场均价</div></div>
        <div class="stat-card"><div class="value">{overview.get('avg_rating', '-')} ⭐</div><div class="label">市场均分</div></div>
        <div class="stat-card"><div class="value">{_safe(overview.get('price_range', 'N/A'))}</div><div class="label">价格区间</div></div>
        <div class="stat-card"><div class="value">{overview.get('competitor_count', 0)}</div><div class="label">竞品数量</div></div>
    </div>"""


def _render_competitors_table(competitors: List[Dict], position: Dict) -> str:
    """渲染竞品对比表"""
    if not competitors:
        return "<p>暂无竞品数据</p>"
    
    position_html = ""
    if position:
        overall = position.get("overall_rank", "")
        rank_labels = {
            "leader": "🥇 市场领导者",
            "challenger": "🥈 挑战者",
            "niche": "🎯 利基玩家",
            "new_entrant": "🆕 新进入者",
        }
        label = rank_labels.get(overall, overall)
        position_html = f"""<div class="card" style="margin-bottom:16px;background:#fff8e1;border-color:#ff9900;">
            <h4>竞争定位: {label}</h4>
            <p>价格: {position.get('price_position', '-')} | 评分: {position.get('rating_position', '-')} | 评论: {position.get('review_count_position', '-')}</p>
        </div>"""
    
    rows = ""
    for i, c in enumerate(competitors):
        rows += f"""<tr>
            <td>{i+1}</td>
            <td><a href="{_safe(c.get('url', '#'))}" target="_blank">{_safe(c.get('title', c.get('asin', 'Unknown')))[:60]}</a></td>
            <td>{_safe(c.get('price', 'N/A'))}</td>
            <td>{c.get('rating', '-')} ⭐</td>
            <td>{format_number(c.get('total_reviews', 0))}</td>
        </tr>"""
    
    return f"""{position_html}
    <table>
        <tr><th>#</th><th>产品</th><th>价格</th><th>评分</th><th>评论数</th></tr>
        {rows}
    </table>"""


def _render_gap_analysis(gap: Dict) -> str:
    """渲染差距分析"""
    if not gap:
        return ""
    
    html = '<h3>差距分析</h3>'
    
    pricing = gap.get("pricing_gaps", [])
    if pricing:
        html += '<h4>价格差距</h4><table><tr><th>竞品</th><th>差价</th><th>洞察</th></tr>'
        for p in pricing[:5]:
            html += f'<tr><td>{_safe(p.get("competitor", ""))[:40]}</td><td>{_safe(p.get("price_diff", ""))}</td><td>{_safe(p.get("insight", ""))}</td></tr>'
        html += '</table>'
    
    feature = gap.get("feature_gaps", [])
    if feature:
        html += '<h4>功能差距</h4><table><tr><th>竞品</th><th>差距</th><th>建议</th></tr>'
        for f in feature[:5]:
            html += f'<tr><td>{_safe(f.get("competitor", ""))[:40]}</td><td>{_safe(f.get("gap", ""))}</td><td>{_safe(f.get("action", ""))}</td></tr>'
        html += '</table>'
    
    return html


def _render_opportunity_scores(scores: Dict) -> str:
    """渲染机会评分"""
    if not scores:
        return ""
    
    breakdown = ""
    for k, v in scores.get("breakdown", {}).items():
        breakdown += f'<div class="stat-card"><div class="label">{k.replace("_", " ").title()}</div><div style="font-size:12px;color:#666;">{_safe(v)}</div></div>'
    
    return f"""<div class="stats-grid">
        <div class="stat-card orange"><div class="value">{scores.get('overall_score', '-')}/10</div><div class="label">综合机会评分</div></div>
    </div>
    <div class="stats-grid">{breakdown}</div>"""


def _render_market_gaps(gaps: List[Dict]) -> str:
    """渲染市场缺口"""
    if not gaps:
        return ""
    
    html = '<h3>市场缺口识别</h3><div class="card-grid">'
    for g in gaps[:6]:
        effort_color = {"low": "green", "medium": "orange", "high": "red"}.get(g.get("effort", ""), "gray")
        html += f"""<div class="card" style="border-left: 4px solid {effort_color};">
            <h4>{_safe(g.get('gap', ''))[:80]}</h4>
            <p>{_safe(g.get('opportunity', ''))}</p>
            <span class="badge badge-p2">难度: {g.get('effort', '-')}</span>
        </div>"""
    html += '</div>'
    return html


def _render_niche_opportunities(niches: List[Dict]) -> str:
    """渲染利基机会"""
    if not niches:
        return ""
    
    html = '<h3>利基市场机会</h3><table><tr><th>利基方向</th><th>目标用户</th><th>市场规模</th><th>竞争程度</th><th>切入策略</th></tr>'
    for n in niches[:5]:
        html += f"""<tr>
            <td>{_safe(n.get('niche', ''))[:50]}</td>
            <td>{_safe(n.get('target_audience', ''))}</td>
            <td>{_safe(n.get('market_size_estimate', '-'))}</td>
            <td>{_safe(n.get('competition_level', '-'))}</td>
            <td>{_safe(n.get('entry_strategy', ''))[:60]}</td>
        </tr>"""
    html += '</table>'
    return html


def _render_risk_assessment(risks: Dict) -> str:
    """渲染风险评估"""
    if not risks:
        return ""
    
    risk_list = risks.get("risks", [])
    if not risk_list:
        return ""
    
    level_colors = {"high": "#f44336", "medium": "#ff9800", "low": "#4caf50"}
    overall_level = risks.get("overall_risk_level", "medium")
    
    html = f"""<h3>⚠️ 风险评估 <span class="badge badge-{'p0' if overall_level == 'high' else 'p1' if overall_level == 'medium' else 'p2'}">{overall_level.upper()}</span></h3>
    <table><tr><th>风险</th><th>等级</th><th>应对策略</th></tr>"""
    
    for r in risk_list:
        level = r.get("level", "low")
        html += f"""<tr>
            <td>{_safe(r.get('risk', ''))}</td>
            <td><span style="color:{level_colors.get(level, '#999')};font-weight:600;">{level.upper()}</span></td>
            <td>{_safe(r.get('mitigation', ''))}</td>
        </tr>"""
    
    html += '</table>'
    return html


def _render_action_plan(plan: Dict) -> str:
    """渲染行动计划"""
    if not plan:
        return "<p>暂无行动计划</p>"
    
    html = ""
    
    immediate = plan.get("immediate_actions", [])
    if immediate:
        html += '<h3>⚡ 立即行动</h3><ul class="priority-list">'
        for a in immediate:
            html += f"""<li class="p0">
                <strong>{_safe(a.get('action', ''))}</strong><br>
                <span style="font-size:12px;color:#888;">{_safe(a.get('detail', ''))} | 时间: {_safe(a.get('timeline', ''))} | 预期: {_safe(a.get('expected_result', ''))}</span>
            </li>"""
        html += '</ul>'
    
    short_term = plan.get("short_term", [])
    if short_term:
        html += '<h3>📅 短期计划 (1-4周)</h3><ul class="priority-list">'
        for a in short_term:
            html += f"""<li class="p1">
                <strong>{_safe(a.get('action', ''))}</strong><br>
                <span style="font-size:12px;color:#888;">{_safe(a.get('detail', ''))} | 时间: {_safe(a.get('timeline', ''))} | 预期: {_safe(a.get('expected_result', ''))}</span>
            </li>"""
        html += '</ul>'
    
    long_term = plan.get("long_term", [])
    if long_term:
        html += '<h3>🔭 长期规划 (1-3月)</h3><ul class="priority-list">'
        for a in long_term:
            html += f"""<li class="p2">
                <strong>{_safe(a.get('action', ''))}</strong><br>
                <span style="font-size:12px;color:#888;">{_safe(a.get('detail', ''))} | 时间: {_safe(a.get('timeline', ''))} | 预期: {_safe(a.get('expected_result', ''))}</span>
            </li>"""
        html += '</ul>'
    
    return html


if __name__ == "__main__":
    print("报告生成器已加载")
