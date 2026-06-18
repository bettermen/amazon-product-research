#!/usr/bin/env python3
"""
竞品分析模块
搜索、对比、分析竞争产品
"""

import re
import json
import urllib.parse
import requests
from typing import Dict, List, Optional
from utils import (
    get_market_host, clean_text, safe_get, create_session,
    format_number, format_price
)


def analyze_competitors(
    primary_product: Dict,
    search_query: str,
    market: str = "US",
    max_competitors: int = 5,
    debug: bool = False
) -> Dict:
    """
    竞品分析

    Args:
        primary_product: 主产品信息 {"asin", "title", "price", "rating", ...}
        search_query: 搜索关键词
        market: 市场
        max_competitors: 最多分析几个竞品
        debug: 调试

    Returns:
        {
            "competitors": [
                {
                    "asin": "...",
                    "title": "...",
                    "price": "...",
                    "rating": 4.2,
                    "total_reviews": 1234,
                    "ranking": 1,
                    "strengths": [...],
                    "weaknesses": [...],
                    "differentiation": "...",
                    "similarity_score": 0.85,
                }
            ],
            "market_overview": {
                "avg_price": "$XX",
                "avg_rating": 4.1,
                "price_range": "$X - $XX",
                "total_products_in_category": N,
            },
            "competitive_position": {
                "price_position": "above_average"/"below_average"/"average",
                "rating_position": "...",
                "review_count_position": "...",
                "overall_rank": "leader"/"challenger"/"niche"/"new_entrant",
            },
            "gap_analysis": {
                "feature_gaps": [...],
                "pricing_gaps": [...],
                "opportunity_areas": [...],
            }
        }
    """
    
    if debug:
        print(f"  🏪 分析竞品格局...")
    
    host = get_market_host(market)
    
    # 1. 搜索竞品
    competitors = _search_competitors(
        search_query, primary_product.get("asin", ""), 
        host, max_competitors, debug
    )
    
    if debug:
        print(f"  找到 {len(competitors)} 个潜在竞品")
    
    # 2. 获取每个竞品的详细信息
    for comp in competitors:
        try:
            details = _scrape_competitor_details(comp["asin"], host, debug)
            comp.update(details)
        except Exception as e:
            if debug:
                print(f"  ⚠️ 获取竞品 {comp['asin']} 详情失败: {e}")
    
    # 3. 计算市场概览
    market_overview = _compute_market_overview(primary_product, competitors)
    
    # 4. 评估竞争位置
    competitive_position = _evaluate_position(primary_product, competitors)
    
    # 5. 差距分析
    gap_analysis = _analyze_gaps(primary_product, competitors, debug)
    
    result = {
        "competitors": competitors,
        "market_overview": market_overview,
        "competitive_position": competitive_position,
        "gap_analysis": gap_analysis,
    }
    
    if debug:
        print(f"  ✅ 竞品分析完成")
    
    return result


def _search_competitors(query: str, primary_asin: str, host: str, 
                        max_count: int, debug: bool) -> List[Dict]:
    """在 Amazon 上搜索竞品"""
    
    competitors = []
    
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://www.{host}/s?k={encoded}&ref=nb_sb_noss"
        
        html = safe_get(url, timeout=15)
        if not html:
            return competitors
        
        # 提取搜索结果中的 ASIN
        asin_pattern = r'data-asin="([A-Z0-9]{10})"'
        asins = re.findall(asin_pattern, html)
        
        # 去重 + 排除主产品
        seen = {primary_asin}
        count = 0
        
        for asin in asins:
            if asin in seen or asin == "" or count >= max_count:
                continue
            seen.add(asin)
            count += 1
            
            competitor = _parse_competitor_from_search(html, asin, host)
            if competitor:
                competitors.append(competitor)
        
        # 备用：从文本中提取产品链接
        if not competitors:
            competitors = _fallback_competitor_search(html, host, primary_asin, max_count)
    
    except Exception as e:
        if debug:
            print(f"  ⚠️ 竞品搜索异常: {e}")
    
    return competitors[:max_count]


