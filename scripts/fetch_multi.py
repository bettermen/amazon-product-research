#!/usr/bin/env python3
"""
多产品评论采集模块
同时获取主产品 + 竞品评论
"""

import re
import json
import time
import requests
from typing import Dict, List, Optional
from datetime import datetime

from utils import (
    get_market_host, clean_text, create_session, safe_get, format_number
)


def fetch_multi_product_reviews(
    primary_asin: str,
    competitor_asins: List[str] = None,
    market: str = "US",
    max_reviews_per_product: int = 200,
    debug: bool = False
) -> Dict:
    """
    批量获取多个产品的评论数据

    Args:
        primary_asin: 主产品 ASIN
        competitor_asins: 竞品 ASIN 列表
        market: 市场
        max_reviews_per_product: 每个产品最大评论数
        debug: 调试

    Returns:
        {
            "products": {
                "B0XXX": {
                    "info": {...},
                    "reviews": [...],
                }
            },
            "total_reviews": int,
            "fetch_time": "ISO datetime"
        }
    """
    
    all_asins = [primary_asin]
    if competitor_asins:
        all_asins.extend(competitor_asins)
    
    # 去重
    all_asins = list(dict.fromkeys(all_asins))
    
    if debug:
        print(f"  📦 开始获取 {len(all_asins)} 个产品的评论...")
    
    products = {}
    total_reviews = 0
    
    host = get_market_host(market)
    
    for i, asin in enumerate(all_asins):
        if debug:
            print(f"  [{i+1}/{len(all_asins)}] 获取 {asin}...")
        
        try:
            product_data = _fetch_single_product(asin, host, max_reviews_per_product, debug)
            products[asin] = product_data
            total_reviews += len(product_data.get("reviews", []))
            
            if i < len(all_asins) - 1:
                time.sleep(1.5)  # 避免被反爬
        except Exception as e:
            if debug:
                print(f"  ⚠️ 获取 {asin} 失败: {e}")
            products[asin] = {
                "info": _empty_product_info(asin, host),
                "reviews": []
            }
    
    if debug:
        print(f"  ✅ 评论采集完成: {len(all_asins)} 个产品, {total_reviews} 条评论")
    
    return {
        "products": products,
        "total_reviews": total_reviews,
        "fetch_time": datetime.now().isoformat(),
        "primary_asin": primary_asin,
        "competitor_asins": competitor_asins or [],
    }


def _fetch_single_product(asin: str, host: str, max_reviews: int, 
                          debug: bool = False) -> Dict:
    """获取单个产品的信息 + 评论"""
    
    # 并行获取产品信息和评论
    product_info = _scrape_product_info(asin, host, debug)
    
    # 爬取评论
    reviews = _scrape_reviews(asin, host, max_reviews, debug)
    
    return {
        "info": product_info,
        "reviews": reviews,
        "review_count": len(reviews),
    }


