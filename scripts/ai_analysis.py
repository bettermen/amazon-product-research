#!/usr/bin/env python3
"""
增强版 AI 评论分析模块
支持批量打标、差评深度分析、VOC 聚类
"""

import re
import json
import time
import requests
from typing import Dict, List, Optional
from collections import Counter


def ai_tag_reviews(
    reviews: List[Dict],
    api_key: str,
    api_base: str = "https://api.openai.com/v1",
    model: str = "gpt-4o-mini",
    delay: float = 0.5,
    debug: bool = False
) -> List[Dict]:
    """
    AI 批量打标评论

    Args:
        reviews: 评论列表
        api_key: LLM API Key
        api_base: API Base URL
        model: 模型名称
        delay: API 调用间隔
        debug: 调试模式

    Returns:
        [{"review": {...}, "tags": {...}}, ...]
    """
    
    print(f"🤖 开始 AI 深度打标 ({len(reviews)} 条评论)...")
    print(f"   模型: {model}")
    
    tagged = []
    total = len(reviews)
    
    for i, review in enumerate(reviews, 1):
        try:
            prompt = _build_enhanced_tagging_prompt(review)
            response = _call_chat_api(prompt, api_key, api_base, model)
            tags = _parse_tags_response(response)
            
            tagged.append({
                "review": {k: v for k, v in review.items() if not k.startswith("_")},
                "tags": tags,
            })
        except Exception as e:
            if debug:
                print(f"  ⚠️ AI 打标失败 [{i}]: {e}")
            # 使用默认打标
            tagged.append({
                "review": {k: v for k, v in review.items() if not k.startswith("_")},
                "tags": _default_tags(review),
            })
        
        if i % 20 == 0 or i == total:
            pct = i * 100 // total
            print(f"  进度: {i}/{total} ({pct}%)")
        
        if i < total:
            time.sleep(delay)
    
    print(f"✅ AI 打标完成: {total} 条评论")
    return tagged


def analyze_negative_reviews(
    tagged_reviews: List[Dict],
    api_key: str,
    api_base: str = "https://api.openai.com/v1",
    model: str = "gpt-4o-mini",
    debug: bool = False
) -> Dict:
    """
    差评深度分析（基于所有已打标的差评，用 LLM 做聚合分析）

    Returns:
        {
            "total_negative": int,
            "root_causes": [{"cause": "...", "frequency": N, "severity": "high", "examples": [...]}],
            "severity_breakdown": {"critical": N, "major": N, "minor": N},
            "improvement_priority": [{"issue": "...", "impact": "...", "solution": "..."}],
            "sentiment_trend": "worsening/stable/improving",
        }
    """
    
    negative_reviews = [
        item for item in tagged_reviews
        if item["tags"].get("sentiment") == "negative"
        and item["tags"].get("pain_points")
    ]
    
    if not negative_reviews:
        return {
            "total_negative": 0,
            "root_causes": [],
            "severity_breakdown": {"critical": 0, "major": 0, "minor": 0},
            "improvement_priority": [],
            "sentiment_trend": "insufficient_data",
        }
    
    if debug:
        print(f"  📊 深度分析 {len(negative_reviews)} 条差评...")
    
    # 收集所有差评的痛点和摘要
    all_pain_points = []
    for item in negative_reviews:
        tags = item["tags"]
        points = tags.get("pain_points", [])
        if isinstance(points, list):
            all_pain_points.extend(points)
    
    # 统计
    from collections import Counter
    pain_counter = Counter(all_pain_points)
    
    # 构建差评摘要给 LLM 做深度分析
    negative_summaries = []
    for item in negative_reviews[:50]:  # 取前50条
        r = item["review"]
        t = item["tags"]
        summary = f"评分{r.get('rating','?')}★: {', '.join(t.get('pain_points', []))} | {t.get('summary', '')}"
        negative_summaries.append(summary)
    
    # 用 LLM 做聚合分析
    try:
        analysis = _call_llm_negative_analysis(negative_summaries, pain_counter.most_common(15), 
                                                api_key, api_base, model, debug)
        return analysis
    except Exception as e:
        if debug:
            print(f"  ⚠️ LLM 差评分析失败: {e}")
        # 回退到简单统计
        return _simple_negative_analysis(pain_counter)