def _parse_competitor_from_search(html: str, asin: str, host: str) -> Optional[Dict]:
    """从搜索结果解析单个竞品"""
    try:
        card_start = html.find(f'data-asin="{asin}"')
        if card_start == -1:
            return None
        
        card_html = html[max(0, card_start - 1000):card_start + 3000]
        
        comp = {
            "asin": asin,
            "title": f"Product {asin}",
            "price": "N/A",
            "rating": 0,
            "total_reviews": 0,
            "image_url": "",
            "url": f"https://www.{host}/dp/{asin}",
            "ranking": 0,
            "similarity_score": 0.7,
        }
        
        # 提取标题
        title_patterns = [
            r'<span[^>]*class="a-size-medium a-color-base a-text-normal"[^>]*>(.*?)</span>',
            r'<h2[^>]*class="a-size-mini a-spacing-none a-color-base s-line-clamp-2"[^>]*>.*?<span[^>]*>(.*?)</span>',
            r'<span[^>]*class="a-size-base-plus a-color-base a-text-normal"[^>]*>(.*?)</span>',
        ]
        for pat in title_patterns:
            tm = re.search(pat, card_html, re.DOTALL)
            if tm:
                title = clean_text(tm.group(1))
                if len(title) > 10:
                    comp["title"] = title
                    break
        
        # 提取价格
        price_match = re.search(r'<span class="a-price-whole">([\d,]+)', card_html)
        if price_match:
            comp["price"] = f"${price_match.group(1)}"
        
        # 提取评分
        rating_match = re.search(r'<span[^>]*class="a-icon-alt"[^>]*>([\d.]+) out of 5', card_html)
        if rating_match:
            comp["rating"] = float(rating_match.group(1))
        
        # 提取评论数
        review_match = re.search(r'([\d,]+)\s*(?:ratings|reviews)', card_html, re.IGNORECASE)
        if review_match:
            comp["total_reviews"] = int(review_match.group(1).replace(',', ''))
        
        # 提取图片
        img_match = re.search(r'src="(https://m\.media-amazon\.com/images/[^"]+)"', card_html)
        if img_match:
            comp["image_url"] = img_match.group(1)
        
        return comp if comp["title"] else None
    
    except Exception:
        return None


def _fallback_competitor_search(html: str, host: str, exclude_asin: str, max_count: int) -> List[Dict]:
    """备用竞品搜索"""
    competitors = []
    seen = {exclude_asin}
    
    link_pattern = r'href="(/dp/([A-Z0-9]{10})/ref=[^"]*)"'
    matches = re.findall(link_pattern, html)
    
    count = 0
    for url_path, asin in matches:
        if asin in seen or count >= max_count:
            continue
        seen.add(asin)
        count += 1
        
        competitors.append({
            "asin": asin,
            "title": f"Product {asin}",
            "price": "N/A",
            "rating": 0,
            "total_reviews": 0,
            "image_url": "",
            "url": f"https://www.{host}{url_path}",
            "ranking": count,
            "similarity_score": 0.5,
        })
    
    return competitors