def _scrape_product_info(asin: str, host: str, debug: bool = False) -> Dict:
    """爬取产品页面信息"""
    
    info = _empty_product_info(asin, host)
    
    try:
        url = f"https://www.{host}/dp/{asin}"
        html = safe_get(url, timeout=15)
        
        if not html:
            return info
        
        # 提取标题
        title_match = re.search(r'<span[^>]*id="productTitle"[^>]*>(.*?)</span>', html, re.DOTALL)
        if title_match:
            info["title"] = clean_text(title_match.group(1))
        
        # 提取价格 - 多种模式
        price_patterns = [
            r'<span class="a-price-whole">([\d,]+)<span class="a-price-decimal">([\d]+)',
            r'<span[^>]*class="a-price[^"]*".*?>\s*\$?([\d.]+)',
            r'"price(?:Amount)?"\s*:\s*"?\$?([\d.]+)"?',
            r'<span class="a-price-whole">([\d,]+)',
        ]
        for pat in price_patterns:
            pm = re.search(pat, html, re.DOTALL)
            if pm:
                price = pm.group(1).replace(',', '')
                if pm.lastindex and pm.lastindex >= 2:
                    price += f".{pm.group(2)}"
                info["price"] = f"${price}"
                break
        
        # 提取评分
        rating_match = re.search(r'<span[^>]*data-hook="rating-out-of-text"[^>]*>([\d.]+) out of 5', html)
        if not rating_match:
            rating_match = re.search(r'"ratingValue"\s*:\s*"?([\d.]+)"?', html)
        if not rating_match:
            rating_match = re.search(r'([\d.]+) out of 5', html)
        if rating_match:
            try:
                info["rating"] = float(rating_match.group(1))
            except ValueError:
                pass
        
        # 提取评论总数
        review_match = re.search(r'([\d,]+)\s*(?:global )?(?:ratings|reviews)', html, re.IGNORECASE)
        if not review_match:
            review_match = re.search(r'"reviewCount"\s*:\s*"?(\d+)"?', html)
        if review_match:
            try:
                info["total_reviews"] = int(review_match.group(1).replace(',', ''))
            except ValueError:
                pass
        
        # 提取排名
        rank_match = re.search(r'Best Sellers Rank[^<]*<span[^>]*>(.*?)</span>', html, re.DOTALL)
        if rank_match:
            info["rank"] = clean_text(rank_match.group(1))
        
        # 提取品牌
        brand_match = re.search(r'"brand"\s*:\s*"([^"]+)"', html)
        if not brand_match:
            brand_match = re.search(r'Brand[^<]*<span[^>]*>(.*?)</span>', html, re.IGNORECASE)
        if brand_match:
            info["brand"] = brand_match.group(1).strip()
        
        # 提取图片
        img_match = re.search(r'"hiRes"\s*:\s*"([^"]+)"', html)
        if not img_match:
            img_match = re.search(r'<img[^>]*id="landingImage"[^>]*src="([^"]+)"', html)
        if img_match:
            info["image_url"] = img_match.group(1)
        
        # 提取五点描述
        bullets = re.findall(r'<span class="a-list-item">\s*(.*?)\s*</span>', html)
        if bullets:
            info["bullet_points"] = [clean_text(b) for b in bullets[:10] 
                                     if len(clean_text(b)) > 10]
        
        if debug:
            print(f"    产品: {info['title'][:60]}...")
            print(f"    价格: {info['price']} | 评分: {info['rating']}★ | 评论: {format_number(info['total_reviews'])}")
    
    except Exception as e:
        if debug:
            print(f"    ⚠️ 产品信息爬取异常: {e}")
    
    return info


def _scrape_reviews(asin: str, host: str, max_reviews: int = 200, debug: bool = False) -> List[Dict]:
    """爬取产品评论"""
    
    reviews = []
    page = 1
    session = create_session()
    
    while len(reviews) < max_reviews:
        url = f"https://www.{host}/product-reviews/{asin}/ref=cm_cr_arp_d_paging_btm_next_{page}?pageNumber={page}&sortBy=recent"
        
        html = safe_get(url, session=session, timeout=15)
        
        if not html:
            break
        
        # 解析当前页评论
        page_reviews = _parse_reviews_page(html)
        
        if not page_reviews:
            break
        
        reviews.extend(page_reviews)
        
        if debug and page == 1:
            print(f"    第1页获取 {len(page_reviews)} 条评论")
        
        # 检查是否有下一页
        if "Next page" not in html and "下一" not in html and 'data-hook="cm_cr-pagination_bar-next-page"' not in html:
            break
        
        page += 1
        time.sleep(1)  # 礼貌延迟
        
        if page > 20:  # 最多20页
            break
    
    return reviews[:max_reviews]


