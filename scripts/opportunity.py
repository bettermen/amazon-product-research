#!/usr/bin/env python3
"""
新品机会分析模块
基于竞品差评、市场缺口、需求趋势识别新品切入机会
"""

import re
import json
import requests
from typing import Dict, List, Optional
from collections import Counter


def analyze_opportunities(
    primary_product: Dict,
    tagged_reviews: List[Dict],
    keyword_data: Dict,
    competitor_data: Dict,
    voc_data: Dict,
    api_key: str = None,
    api_base: str = "https://api.openai.com/v1",
    model: str = "gpt-4o-mini",
    debug: bool = False
) -> Dict:
    """
    新品机会分析

    Args:
        primary_product: 主产品信息
        tagged_reviews: 已打标评论
        keyword_data: 关键词研究结果
        competitor_data: 竞品分析结果
        voc_data: VOC聚类结果
        api_key: LLM API Key（可选，有则用 AI 分析）
        debug: 调试

    Returns:
        {
            "opportunity_scores": {...},
            "market_gaps": [...],
            "niche_opportunities": [...],
            "product_improvement_ideas": [...],
            "risk_assessment": {...},
            "action_plan": {...},
        }
    """
    
    if debug:
        print(f"  💡 分析新品机会...")
    
    result = {}
    
    # 1. 市场缺口识别
    result["market_gaps"] = _identify_market_gaps(
        primary_product, competitor_data, keyword_data, tagged_reviews
    )
    
    # 2. 利基机会
    result["niche_opportunities"] = _identify_niche_opportunities(
        tagged_reviews, keyword_data, voc_data
    )
    
    # 3. 产品改进思路
    result["product_improvement_ideas"] = _generate_improvement_ideas(
        tagged_reviews, voc_data, competitor_data
    )
    
    # 4. 机会评分
    result["opportunity_scores"] = _compute_opportunity_scores(result)
    
    # 5. 风险评估
    result["risk_assessment"] = _assess_risks(primary_product, competitor_data)
    
    # 6. 行动计划
    result["action_plan"] = _generate_action_plan(result)
    
    if debug:
        print(f"  ✅ 机会分析完成: {len(result['market_gaps'])} 个市场缺口, "
              f"{len(result['niche_opportunities'])} 个利基机会")
    
    return result


def _identify_market_gaps(
    primary: Dict, competitor_data: Dict, keyword_data: Dict,
    tagged_reviews: List[Dict]
) -> List[Dict]:
    """识别市场缺口"""
    
    gaps = []
    
    # 从竞品分析中找出价格缺口
    pricing_gaps = competitor_data.get("gap_analysis", {}).get("pricing_gaps", [])
    if pricing_gaps:
        for pg in pricing_gaps[:3]:
            gaps.append({
                "type": "pricing",
                "gap": pg.get("insight", ""),
                "opportunity": "可通过定价策略切入市场",
                "effort": "low",
            })
    
    # 从关键词中找到未被充分覆盖的搜索词
    suggest_keywords = keyword_data.get("amazon_suggest_keywords", [])
    hf_keywords = [w for w, _ in keyword_data.get("high_frequency_keywords", [])]
    
    # 高搜索量但未被高频使用的词 → 市场缺口
    uncovered = set(suggest_keywords[:10]) - set(hf_keywords[:20])
    for kw in list(uncovered)[:3]:
        gaps.append({
            "type": "keyword_gap",
            "gap": f"搜索词 '{kw}' 有搜索量但竞品未充分覆盖",
            "opportunity": f"在 Listing 中突出 '{kw}' 相关卖点",
            "effort": "low",
        })
    
    # 从差评识别功能缺口
    from collections import Counter
    pain_counter = Counter()
    for item in tagged_reviews:
        tags = item.get("tags", {})
        pain_points = tags.get("pain_points", [])
        if isinstance(pain_points, list):
            pain_counter.update(pain_points)
    
    # 高频痛点 → 功能缺口
    for pain, count in pain_counter.most_common(5):
        if count >= 2:
            gaps.append({
                "type": "feature_gap",
                "gap": f"竞品普遍存在 '{pain}' 问题 ({count}次提及)",
                "opportunity": f"解决 '{pain}' 问题可形成差异化优势",
                "effort": "medium",
            })
    
    return gaps[:8]