def _scrape_competitor_details(asin: str, host: str, debug: bool) -> Dict:
    """爬取竞品详细信息"""
    
    details = {}
    
    try:
        url = f"https://www.{host}/dp/{asin}"
        html = safe_get(url, timeout=15)
        
        if not html:
            return details
        
        # 特征提取
        features = []
        
        # 从标题/五点/A+内容中提取特征
        feature_sections = re.findall(r'<li[^>]*>(.*?)</li>', html)
        for section in feature_sections[:10]:
            text = clean_text(section)
            if len(text) > 5:
                features.append(text)
        
        details["features"] = features[:10]
        
        # 分析优劣势（基于评分 + 价格）
        # 这里做简单推断，实际应基于评论分析
        strengths = []
        weaknesses = []
        
        # 从标题提取可能的关键特性
        title_match = re.search(r'<span[^>]*id="productTitle"[^>]*>(.*?)</span>', html, re.DOTALL)
        if title_match:
            title = clean_text(title_match.group(1)).lower()
            pos_keywords = ['premium', 'professional', 'durable', 'best', 'top', 'quality',
                          'noise cancel', 'waterproof', 'bluetooth 5', 'long battery',
                          'fast charge', 'hi-res', 'ergonomic']
            neg_keywords = ['basic', 'budget', 'cheap', 'entry']
            
            for kw in pos_keywords:
                if kw in title:
                    strengths.append(f"Feature: {kw}")
        
        details["strengths"] = strengths[:5] or ["Competitive product"]
        details["weaknesses"] = weaknesses[:3] or ["Insufficient data"]
        details["differentiation"] = "Standard competitive product"
    
    except Exception as e:
        if debug:
            print(f"    ⚠️ 爬取 {asin} 详情异常: {e}")
    
    return details


def _compute_market_overview(primary: Dict, competitors: List[Dict]) -> Dict:
    """计算市场概览"""
    
    all_products = [primary] + competitors
    
    prices = []
    ratings = []
    reviews = []
    
    for p in all_products:
        # 解析价格
        price_str = p.get("price", "N/A")
        price_nums = re.findall(r'[\d.]+', str(price_str))
        if price_nums:
            try:
                prices.append(float(price_nums[0]))
            except ValueError:
                pass
        
        rating = p.get("rating", 0)
        if rating and rating > 0:
            ratings.append(float(rating))
        
        rv = p.get("total_reviews", 0)
        if rv:
            reviews.append(int(rv))
    
    avg_price = sum(prices) / len(prices) if prices else 0
    avg_rating = sum(ratings) / len(ratings) if ratings else 0
    avg_reviews = sum(reviews) / len(reviews) if reviews else 0
    
    return {
        "avg_price": f"${avg_price:.2f}" if avg_price else "N/A",
        "avg_rating": round(avg_rating, 1),
        "avg_review_count": format_number(int(avg_reviews)),
        "price_range": f"${min(prices):.2f} - ${max(prices):.2f}" if prices else "N/A",
        "price_std": round((sum((p - avg_price)**2 for p in prices) / len(prices))**0.5, 2) if len(prices) > 1 else 0,
        "products_analyzed": len(all_products),
        "competitor_count": len(competitors),
    }


def _evaluate_position(primary: Dict, competitors: List[Dict]) -> Dict:
    """评估竞争位置"""
    
    primary_price = 0
    price_match = re.search(r'[\d.]+', str(primary.get("price", "0")))
    if price_match:
        primary_price = float(price_match.group())
    
    primary_rating = float(primary.get("rating", 0))
    primary_reviews = int(primary.get("total_reviews", 0))
    
    # 收集所有竞品数据
    comp_prices = []
    comp_ratings = []
    comp_reviews = []
    
    for c in competitors:
        pm = re.search(r'[\d.]+', str(c.get("price", "0")))
        if pm:
            comp_prices.append(float(pm.group()))
        if c.get("rating", 0) > 0:
            comp_ratings.append(float(c["rating"]))
        if c.get("total_reviews", 0) > 0:
            comp_reviews.append(int(c["total_reviews"]))
    
    # 价格定位
    if comp_prices:
        avg_price = sum(comp_prices) / len(comp_prices)
        if primary_price > avg_price * 1.2:
            price_position = "above_average"
        elif primary_price < avg_price * 0.8:
            price_position = "below_average"
        else:
            price_position = "average"
    else:
        price_position = "unknown"
    
    # 评分定位
    if comp_ratings:
        avg_rating = sum(comp_ratings) / len(comp_ratings)
        if primary_rating > avg_rating + 0.3:
            rating_position = "above_average"
        elif primary_rating < avg_rating - 0.3:
            rating_position = "below_average"
        else:
            rating_position = "average"
    else:
        rating_position = "unknown"
    
    # 评论数定位
    if comp_reviews:
        avg_rv = sum(comp_reviews) / len(comp_reviews)
        if primary_reviews > avg_rv * 2:
            review_position = "market_leader"
        elif primary_reviews > avg_rv:
            review_position = "above_average"
        else:
            review_position = "below_average"
    else:
        review_position = "unknown"
    
    # 综合排名
    scores = 0
    if price_position == "below_average":
        scores += 1
    if rating_position == "above_average":
        scores += 1
    if review_position == "market_leader":
        scores += 2
    elif review_position == "above_average":
        scores += 1
    
    if primary_rating >= 4.3 and primary_reviews >= 1000:
        overall = "leader"
    elif primary_rating >= 4.0 and primary_reviews >= 100:
        overall = "challenger"
    elif primary_reviews < 50:
        overall = "new_entrant"
    else:
        overall = "niche"
    
    return {
        "price_position": price_position,
        "rating_position": rating_position,
        "review_count_position": review_position,
        "overall_rank": overall,
        "primary_price": f"${primary_price:.2f}" if primary_price else "N/A",
        "primary_rating": primary_rating,
        "primary_reviews": format_number(primary_reviews),
    }


