#!/usr/bin/env python3
"""
关键词扩展与挖掘模块
基于评论文本挖掘 + Amazon Suggest API，输出关键词频率/相关性/扩展建议
"""

import re
import json
import urllib.parse
import requests
from typing import Dict, List, Optional, Tuple
from collections import Counter
from utils import safe_get, compute_word_frequency, clean_text


def research_keywords(
    reviews: List[Dict],
    product_title: str = "",
    search_query: str = "",
    market: str = "US",
    debug: bool = False
) -> Dict:
    """
    综合关键词研究

    Args:
        reviews: 评论列表 [{"rating", "title", "body"}, ...]
        product_title: 产品标题
        search_query: 初始搜索关键词
        market: 市场
        debug: 调试

    Returns:
        {
            "high_frequency_keywords": [(词, 频率), ...],
            "pain_point_keywords": [(词, 频率), ...],  # 差评高频词
            "selling_point_keywords": [(词, 频率), ...],  # 好评高频词
            "amazon_suggest_keywords": [...],  # Amazon搜索建议
            "long_tail_keywords": [...],  # 长尾关键词
            "keyword_clusters": {...},  # 关键词分组
            "recommended_keywords": {...},  # 推荐关键词（按类型分组）
        }
    """
    
    result = {
        "high_frequency_keywords": [],
        "pain_point_keywords": [],
        "selling_point_keywords": [],
        "amazon_suggest_keywords": [],
        "long_tail_keywords": [],
        "keyword_clusters": {},
        "recommended_keywords": {},
    }
    
    if debug:
        print("  🔑 开始关键词研究...")
    
    # 1. 从评论中提取高频关键词
    all_review_texts = []
    negative_texts = []
    positive_texts = []
    
    for review in reviews:
        body = review.get("body", "") or review.get("content", "")
        title = review.get("title", "")
        full_text = f"{title} {body}"
        
        all_review_texts.append(full_text)
        
        rating = review.get("rating", 3)
        if rating <= 2:
            negative_texts.append(full_text)
        elif rating >= 4:
            positive_texts.append(full_text)
    
    # 高频词（英文）
    if all_review_texts:
        result["high_frequency_keywords"] = compute_word_frequency(
            all_review_texts, top_n=30, min_len=3, lang="en"
        )
    
    # 差评高频词
    if negative_texts:
        result["pain_point_keywords"] = compute_word_frequency(
            negative_texts, top_n=20, min_len=3, lang="en"
        )
    
    # 好评高频词
    if positive_texts:
        result["selling_point_keywords"] = compute_word_frequency(
            positive_texts, top_n=20, min_len=3, lang="en"
        )
    
    # 2. 提取核心关键词 seed
    seed_keywords = _extract_seed_keywords(product_title, search_query, reviews)
    
    if debug:
        print(f"  📌 种子关键词: {seed_keywords[:10]}")
    
    # 3. 获取 Amazon 搜索建议（自动补全）
    suggest_keywords = []
    for seed in seed_keywords[:3]:
        suggestions = _fetch_amazon_suggestions(seed, market, debug)
        suggest_keywords.extend(suggestions)
    
    # 去重 + 排序（按长度，短在前）
    seen = set()
    unique_suggests = []
    for kw in suggest_keywords:
        kw_lower = kw.lower().strip()
        if kw_lower not in seen and len(kw_lower) > 3:
            seen.add(kw_lower)
            unique_suggests.append(kw_lower)
    
    result["amazon_suggest_keywords"] = sorted(unique_suggests, key=len)[:30]
    
    # 4. 生成长尾关键词
    long_tail = _generate_long_tail_keywords(
        seed_keywords,
        result["pain_point_keywords"],
        result["selling_point_keywords"],
        result["amazon_suggest_keywords"]
    )
    result["long_tail_keywords"] = long_tail[:30]
    
    # 5. 关键词分组/聚类
    result["keyword_clusters"] = _cluster_keywords(result)
    
    # 6. 推荐关键词
    result["recommended_keywords"] = _recommend_keywords(result)
    
    if debug:
        print(f"  ✅ 关键词研究完成: 高频{len(result['high_frequency_keywords'])}个, "
              f"建议{len(result['amazon_suggest_keywords'])}个, "
              f"长尾{len(result['long_tail_keywords'])}个")
    
    return result