def _identify_niche_opportunities(
    tagged_reviews: List[Dict], keyword_data: Dict, voc_data: Dict
) -> List[Dict]:
    """识别利基市场机会"""
    
    niches = []
    
    # 从使用场景中识别利基
    use_case_counter = Counter()
    for item in tagged_reviews:
        tags = item.get("tags", {})
        use_cases = tags.get("use_cases", [])
        if isinstance(use_cases, list):
            use_case_counter.update(use_cases)
    
    # 高频使用场景 → 利基机会
    for scene, count in use_case_counter.most_common(5):
        if count >= 2:
            niches.append({
                "niche": f"针对 {scene} 场景的专用产品线",
                "target_audience": f"{scene} 用户群体",
                "market_size_estimate": "medium" if count >= 5 else "small",
                "competition_level": "low" if count >= 5 else "very_low",
                "entry_strategy": f"开发 {scene} 专属功能 + 精准投放广告",
            })
    
    # 从用户画像识别利基
    profile_counter = Counter()
    for item in tagged_reviews:
        tags = item.get("tags", {})
        profile = tags.get("user_profile", "")
        if profile:
            profile_counter[profile] += 1
    
    for profile, count in profile_counter.most_common(3):
        if count >= 2:
            niches.append({
                "niche": f"面向 {profile} 的定制产品",
                "target_audience": profile,
                "market_size_estimate": "medium",
                "competition_level": "low",
                "entry_strategy": f"精准定位 {profile} 需求，定制化产品+内容营销",
            })
    
    # 从长尾关键词识别利基
    long_tail = keyword_data.get("long_tail_keywords", [])
    for kw in long_tail[:5]:
        if len(kw) > 20:  # 长尾词
            niches.append({
                "niche": f"关键词 '{kw}' 的细分市场",
                "target_audience": kw,
                "market_size_estimate": "small",
                "competition_level": "very_low",
                "entry_strategy": f"围绕 '{kw}' 做精准 Listing + PPC",
            })
    
    return niches[:6]


def _generate_improvement_ideas(
    tagged_reviews: List[Dict], voc_data: Dict, competitor_data: Dict
) -> List[Dict]:
    """生成产品改进思路"""
    
    ideas = []
    
    # 从VOC数据提取改进建议
    improvement_counter = Counter()
    for item in tagged_reviews:
        tags = item.get("tags", {})
        suggestions = tags.get("improvement_suggestions", [])
        if isinstance(suggestions, list):
            improvement_counter.update(suggestions)
    
    for suggestion, count in improvement_counter.most_common(8):
        if count >= 1:
            ideas.append({
                "idea": suggestion,
                "source": "customer_feedback",
                "frequency": count,
                "priority": "P0" if count >= 3 else "P1" if count >= 2 else "P2",
                "expected_impact": "high" if count >= 3 else "medium",
            })
    
    # 从VOC聚类中提取
    clusters = voc_data.get("clusters", [])
    for cluster in clusters:
        if cluster.get("sentiment") == "negative":
            ideas.append({
                "idea": cluster.get("action", ""),
                "source": "voc_cluster",
                "frequency": cluster.get("mentions", 0),
                "priority": "P1",
                "expected_impact": "high",
            })
    
    # 去重
    seen = set()
    unique_ideas = []
    for idea in ideas:
        if idea["idea"] not in seen and idea["idea"]:
            seen.add(idea["idea"])
            unique_ideas.append(idea)
    
    return unique_ideas[:10]