def _analyze_gaps(primary: Dict, competitors: List[Dict], debug: bool) -> Dict:
    """差距分析"""
    
    gaps = {
        "feature_gaps": [],
        "pricing_gaps": [],
        "opportunity_areas": [],
    }
    
    # 价格差距
    primary_price = 0
    pm = re.search(r'[\d.]+', str(primary.get("price", "0")))
    if pm:
        primary_price = float(pm.group())
    
    for c in competitors:
        cm = re.search(r'[\d.]+', str(c.get("price", "0")))
        if cm:
            cp = float(cm.group())
            diff = cp - primary_price
            if diff > 0:
                gaps["pricing_gaps"].append({
                    "competitor": c.get("title", "Unknown"),
                    "price_diff": f"+${diff:.2f}",
                    "insight": f"竞品比主产品贵 ${diff:.2f}，可主打性价比" if diff > 5 else "价格接近，需突出差异化",
                })
            elif diff < 0:
                gaps["pricing_gaps"].append({
                    "competitor": c.get("title", "Unknown"),
                    "price_diff": f"-${abs(diff):.2f}",
                    "insight": "竞品更便宜，需突出品质/功能优势",
                })
    
    # 评分差距
    primary_rating = primary.get("rating", 0)
    for c in competitors:
        cr = c.get("rating", 0)
        if cr > primary_rating + 0.2:
            gaps["feature_gaps"].append({
                "competitor": c.get("title", "Unknown"),
                "gap": f"评分高 {cr - primary_rating:.1f} 分",
                "action": f"分析 {c.get('asin', '')} 的评论找出差异化",
            })
    
    # 机会领域
    gaps["opportunity_areas"] = [
        {
            "area": "Listing 优化",
            "opportunity": "基于差评分析改进标题、五点、描述",
            "potential_impact": "高",
        },
        {
            "area": "定价策略",
            "opportunity": "根据竞品价格调整定价/促销策略",
            "potential_impact": "中",
        },
        {
            "area": "产品改进",
            "opportunity": "基于 VOC 数据改进产品设计/质量",
            "potential_impact": "高",
        },
        {
            "area": "评论管理",
            "opportunity": "主动回应用户差评，提升品牌形象",
            "potential_impact": "中",
        },
    ]
    
    return gaps


if __name__ == "__main__":
    test_product = {
        "asin": "B0CHX1W1XY",
        "title": "Wireless Bluetooth Earbuds",
        "price": "$29.99",
        "rating": 4.2,
        "total_reviews": 500,
    }
    
    result = analyze_competitors(
        primary_product=test_product,
        search_query="bluetooth earbuds",
        max_competitors=3,
        debug=True,
    )
    
    print(f"\n竞品数量: {len(result['competitors'])}")
    print(f"市场均价: {result['market_overview']['avg_price']}")
    print(f"竞争定位: {result['competitive_position']['overall_rank']}")