def cluster_voc(
    tagged_reviews: List[Dict],
    api_key: str,
    api_base: str = "https://api.openai.com/v1",
    model: str = "gpt-4o-mini",
    debug: bool = False
) -> Dict:
    """
    VOC（客户之声）聚类分析

    将所有评论中的用户反馈按主题聚类，识别核心需求、期望、痛点

    Returns:
        {
            "clusters": [
                {
                    "theme": "主题名",
                    "sentiment": "positive/mixed/negative",
                    "mentions": N,
                    "key_quotes": [...],
                    "insight": "洞察",
                    "action": "建议行动",
                }
            ],
            "customer_expectations": [...],
            "unmet_needs": [...],
            "delighters": [...],  # 超出预期的点
        }
    """
    
    if debug:
        print(f"  🔬 进行 VOC 聚类分析...")
    
    # 收集所有结构化反馈
    all_items = []
    for item in tagged_reviews[:100]:  # 取前100条控制成本
        t = item["tags"]
        all_items.append({
            "rating": item["review"].get("rating", 0),
            "sentiment": t.get("sentiment", "neutral"),
            "pain_points": t.get("pain_points", []),
            "selling_points": t.get("selling_points", []),
            "use_cases": t.get("use_cases", []),
            "summary": t.get("summary", ""),
            "improvement": t.get("improvement_suggestions", []),
        })
    
    # 统计提及频率
    pain_counter = Counter()
    sell_counter = Counter()
    use_case_counter = Counter()
    improvement_counter = Counter()
    
    for item in all_items:
        pain_counter.update(item["pain_points"] if isinstance(item["pain_points"], list) else [])
        sell_counter.update(item["selling_points"] if isinstance(item["selling_points"], list) else [])
        use_case_counter.update(item["use_cases"] if isinstance(item["use_cases"], list) else [])
        improvement_counter.update(item["improvement"] if isinstance(item["improvement"], list) else [])
    
    # 用 LLM 聚类
    try:
        clusters = _call_llm_voc_clustering(
            pain_counter.most_common(20),
            sell_counter.most_common(15),
            use_case_counter.most_common(10),
            improvement_counter.most_common(10),
            api_key, api_base, model, debug
        )
        return clusters
    except Exception as e:
        if debug:
            print(f"  ⚠️ LLM VOC 聚类失败: {e}")
        return _simple_voc_clustering(pain_counter, sell_counter, use_case_counter, improvement_counter)


# ========== Prompt 构建 ==========

def _build_enhanced_tagging_prompt(review: Dict) -> str:
    """构建增强打标 Prompt（比原版提取更多维度）"""
    
    rating = review.get("rating", 0)
    title = review.get("title", "")
    body = review.get("body", "")
    
    if len(body) > 1200:
        body = body[:1200] + "..."
    
    return f"""Analyze this Amazon product review and extract structured insights.

Review:
- Rating: {rating}/5 stars
- Title: {title}
- Body: {body}

Extract these fields as JSON:
1. "sentiment": "positive"/"negative"/"neutral"
2. "pain_points": array of specific problems mentioned (max 5)
3. "selling_points": array of things the user liked (max 5)
4. "use_cases": array of usage scenarios (max 3)
5. "user_profile": one sentence describing who this buyer is
6. "improvement_suggestions": array of what could be better (max 3)
7. "emotion_intensity": 1-5 scale (1=mild, 5=extreme)
8. "product_expectation": "met"/"exceeded"/"below" - did it meet expectations?
9. "repurchase_intent": "likely"/"unlikely"/"unsure"
10. "summary": one sentence summary (max 20 words)

Output ONLY valid JSON, no other text.

Example:
```json
{{
  "sentiment": "negative",
  "pain_points": ["short battery life", "uncomfortable fit"],
  "selling_points": ["good sound quality"],
  "use_cases": ["commuting", "workouts"],
  "user_profile": "fitness enthusiast who values comfort",
  "improvement_suggestions": ["longer battery", "softer ear tips"],
  "emotion_intensity": 3,
  "product_expectation": "below",
  "repurchase_intent": "unlikely",
  "summary": "Good sound but battery and comfort issues"
}}
```"""


def _call_chat_api(prompt: str, api_key: str, api_base: str, model: str,
                   temperature: float = 0.3, max_tokens: int = 600) -> str:
    """调用 Chat API"""
    url = f"{api_base.rstrip('/')}/chat/completions"
    
    resp = requests.post(url, json={
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }, timeout=45)
    
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"]
    else:
        raise Exception(f"API Error {resp.status_code}: {resp.text[:200]}")