def _compute_opportunity_scores(result: Dict) -> Dict:
    """计算机会评分"""
    
    scores = {
        "overall_score": 0,
        "market_attractiveness": 0,
        "competitive_intensity": 0,
        "entry_difficulty": 0,
        "profit_potential": 0,
        "breakdown": {},
    }
    
    # 市场吸引力（基于市场缺口数量）
    gaps = result.get("market_gaps", [])
    niches = result.get("niche_opportunities", [])
    
    scores["market_attractiveness"] = min(10, len(gaps) * 2 + len(niches) * 1.5)
    
    # 竞争强度（基于利基数量，越多越分散）
    scores["competitive_intensity"] = max(1, 10 - len(niches) * 1.5)
    
    # 进入难度（改进建议越多，说明现有产品不完善，容易进入）
    ideas = result.get("product_improvement_ideas", [])
    p0_count = sum(1 for i in ideas if i.get("priority") == "P0")
    scores["entry_difficulty"] = max(1, 10 - (p0_count * 2 + len(ideas) * 0.5))
    
    # 利润潜力
    scores["profit_potential"] = min(10, 5 + len(gaps))
    
    # 综合评分
    scores["overall_score"] = round(
        scores["market_attractiveness"] * 0.3 +
        (10 - scores["competitive_intensity"]) * 0.25 +
        (10 - scores["entry_difficulty"]) * 0.2 +
        scores["profit_potential"] * 0.25,
        1
    )
    
    # 详细解释
    scores["breakdown"] = {
        "market_attractiveness": f"{scores['market_attractiveness']:.0f}/10 - "
                                 f"发现 {len(gaps)} 个市场缺口, {len(niches)} 个利基机会",
        "competitive_intensity": f"{scores['competitive_intensity']:.0f}/10 - "
                                 f"竞争{'较激烈' if scores['competitive_intensity'] > 6 else '适中' if scores['competitive_intensity'] > 3 else '较低'}",
        "entry_difficulty": f"{scores['entry_difficulty']:.0f}/10 - "
                           f"需要解决 {p0_count} 个关键问题",
        "profit_potential": f"{scores['profit_potential']:.0f}/10 - "
                           f"{'高' if scores['profit_potential'] > 7 else '中等' if scores['profit_potential'] > 4 else '待观察'}利润潜力",
    }
    
    return scores


def _assess_risks(primary: Dict, competitor_data: Dict) -> Dict:
    """风险评估"""
    
    competitors = competitor_data.get("competitors", [])
    position = competitor_data.get("competitive_position", {})
    
    risks = []
    
    # 竞争风险
    if len(competitors) >= 5:
        risks.append({
            "risk": "高竞争强度",
            "level": "high",
            "mitigation": "差异化定位 + 精准细分市场切入",
        })
    
    # 价格战风险
    primary_price = 0
    pm = re.search(r'[\d.]+', str(primary.get("price", "0")))
    if pm:
        primary_price = float(pm.group())
    
    low_price_competitors = 0
    for c in competitors:
        cm = re.search(r'[\d.]+', str(c.get("price", "0")))
        if cm:
            cp = float(cm.group())
            if cp < primary_price * 0.8:
                low_price_competitors += 1
    
    if low_price_competitors >= 2:
        risks.append({
            "risk": "价格战威胁",
            "level": "medium",
            "mitigation": "强调品质差异化，避免纯价格竞争；考虑差异化定价策略",
        })
    
    # 评分风险
    primary_rating = primary.get("rating", 0)
    if primary_rating < 3.8:
        risks.append({
            "risk": "产品评分偏低",
            "level": "high",
            "mitigation": "优先解决高频痛点，提升产品质量，鼓励好评",
        })
    
    # 市场规模风险
    total_reviews = primary.get("total_reviews", 0)
    if total_reviews < 50:
        risks.append({
            "risk": "市场规模不确定",
            "level": "medium",
            "mitigation": "小批量测试市场反应，验证需求后再扩大投入",
        })
    
    return {
        "risks": risks,
        "overall_risk_level": "high" if any(r["level"] == "high" for r in risks) 
                              else "medium" if risks else "low",
        "key_concerns": [r["risk"] for r in risks[:3]],
    }