def _extract_seed_keywords(title: str, query: str, reviews: List[Dict]) -> List[str]:
    """从标题、搜索词、评论中提取种子关键词"""
    seeds = []
    
    # 从标题提取
    if title:
        # 提取英文单词（2字符以上）
        words = re.findall(r'[a-zA-Z]{2,}', title.lower())
        # 常见停用词过滤
        stopwords = {'the', 'and', 'for', 'with', 'this', 'that', 'new', 'pack',
                     'size', 'color', 'set', 'inch', 'large', 'small', 'pro', 'max'}
        seeds.extend([w for w in words if w not in stopwords])
    
    # 从搜索词提取
    if query:
        words = re.findall(r'[a-zA-Z]{2,}', query.lower())
        seeds.extend([w for w in words if w not in stopwords])
    
    # 去重，保持顺序
    seen = set()
    unique_seeds = []
    for s in seeds:
        if s not in seen:
            seen.add(s)
            unique_seeds.append(s)
    
    return unique_seeds[:10]


def _fetch_amazon_suggestions(query: str, market: str = "US", debug: bool = False) -> List[str]:
    """获取 Amazon 搜索自动补全建议"""
    suggestions = []
    
    market_config = {
        "US": "com",
        "UK": "co.uk",
        "DE": "de",
        "JP": "co.jp",
        "FR": "fr",
        "CA": "ca",
    }
    
    tld = market_config.get(market.upper(), "com")
    
    try:
        # Amazon 搜索建议 API
        encoded = urllib.parse.quote(query)
        url = f"https://completion.amazon.{tld}/api/2017/suggestions?mid=ATVPDKIKX0DER&alias=aps&prefix={encoded}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            for suggestion in data.get("suggestions", []):
                value = suggestion.get("value", "")
                if value:
                    suggestions.append(value)
        
        if debug and suggestions:
            print(f"  💡 Amazon建议 ({query}): {suggestions[:5]}")
    
    except Exception as e:
        if debug:
            print(f"  ⚠️ Amazon建议获取失败: {e}")
        
        # 备用方案：使用爬虫搜索
        try:
            alt_url = f"https://www.amazon.{tld}/s?k={urllib.parse.quote(query)}"
            html = safe_get(alt_url, timeout=10)
            if html:
                # 提取相关搜索
                related = re.findall(r'data-keyword="([^"]+)"', html)
                suggestions.extend(related[:10])
        except Exception:
            pass
    
    return suggestions


def _generate_long_tail_keywords(
    seeds: List[str],
    pain_kws: List[tuple],
    sell_kws: List[tuple],
    suggests: List[str]
) -> List[str]:
    """生成长尾关键词"""
    long_tail = set()
    
    # 修饰词
    modifiers = [
        "best", "top rated", "premium", "budget", "cheap",
        "professional", "portable", "compact", "lightweight",
        "high quality", "durable", "easy to use",
        "for beginners", "for professionals", "for travel",
        "with case", "wireless", "rechargeable",
        "2024", "2025", "latest", "new model",
        "noise cancelling", "waterproof", "bluetooth",
    ]
    
    # 场景词
    scenarios = [
        "for home", "for office", "for travel", "for gym",
        "for kids", "for elderly", "for students",
        "for gaming", "for work", "for sports",
    ]
    
    # 组合生成
    for seed in seeds[:5]:
        for mod in modifiers[:10]:
            long_tail.add(f"{mod} {seed}")
        for scenario in scenarios[:5]:
            long_tail.add(f"{seed} {scenario}")
    
    # 加入 Amazon 建议
    long_tail.update(suggests[:20])
    
    # 加入差评词组合
    pain_words = [w for w, _ in pain_kws[:5]]
    sell_words = [w for w, _ in sell_kws[:5]]
    
    for seed in seeds[:3]:
        for pw in pain_words:
            long_tail.add(f"{seed} {pw}")
        for sw in sell_words:
            long_tail.add(f"{seed} with {sw}")
    
    return list(long_tail)