def _parse_tags_response(response: str) -> Dict:
    """多策略解析 AI 返回"""
    strategies = [
        lambda s: json.loads(s.strip()),
        lambda s: json.loads(re.search(r'\{[\s\S]*\}', s).group()),
        lambda s: json.loads(re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', s).group(1)),
    ]
    
    for strategy in strategies:
        try:
            result = strategy(response)
            if "sentiment" in result:
                return result
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue
    
    raise ValueError(f"Failed to parse response: {response[:100]}")


def _default_tags(review: Dict) -> Dict:
    """默认打标"""
    rating = review.get("rating", 0)
    sentiment = "positive" if rating >= 4 else "negative" if rating <= 2 else "neutral"
    
    return {
        "sentiment": sentiment,
        "pain_points": [],
        "selling_points": [],
        "use_cases": [],
        "user_profile": "",
        "improvement_suggestions": [],
        "emotion_intensity": abs(3 - rating),
        "product_expectation": "met" if rating >= 3 else "below",
        "repurchase_intent": "likely" if rating >= 4 else "unsure",
        "summary": review.get("title", "")[:20],
    }


# ========== LLM 高级分析 ==========

def _call_llm_negative_analysis(
    summaries: List[str],
    pain_counts: List[tuple],
    api_key: str, api_base: str, model: str, debug: bool
) -> Dict:
    """用 LLM 做差评根因分析"""
    
    summaries_text = "\n".join(f"- {s}" for s in summaries[:30])
    pains_text = "\n".join(f"- {p}: {c} mentions" for p, c in pain_counts)
    
    prompt = f"""Analyze these Amazon product negative review summaries and identify root causes.

Pain point frequencies:
{pains_text}

Review summaries:
{summaries_text}

Output JSON with:
1. "root_causes": array of {{"cause": "specific root cause", "frequency": N, "severity": "critical"/"major"/"minor", "examples": ["quote1", "quote2"]}}
2. "severity_breakdown": {{"critical": N, "major": N, "minor": N}}
3. "improvement_priority": array of {{"issue": "problem", "impact": "business impact", "solution": "actionable fix", "effort": "low"/"medium"/"high"}}
4. "sentiment_trend": "worsening"/"stable"/"improving" with brief reasoning

Output ONLY valid JSON."""

    response = _call_chat_api(prompt, api_key, api_base, model, max_tokens=1500)
    result = _parse_tags_response(response)
    return result


def _call_llm_voc_clustering(
    pains: List[tuple], sells: List[tuple],
    use_cases: List[tuple], improvements: List[tuple],
    api_key: str, api_base: str, model: str, debug: bool
) -> Dict:
    """用 LLM 做 VOC 聚类"""
    
    prompt = f"""Cluster this Amazon product's Voice of Customer (VOC) feedback into themes.

Pain points (with frequency):
{json.dumps(dict(pains[:15]), indent=2)}

Selling points (with frequency):
{json.dumps(dict(sells[:10]), indent=2)}

Use cases (with frequency):
{json.dumps(dict(use_cases[:8]), indent=2)}

Improvement suggestions (with frequency):
{json.dumps(dict(improvements[:8]), indent=2)}

Output JSON with:
1. "clusters": array of {{"theme": "theme name (3-8 words)", "sentiment": "positive"/"mixed"/"negative", "mentions": N, "key_quotes": ["representative phrases"], "insight": "what this reveals about customer needs", "action": "recommended action for product team"}} (4-8 clusters)
2. "customer_expectations": array of {{"expectation": "what customers want", "importance": "high"/"medium"/"low", "gap": "met"/"partially"/"unmet"}} (3-6 items)
3. "unmet_needs": array of "specific needs not addressed by current product" (2-5 items)
4. "delighters": array of "features that exceed expectations" (2-4 items)

Output ONLY valid JSON."""

    response = _call_chat_api(prompt, api_key, api_base, model, max_tokens=2000)
    result = _parse_tags_response(response)
    return result


# ========== 简单回退分析 ==========

def _simple_negative_analysis(pain_counter: Counter) -> Dict:
    """简单的差评统计（无 LLM）"""
    top_pains = pain_counter.most_common(10)
    
    return {
        "total_negative": sum(pain_counter.values()),
        "root_causes": [
            {"cause": p, "frequency": c, "severity": "major" if c > 1 else "minor", "examples": []}
            for p, c in top_pains
        ],
        "severity_breakdown": {"critical": 0, "major": sum(1 for _, c in top_pains if c > 1), "minor": 0},
        "improvement_priority": [
            {"issue": p, "impact": "Customer satisfaction", "solution": "需要深入调查", "effort": "medium"}
            for p, _ in top_pains[:5]
        ],
        "sentiment_trend": "stable",
    }


def _simple_voc_clustering(
    pain_counter: Counter, sell_counter: Counter,
    use_case_counter: Counter, improvement_counter: Counter
) -> Dict:
    """简单的 VOC 聚类（无 LLM）"""
    
    clusters = []
    
    # 痛点聚类
    for pain, count in pain_counter.most_common(5):
        clusters.append({
            "theme": f"客户不满: {pain}",
            "sentiment": "negative",
            "mentions": count,
            "key_quotes": [pain],
            "insight": f"客户对{pain}不满意",
            "action": f"改进{pain}",
        })
    
    # 卖点聚类
    for sell, count in sell_counter.most_common(5):
        clusters.append({
            "theme": f"客户认可: {sell}",
            "sentiment": "positive",
            "mentions": count,
            "key_quotes": [sell],
            "insight": f"{sell}是核心卖点",
            "action": f"在 Listing 中突出{sell}",
        })
    
    return {
        "clusters": clusters[:8],
        "customer_expectations": [
            {"expectation": f"更好的{im}", "importance": "high", "gap": "unmet"}
            for im, _ in improvement_counter.most_common(5)
        ],
        "unmet_needs": [im for im, _ in improvement_counter.most_common(3)],
        "delighters": [s for s, _ in sell_counter.most_common(3)],
    }


if __name__ == "__main__":
    print("AI 分析模块已加载")
    print("需要 API Key 进行真实测试")