def _generate_action_plan(result: Dict) -> Dict:
    """生成行动计划"""
    
    gaps = result.get("market_gaps", [])
    niches = result.get("niche_opportunities", [])
    ideas = result.get("product_improvement_ideas", [])
    
    plans = {
        "immediate_actions": [],
        "short_term": [],
        "long_term": [],
    }
    
    # 立即行动
    plans["immediate_actions"] = [
        {
            "action": "优化 Listing 标题和关键词",
            "detail": "基于关键词研究结果，更新标题包含高频搜索词",
            "timeline": "1-3天",
            "expected_result": "提升搜索曝光和 CTR",
        },
        {
            "action": "分析并回复差评",
            "detail": "对现有差评逐一回复，展现品牌关怀",
            "timeline": "1-2天",
            "expected_result": "提升品牌形象，可能转为好评",
        },
    ]
    
    # 短期行动
    short_term = []
    for gap in gaps[:3]:
        short_term.append({
            "action": f"解决: {gap.get('gap', '')[:60]}",
            "detail": gap.get("opportunity", ""),
            "timeline": "1-4周",
            "expected_result": "缩小与竞品差距",
        })
    
    for idea in ideas[:3]:
        if idea.get("priority") == "P0":
            short_term.append({
                "action": f"改进: {idea['idea'][:40]}",
                "detail": f"基于 {idea['frequency']} 条用户反馈",
                "timeline": "2-4周",
                "expected_result": "提升用户满意度",
            })
    
    plans["short_term"] = short_term[:5]
    
    # 长期行动
    long_term = []
    for niche in niches[:3]:
        long_term.append({
            "action": f"探索利基: {niche.get('niche', '')[:50]}",
            "detail": niche.get("entry_strategy", ""),
            "timeline": "1-3个月",
            "expected_result": "开辟新增长点",
        })
    
    plans["long_term"] = long_term[:3]
    
    return plans


if __name__ == "__main__":
    import re  # needed for price extraction in risk assessment
    
    test_tagged = [
        {"review": {"rating": 2}, "tags": {"pain_points": ["电池短", "充电慢"], "use_cases": ["健身"], "user_profile": "健身爱好者", "improvement_suggestions": ["加长续航"]}},
        {"review": {"rating": 1}, "tags": {"pain_points": ["电池短", "不舒适"], "use_cases": ["通勤"], "user_profile": "上班族", "improvement_suggestions": ["改进舒适度"]}},
        {"review": {"rating": 5}, "tags": {"pain_points": [], "use_cases": ["旅行"], "user_profile": "旅行者", "improvement_suggestions": []}},
    ]
    
    result = analyze_opportunities(
        primary_product={"asin": "B0XX", "title": "Earbuds", "price": "$29", "rating": 3.5, "total_reviews": 200},
        tagged_reviews=test_tagged,
        keyword_data={"amazon_suggest_keywords": ["bluetooth earbuds", "wireless earphones"], "high_frequency_keywords": [("sound", 10)], "long_tail_keywords": ["best wireless earbuds for running 2024"]},
        competitor_data={"gap_analysis": {"pricing_gaps": [{"insight": "竞品更贵"}]}, "competitors": [{"asin": "B01", "price": "$39", "rating": 4.4}, {"asin": "B02", "price": "$19", "rating": 3.8}], "competitive_position": {"overall_rank": "challenger"}},
        voc_data={"clusters": [{"sentiment": "negative", "mentions": 3, "action": "延长电池续航"}]},
        debug=True,
    )
    
    print(f"\n机会评分: {result['opportunity_scores']['overall_score']}/10")
    print(f"市场缺口: {len(result['market_gaps'])} 个")
    print(f"利基机会: {len(result['niche_opportunities'])} 个")
    print(f"改进建议: {len(result['product_improvement_ideas'])} 个")