def _parse_reviews_page(html: str) -> List[Dict]:
    """解析评论页面"""
    reviews = []
    
    # 查找所有评论卡片
    review_cards = re.split(r'<div[^>]*data-hook="review"[^>]*>', html)
    
    # 如果没有 data-hook，尝试其他方式
    if len(review_cards) < 2:
        review_cards = re.split(r'<div[^>]*id="customer_review[^"]*"', html)
    
    for card in review_cards[1:]:  # 跳过第一个（分割前的内容）
        try:
            review = _parse_single_review(card)
            if review and review.get("body"):
                reviews.append(review)
        except Exception:
            continue
    
    return reviews


def _parse_single_review(card_html: str) -> Optional[Dict]:
    """解析单条评论"""
    
    review = {
        "id": "",
        "rating": 0,
        "title": "",
        "body": "",
        "author": "Anonymous",
        "date": "",
        "verified_purchase": False,
        "helpful_votes": 0,
    }
    
    # 提取评分
    rating_match = re.search(r'([\d.]+) out of 5', card_html)
    if not rating_match:
        rating_match = re.search(r'<span[^>]*class="a-icon-alt"[^>]*>([\d.]+) out of 5', card_html)
    if rating_match:
        try:
            review["rating"] = float(rating_match.group(1))
        except ValueError:
            review["rating"] = 0
    
    # 提取标题
    title_match = re.search(r'<a[^>]*data-hook="review-title"[^>]*>(.*?)</a>', card_html, re.DOTALL)
    if not title_match:
        title_match = re.search(r'<span[^>]*data-hook="review-title"[^>]*>.*?<span[^>]*>(.*?)</span>', card_html, re.DOTALL)
    if title_match:
        review["title"] = clean_text(title_match.group(1))
    
    # 提取正文
    body_match = re.search(r'<span[^>]*data-hook="review-body"[^>]*>(.*?)</span>', card_html, re.DOTALL)
    if not body_match:
        body_match = re.search(r'<div[^>]*data-hook="review-collapsed"[^>]*>(.*?)</div>', card_html, re.DOTALL)
    if body_match:
        review["body"] = clean_text(body_match.group(1))
    
    # 提取作者
    author_match = re.search(r'<span[^>]*class="a-profile-name"[^>]*>(.*?)</span>', card_html)
    if author_match:
        review["author"] = clean_text(author_match.group(1))
    
    # 提取日期
    date_match = re.search(r'<span[^>]*data-hook="review-date"[^>]*>(.*?)</span>', card_html)
    if date_match:
        review["date"] = clean_text(date_match.group(1))
    
    # 提取有用票数
    helpful_match = re.search(r'([\d,]+) people found this helpful', card_html)
    if not helpful_match:
        helpful_match = re.search(r'(\d+) people found this helpful', card_html)
    if helpful_match:
        review["helpful_votes"] = int(helpful_match.group(1).replace(',', ''))
    
    # 验证购买
    review["verified_purchase"] = "Verified Purchase" in card_html or "verified" in card_html.lower()
    
    # 提取 review ID
    id_match = re.search(r'id="([^"]*customer_review[^"]*)"', card_html)
    if id_match:
        review["id"] = id_match.group(1)
    
    return review


def _empty_product_info(asin: str, host: str) -> Dict:
    """空产品信息模板"""
    return {
        "asin": asin,
        "title": f"Product {asin}",
        "price": "N/A",
        "rating": 0,
        "total_reviews": 0,
        "image_url": f"https://ws-na.amazon-adsystem.com/widgets/q?_encoding=UTF8&ASIN={asin}&Format=_SL250_",
        "url": f"https://www.{host}/dp/{asin}",
        "rank": "N/A",
        "brand": "N/A",
        "bullet_points": [],
    }


if __name__ == "__main__":
    # 测试
    result = fetch_multi_product_reviews(
        primary_asin="B0CHX1W1XY",
        competitor_asins=["B09JQL3LJM", "B09JSD1H4S"],
        max_reviews_per_product=20,
        debug=True,
    )
    
    for asin, data in result["products"].items():
        print(f"\n{asin}: {data['info']['title'][:50]}")
        print(f"  评论: {len(data['reviews'])} 条")
