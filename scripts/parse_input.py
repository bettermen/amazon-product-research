#!/usr/bin/env python3
"""
智能输入解析模块
支持 ASIN/产品名/一句话描述 → 自动搜索 Amazon 找到匹配产品
"""

import re
import json
import requests
import urllib.parse
from typing import Dict, List, Optional, Tuple


def parse_user_input(user_input: str, market: str = "US", debug: bool = False) -> Dict:
    """
    解析用户输入，识别类型并搜索产品

    Args:
        user_input: 用户输入（ASIN / 产品名 / 描述）
        market: 目标市场（US/UK/DE/JP等）
        debug: 调试模式

    Returns:
        {
            "input_type": "asin" | "product_name" | "description",
            "original_input": "原始输入",
            "market": "US",
            "products": [
                {
                    "asin": "B0XXXXX",
                    "title": "产品标题",
                    "price": "$XX.XX",
                    "rating": 4.3,
                    "total_reviews": 1234,
                    "image_url": "...",
                    "url": "...",
                    "relevance": 0.95,
                    "rank": "#1 in Category",
                    "brand": "品牌名"
                }
            ],
            "primary_asin": "B0XXXXX",  # 最佳匹配的ASIN
            "search_query": "搜索关键词"
        }
    """
    result = {
        "input_type": None,
        "original_input": user_input.strip(),
        "market": market,
        "products": [],
        "primary_asin": None,
        "search_query": user_input.strip()
    }

    # 1. 检测是否是 ASIN
    asin = _extract_asin(user_input)
    if asin:
        result["input_type"] = "asin"
        result["primary_asin"] = asin
        if debug:
            print(f"  检测到 ASIN: {asin}")
        # 通过 ASIN 获取产品信息
        product = _fetch_product_by_asin(asin, market, debug)
        if product:
            result["products"].append(product)
        return result

    # 2. 检测是否是 Amazon URL
    url_asin = _extract_asin_from_url(user_input)
    if url_asin:
        result["input_type"] = "asin"
        result["primary_asin"] = url_asin
        if debug:
            print(f"  从 URL 提取 ASIN: {url_asin}")
        product = _fetch_product_by_asin(url_asin, market, debug)
        if product:
            result["products"].append(product)
        return result

    # 3. 否则当作产品名/描述来搜索
    result["input_type"] = "product_name" if len(user_input) < 80 else "description"
    
    # 提取搜索关键词
    search_query = _extract_search_query(user_input)
    result["search_query"] = search_query
    
    if debug:
        print(f"  搜索关键词: {search_query}")
    
    # 搜索 Amazon 产品
    products = _search_amazon_products(search_query, market, debug)
    
    if products:
        result["products"] = products[:5]  # 取前5个
        result["primary_asin"] = products[0]["asin"]
    
    return result


