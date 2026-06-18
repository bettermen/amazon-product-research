#!/usr/bin/env python3
"""
共享工具函数
"""

import re
import json
import time
import hashlib
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any


# ========== 文本处理 ==========

def clean_text(text: str) -> str:
    """清洗文本"""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def truncate_text(text: str, max_len: int = 200) -> str:
    """截断文本"""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def extract_english(text: str) -> str:
    """从混合文本中提取英文部分"""
    eng = re.findall(r'[a-zA-Z][a-zA-Z\s\-.\'"]+', text)
    return ' '.join(eng).strip()


def extract_chinese(text: str) -> str:
    """从混合文本中提取中文部分"""
    cn = re.findall(r'[\u4e00-\u9fff]+', text)
    return ''.join(cn)


# ========== 网络请求 ==========

def create_session(headers: Optional[Dict] = None) -> requests.Session:
    """创建带重试的 Session"""
    session = requests.Session()
    
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    if headers:
        default_headers.update(headers)
    
    session.headers.update(default_headers)
    return session


def safe_get(url: str, session: Optional[requests.Session] = None, 
             max_retries: int = 3, timeout: int = 15, debug: bool = False) -> Optional[str]:
    """安全的 GET 请求，带重试"""
    sess = session or create_session()
    
    for attempt in range(max_retries):
        try:
            resp = sess.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 503:
                if debug:
                    print(f"  ⚠️ 503 Service Unavailable, 重试 {attempt+1}/{max_retries}")
                time.sleep(2 ** attempt)
            elif resp.status_code == 429:
                if debug:
                    print(f"  ⚠️ 429 Rate Limited, 等待后重试...")
                time.sleep(5)
            else:
                if debug:
                    print(f"  ⚠️ HTTP {resp.status_code}")
                return None
        except requests.Timeout:
            if debug:
                print(f"  ⚠️ 请求超时, 重试 {attempt+1}/{max_retries}")
            time.sleep(1)
        except Exception as e:
            if debug:
                print(f"  ⚠️ 请求异常: {e}")
            return None
    
    return None


# ========== 数据统计 ==========

def compute_sentiment_distribution(tagged_reviews: List[Dict]) -> Dict:
    """计算情感分布"""
    positive = negative = neutral = 0
    for item in tagged_reviews:
        s = item["tags"].get("sentiment", "neutral")
        if s == "positive":
            positive += 1
        elif s == "negative":
            negative += 1
        else:
            neutral += 1
    
    total = max(positive + negative + neutral, 1)
    return {
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "positive_pct": round(positive / total * 100, 1),
        "negative_pct": round(negative / total * 100, 1),
        "neutral_pct": round(neutral / total * 100, 1),
    }


def compute_rating_distribution(reviews: List[Dict]) -> Dict:
    """计算评分分布"""
    dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for r in reviews:
        rating = int(r.get("rating", 0))
        if rating in dist:
            dist[rating] += 1
    
    total = max(sum(dist.values()), 1)
    return {
        "distribution": dist,
        "avg_rating": round(sum(k * v for k, v in dist.items()) / total, 2),
        "total": total,
    }


def compute_word_frequency(texts: List[str], top_n: int = 50, 
                           min_len: int = 3, lang: str = "en") -> List[tuple]:
    """
    词频统计
    
    Args:
        texts: 文本列表
        top_n: 返回前N个
        min_len: 最小词长
        lang: 语言 (en/cn)
    
    Returns:
        [(word, count), ...]
    """
    from collections import Counter
    
    all_words = []
    
    for text in texts:
        if lang == "cn":
            # 简单的中文分词（按字符 + 双字词组）
            chars = list(text)
            # 单字
            for c in chars:
                if '\u4e00' <= c <= '\u9fff':
                    all_words.append(c)
            # 双字词组
            for i in range(len(chars) - 1):
                if all('\u4e00' <= c <= '\u9fff' for c in chars[i:i+2]):
                    all_words.append(chars[i] + chars[i+1])
        else:
            words = re.findall(r'[a-zA-Z]+', text.lower())
            all_words.extend([w for w in words if len(w) >= min_len])
    
    counter = Counter(all_words)
    
    # 过滤常见停用词
    en_stopwords = {'the', 'and', 'for', 'this', 'that', 'with', 'was', 'are', 'but',
                    'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'has',
                    'have', 'from', 'they', 'its', 'his', 'been', 'very', 'just',
                    'too', 'out', 'will', 'some', 'what'}
    
    cn_stopwords = {'的', '了', '是', '我', '不', '在', '人', '有', '这', '个',
                    '也', '就', '都', '要', '会', '可', '说', '和', '很', '到'}
    
    stopwords = en_stopwords if lang == "en" else cn_stopwords
    
    filtered = [(w, c) for w, c in counter.most_common(top_n * 2)
                if w.lower() not in stopwords][:top_n]
    
    return filtered


# ========== JSON / 文件处理 ==========

def safe_json_parse(text: str) -> Optional[Dict]:
    """安全解析 JSON（多种容错策略）"""
    strategies = [
        lambda t: json.loads(t.strip()),
        lambda t: json.loads(re.search(r'\{[\s\S]*\}', t).group()),
        lambda t: json.loads(re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', t).group(1)),
    ]
    
    for strategy in strategies:
        try:
            result = strategy(text)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, AttributeError, KeyError):
            continue
    
    return None


def generate_cache_key(*args) -> str:
    """生成缓存键"""
    raw = '|'.join(str(a) for a in args)
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def format_number(n: int) -> str:
    """格式化数字"""
    if n >= 1000000:
        return f"{n/1000000:.1f}M"
    elif n >= 1000:
        return f"{n/1000:.1f}K"
    return str(n)


def format_price(price_str: str) -> str:
    """格式化价格"""
    if not price_str or price_str == "N/A":
        return price_str
    
    # 提取数字
    nums = re.findall(r'[\d.]+', price_str)
    if not nums:
        return price_str
    
    try:
        price = float(nums[0])
        if price >= 100:
            return f"${price:,.0f}"
        else:
            return f"${price:.2f}"
    except ValueError:
        return price_str


# ========== 市场配置 ==========

MARKET_CONFIG = {
    "US": {"host": "amazon.com", "currency": "$", "lang": "en-US"},
    "UK": {"host": "amazon.co.uk", "currency": "£", "lang": "en-GB"},
    "DE": {"host": "amazon.de", "currency": "€", "lang": "de-DE"},
    "JP": {"host": "amazon.co.jp", "currency": "¥", "lang": "ja-JP"},
    "FR": {"host": "amazon.fr", "currency": "€", "lang": "fr-FR"},
    "CA": {"host": "amazon.ca", "currency": "CA$", "lang": "en-CA"},
    "IT": {"host": "amazon.it", "currency": "€", "lang": "it-IT"},
    "ES": {"host": "amazon.es", "currency": "€", "lang": "es-ES"},
}


def get_market_host(market: str) -> str:
    return MARKET_CONFIG.get(market.upper(), MARKET_CONFIG["US"])["host"]


def get_market_currency(market: str) -> str:
    return MARKET_CONFIG.get(market.upper(), MARKET_CONFIG["US"])["currency"]