def _cluster_keywords(result: Dict) -> Dict:
    """对关键词进行简单分组"""
    clusters = {
        "产品属性": [],
        "功能特性": [],
        "使用场景": [],
        "质量问题": [],
        "价格相关": [],
        "品牌相关": [],
    }
    
    # 属性词
    attr_words = {'size', 'color', 'weight', 'material', 'design', 'shape',
                  'dimension', 'length', 'width', 'height', '容量', '尺寸', '颜色'}
    
    # 功能词
    func_words = {'bluetooth', 'wireless', 'noise', 'cancelling', 'waterproof',
                  'rechargeable', 'battery', 'charging', 'portable', 'connect',
                  'speed', 'power', 'volume', 'sound', 'quality'}
    
    # 场景词
    scene_words = {'travel', 'home', 'office', 'gym', 'sports', 'outdoor',
                   'work', 'gaming', 'study', 'school', 'car', 'kitchen'}
    
    # 问题词
    problem_words = {'broken', 'defective', 'poor', 'cheap', 'waste', 'bad',
                     'issue', 'problem', 'fail', 'return', 'refund', 'disappointed'}
    
    # 价格词
    price_words = {'price', 'worth', 'value', 'expensive', 'cheap', 'affordable',
                   'overpriced', 'deal', 'discount', 'budget', 'cost'}
    
    all_kws = result["high_frequency_keywords"] + result["pain_point_keywords"]
    
    for word, count in all_kws:
        word_lower = word.lower()
        
        if word_lower in attr_words:
            clusters["产品属性"].append({"word": word, "count": count})
        elif word_lower in func_words:
            clusters["功能特性"].append({"word": word, "count": count})
        elif word_lower in scene_words:
            clusters["使用场景"].append({"word": word, "count": count})
        elif word_lower in problem_words:
            clusters["质量问题"].append({"word": word, "count": count})
        elif word_lower in price_words:
            clusters["价格相关"].append({"word": word, "count": count})
    
    # 品牌词（大写开头的词）
    for word, count in all_kws:
        if word[0].isupper() and len(word) > 1:
            clusters["品牌相关"].append({"word": word, "count": count})
    
    return {k: v for k, v in clusters.items() if v}


def _recommend_keywords(result: Dict) -> Dict:
    """生成关键词推荐"""
    recommends = {
        "高转化词": [],
        "低竞争词": [],
        "长尾机会词": [],
        "差评机会词": [],
    }
    
    # 取高频词中频率中等但相关的作为高转化词
    hf_kws = result["high_frequency_keywords"]
    if hf_kws:
        # 取频率前10-20%（不是最高频但仍有搜索量的）
        mid = max(len(hf_kws) // 5, 1)
        recommends["高转化词"] = [{"keyword": w, "frequency": c} 
                                 for w, c in hf_kws[mid:mid+10]]
    
    # 长尾机会词（取 Amazon 建议中的长词）
    suggests = result.get("amazon_suggest_keywords", [])
    recommends["长尾机会词"] = [{"keyword": kw, "type": "long_tail"}
                               for kw in suggests[:10] if len(kw) > 15]
    
    # 从 Amazon 建议中取较短但具体的作为低竞争词
    recommends["低竞争词"] = [{"keyword": kw, "type": "amazon_suggest"}
                             for kw in suggests[5:15] if 10 < len(kw) < 30]
    
    # 差评机会词（竞品差评相关词 → 可在 Listing 中突出解决）
    pain_kws = result.get("pain_point_keywords", [])
    recommends["差评机会词"] = [{"keyword": f"no {w} solution", "source": "pain_point"}
                               for w, _ in pain_kws[:8]]
    
    return {k: v for k, v in recommends.items() if v}


if __name__ == "__main__":
    # 测试
    test_reviews = [
        {"rating": 5, "title": "Amazing sound quality", "body": "The sound quality is amazing. Battery lasts forever. Noise cancelling works perfectly."},
        {"rating": 1, "title": "Broke after a week", "body": "These broke after just one week. Very poor build quality. Would not recommend."},
        {"rating": 4, "title": "Good value for money", "body": "Good sound for the price. Battery life is decent. Comfortable to wear."},
        {"rating": 2, "title": "Not comfortable", "body": "They hurt my ears after 30 minutes. The ear tips are too hard. Returning them."},
    ]
    
    result = research_keywords(
        reviews=test_reviews,
        product_title="Wireless Bluetooth Earbuds Noise Cancelling",
        search_query="bluetooth earbuds",
        debug=True,
    )
    
    print("\n" + "=" * 50)
    print("关键词研究结果")
    print("=" * 50)
    print(f"高频词: {result['high_frequency_keywords'][:10]}")
    print(f"差评词: {result['pain_point_keywords'][:10]}")
    print(f"Amazon建议: {result['amazon_suggest_keywords'][:10]}")
    print(f"长尾词: {result['long_tail_keywords'][:10]}")