def _extract_asin(text: str) -> Optional[str]:
    """从文本中提取 ASIN（10位字母数字组合）"""
    # ASIN 格式: B0 + 8位字母数字
    patterns = [
        r'\b([A-Z0-9]{10})\b',  # 标准10位
        r'[Aa][Ss][Ii][Nn][:：\s]*([A-Z0-9]{10})',  # ASIN: B0XXXXX
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            asin = match.group(1)
            # 验证 ASIN 格式（以B开头且仅字母数字）
            if re.match(r'^[A-Z0-9]{10}$', asin) and asin.startswith('B'):
                return asin
    
    return None


def _extract_asin_from_url(text: str) -> Optional[str]:
    """从 Amazon URL 提取 ASIN"""
    patterns = [
        r'amazon\.[a-z.]+/dp/([A-Z0-9]{10})',
        r'amazon\.[a-z.]+/.*?/dp/([A-Z0-9]{10})',
        r'/dp/([A-Z0-9]{10})',
        r'/product/([A-Z0-9]{10})',
        r'ASIN[=]?([A-Z0-9]{10})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def _extract_search_query(text: str) -> str:
    """从用户输入提取搜索关键词"""
    # 去除常见停用词和多余空格
    stop_words = ['the', 'a', 'an', 'is', 'are', 'was', 'were',
                  '请', '帮', '我', '分析', '一下', '这个', '产品',
                  '搜索', '找', '查', '看看', '怎么样', '好不好']
    
    # 简单清洗
    cleaned = text.strip()
    
    # 如果中文较多，保留原文
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', cleaned))
    if chinese_chars > 5:
        # 提取英文关键词部分
        eng_keywords = re.findall(r'[a-zA-Z0-9\s\-]+', cleaned)
        if eng_keywords:
            return ' '.join(eng_keywords).strip()
    
    return cleaned[:200]  # 限制长度


def _fetch_product_by_asin(asin: str, market: str, debug: bool) -> Optional[Dict]:
    """通过 ASIN 获取产品信息（使用 Amazon Product Advertising API 或爬取）"""
    
    market_config = {
        "US": "amazon.com",
        "UK": "amazon.co.uk",
        "DE": "amazon.de",
        "JP": "amazon.co.jp",
        "FR": "amazon.fr",
        "CA": "amazon.ca",
        "IT": "amazon.it",
        "ES": "amazon.es",
    }
    
    host = market_config.get(market.upper(), "amazon.com")
    
    # 构建产品信息（通过 scraping Amazon 页面）
    product = {
        "asin": asin,
        "title": f"Product {asin}",
        "price": "N/A",
        "rating": 0,
        "total_reviews": 0,
        "image_url": f"https://ws-na.amazon-adsystem.com/widgets/q?_encoding=UTF8&ASIN={asin}&Format=_SL250_",
        "url": f"https://www.{host}/dp/{asin}",
        "relevance": 1.0,
        "rank": "N/A",
        "brand": "N/A"
    }
    
    # 尝试爬取产品页面获取基本信息
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        url = f"https://www.{host}/dp/{asin}"
        
        resp = requests.get(url, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            html = resp.text
            
            # 提取标题
            title_match = re.search(r'<span[^>]*id="productTitle"[^>]*>(.*?)</span>', html, re.DOTALL)
            if title_match:
                product["title"] = title_match.group(1).strip()
            
            # 提取价格
            price_patterns = [
                r'<span class="a-price-whole">([\d,]+)',
                r'<span[^>]*data-a-color="price"[^>]*>.*?\$([\d.]+)',
                r'"price":"\$?([\d.]+)"',
            ]
            for pat in price_patterns:
                pm = re.search(pat, html)
                if pm:
                    product["price"] = f"${pm.group(1)}"
                    break
            
            # 提取评分
            rating_match = re.search(r'<span[^>]*>([\d.]+) out of 5', html)
            if not rating_match:
                rating_match = re.search(r'"ratingValue":"([\d.]+)"', html)
            if rating_match:
                product["rating"] = float(rating_match.group(1))
            
            # 提取评论数
            review_match = re.search(r'([\d,]+) (?:global )?ratings', html)
            if not review_match:
                review_match = re.search(r'"reviewCount":"(\d+)"', html)
            if review_match:
                product["total_reviews"] = int(review_match.group(1).replace(',', ''))
            
            if debug:
                print(f"  产品: {product['title'][:60]}...")
                print(f"  价格: {product['price']} | 评分: {product['rating']} | 评论: {product['total_reviews']}")
    
    except Exception as e:
        if debug:
            print(f"  ⚠️ 爬取产品信息失败: {e}")
    
    return product


def _search_amazon_products(query: str, market: str = "US", debug: bool = False) -> List[Dict]:
    """
    在 Amazon 上搜索产品
    
    使用 Amazon 搜索页面 + 解析结果
    """
    
    host = {
        "US": "amazon.com",
        "UK": "amazon.co.uk",
        "DE": "amazon.de",
        "JP": "amazon.co.jp",
    }.get(market.upper(), "amazon.com")
    
    products = []
    
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"https://www.{host}/s?k={encoded_query}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        
        if debug:
            print(f"  搜索 URL: {url}")
        
        resp = requests.get(url, headers=headers, timeout=20)
        
        if resp.status_code != 200:
            if debug:
                print(f"  搜索返回状态码: {resp.status_code}")
            return products
        
        html = resp.text
        
        # 解析搜索结果
        # 方法1: 提取 data-asin 属性
        asin_pattern = r'data-asin="([A-Z0-9]{10})"'
        asins = re.findall(asin_pattern, html)
        seen_asins = set()
        unique_asins = []
        for a in asins:
            if a not in seen_asins and a != "":
                seen_asins.add(a)
                unique_asins.append(a)
        
        if debug:
            print(f"  找到 {len(unique_asins)} 个 ASIN")
        
        # 解析每个产品卡片
        for asin in unique_asins[:10]:
            product = _parse_search_result_card(html, asin, host)
            if product:
                products.append(product)
        
        # 如果解析不到，用备用方法
        if not products:
            products = _parse_search_fallback(html, host)
        
        if debug:
            print(f"  成功解析 {len(products)} 个产品")
            for p in products[:3]:
                print(f"    - {p['title'][:50]}... [{p['rating']}★, {p['total_reviews']} reviews]")
    
    except Exception as e:
        if debug:
            print(f"  搜索异常: {e}")
    
    return products


def _parse_search_result_card(html: str, asin: str, host: str) -> Optional[Dict]:
    """从搜索结果页面解析单个产品卡片"""
    try:
        # 找到该 ASIN 对应的产品卡片区域
        card_start = html.find(f'data-asin="{asin}"')
        if card_start == -1:
            return None
        
        # 提取卡片周围约 5000 字符的 HTML
        card_html = html[max(0, card_start - 500):card_start + 5000]
        
        product = {
            "asin": asin,
            "title": "",
            "price": "N/A",
            "rating": 0,
            "total_reviews": 0,
            "image_url": f"https://ws-na.amazon-adsystem.com/widgets/q?_encoding=UTF8&ASIN={asin}&Format=_SL250_",
            "url": f"https://www.{host}/dp/{asin}",
            "relevance": 0.9,
            "rank": "N/A",
            "brand": "N/A"
        }
        
        # 提取标题
        title_patterns = [
            r'<span[^>]*class="a-size-medium a-color-base a-text-normal"[^>]*>(.*?)</span>',
            r'<span[^>]*class="a-size-base-plus a-color-base a-text-normal"[^>]*>(.*?)</span>',
            r'<h2[^>]*>.*?<span[^>]*>(.*?)</span>',
            r'aria-label="([^"]*?)"',
        ]
        for pat in title_patterns:
            tm = re.search(pat, card_html, re.DOTALL)
            if tm:
                title = tm.group(1).strip()
                if len(title) > 10:
                    product["title"] = _clean_html(title)
                    break
        
        # 提取价格
        price_patterns = [
            r'<span class="a-price[^"]*">.*?<span class="a-offscreen">\$([\d.]+)</span>',
            r'\$([\d.]+)\s*</span>',
        ]
        for pat in price_patterns:
            pm = re.search(pat, card_html, re.DOTALL)
            if pm:
                product["price"] = f"${pm.group(1)}"
                break
        
        # 提取评分
        rating_match = re.search(r'<span[^>]*>([\d.]+) out of 5', card_html)
        if rating_match:
            product["rating"] = float(rating_match.group(1))
        
        # 提取评论数
        review_match = re.search(r'([\d,]+)\s*(?:ratings|reviews)', card_html, re.IGNORECASE)
        if review_match:
            product["total_reviews"] = int(review_match.group(1).replace(',', ''))
        
        return product if product["title"] else None
    
    except Exception:
        return None


def _parse_search_fallback(html: str, host: str) -> List[Dict]:
    """备用解析方法：提取页面中所有产品链接"""
    products = []
    seen = set()
    
    # 提取所有 /dp/ASIN 链接
    link_pattern = r'href="(/dp/([A-Z0-9]{10})/[^"]*)"'
    matches = re.findall(link_pattern, html)
    
    for url_path, asin in matches:
        if asin in seen:
            continue
        seen.add(asin)
        
        product = {
            "asin": asin,
            "title": f"Product {asin}",
            "price": "N/A",
            "rating": 0,
            "total_reviews": 0,
            "image_url": f"https://ws-na.amazon-adsystem.com/widgets/q?_encoding=UTF8&ASIN={asin}&Format=_SL250_",
            "url": f"https://www.{host}{url_path}",
            "relevance": 0.7,
            "rank": "N/A",
            "brand": "N/A"
        }
        products.append(product)
        
        if len(products) >= 10:
            break
    
    return products


def _clean_html(text: str) -> str:
    """清洗 HTML 标签"""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#39;', "'", text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


if __name__ == "__main__":
    # 测试
    test_cases = [
        "B0CHX1W1XY",
        "bluetooth earbuds noise cancelling",
        "https://www.amazon.com/dp/B08N5WRWNW",
        "AirPods Pro 2 分析一下",
    ]
    
    for test in test_cases:
        print(f"\n{'='*60}")
        print(f"输入: {test}")
        print(f"{'='*60}")
        result = parse_user_input(test, debug=True)
        print(f"类型: {result['input_type']}")
        print(f"主ASIN: {result['primary_asin']}")
        if result['products']:
            print(f"产品: {result['products'][0]['title'][:50]}")
            print(f"价格: {result['products'][0]['price']}")
            print(f"评分: {result['products'][0]['rating']}")
