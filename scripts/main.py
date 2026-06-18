#!/usr/bin/env python3
"""
Amazon 产品深度研究 - 一站式入口
一句话输入 → 全链路自动分析 → 输出完整 HTML 报告

用法:
    python main.py "bluetooth earbuds noise cancelling"
    python main.py B0CHX1W1XY
    python main.py "smart watch for kids" --output report.html
"""

import os
import sys
import io
import argparse
from datetime import datetime

# 修复 Windows GBK 编码问题
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加脚本目录到路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from parse_input import parse_user_input
from fetch_multi import fetch_multi_product_reviews
from keyword_research import research_keywords
from ai_analysis import ai_tag_reviews, analyze_negative_reviews, cluster_voc
from competitor import analyze_competitors
from opportunity import analyze_opportunities
from generate_report import generate_full_report


def main():
    parser = argparse.ArgumentParser(
        description="Amazon 产品深度研究 - 一句话全链路分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py "bluetooth earbuds"
  python main.py B0CHX1W1XY
  python main.py "kitchen knife set" --api-key sk-xxx
  python main.py "yoga mat" --market UK --no-ai
        """
    )
    
    parser.add_argument("input", type=str, help="产品名/ASIN/一句话描述")
    parser.add_argument("--api-key", type=str, default=os.environ.get("OPENAI_API_KEY"),
                        help="LLM API Key (OpenAI/DeepSeek 兼容)")
    parser.add_argument("--api-base", type=str, 
                        default=os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1"),
                        help="LLM API Base URL")
    parser.add_argument("--model", type=str, default="gpt-4o-mini",
                        help="LLM Model (默认: gpt-4o-mini)")
    parser.add_argument("--market", type=str, default="US",
                        help="Amazon 市场 (US/UK/DE/JP/FR/CA/IT/ES)")
    parser.add_argument("--output", type=str, default=None,
                        help="输出 HTML 路径 (默认: amazon_report_<时间戳>.html)")
    parser.add_argument("--max-reviews", type=int, default=200,
                        help="每个产品最大评论数 (默认: 200)")
    parser.add_argument("--no-ai", action="store_true",
                        help="跳过 AI 深度分析（仅用规则统计）")
    parser.add_argument("--debug", action="store_true",
                        help="调试模式")
    
    args = parser.parse_args()
    
    # === 阶段1: 智能输入解析 ===
    print("\n" + "=" * 60)
    print("  🛍️  Amazon 产品深度研究 Skill")
    print("  一句话输入 · 全链路分析")
    print("=" * 60)
    
    print(f"\n📥 输入: {args.input}")
    print(f"📊 市场: {args.market}")
    if not args.no_ai:
        print(f"🤖 AI 模型: {args.model}")
    
    print("\n--- 阶段1: 输入解析 ---")
    parsed = parse_user_input(args.input, market=args.market, debug=args.debug)
    
    if not parsed.get("primary_asin"):
        print("\n❌ 未能识别产品，请检查输入（提供有效 ASIN 或产品名）")
        sys.exit(1)
    
    print(f"\n✅ 识别到产品: {parsed['products'][0]['title'][:60]}...")
    print(f"   ASIN: {parsed['primary_asin']}")
    print(f"   评分: {parsed['products'][0].get('rating', 'N/A')}")
    
    # === 阶段2: 评论采集 ===
    print("\n--- 阶段2: 评论采集 ---")
    
    # 先做一次竞品搜索获取竞品 ASIN
    temp_competitors = []
    if parsed["input_type"] != "asin":
        try:
            from competitor import _search_competitors
            from utils import get_market_host
            host = get_market_host(args.market)
            temp_competitors = _search_competitors(
                parsed.get("search_query", args.input),
                parsed["primary_asin"],
                host, 5, args.debug
            )
        except Exception as e:
            if args.debug:
                print(f"  ⚠️ 预搜索竞品失败: {e}")
    
    competitor_asins = [c["asin"] for c in temp_competitors[:4]]
    
    multi_reviews = fetch_multi_product_reviews(
        primary_asin=parsed["primary_asin"],
        competitor_asins=competitor_asins,
        market=args.market,
        max_reviews_per_product=args.max_reviews,
        debug=args.debug,
    )
    
    # 收集所有评论
    all_reviews = []
    for asin, data in multi_reviews["products"].items():
        all_reviews.extend(data.get("reviews", []))
    
    print(f"\n✅ 共采集 {len(all_reviews)} 条评论 ({len(multi_reviews['products'])} 个产品)")
    
    # === 阶段3: AI 深度打标 ===
    print("\n--- 阶段3: AI 深度打标 ---")
    
    if not args.no_ai and args.api_key:
        tagged = ai_tag_reviews(
            reviews=all_reviews,
            api_key=args.api_key,
            api_base=args.api_base,
            model=args.model,
            debug=args.debug,
        )
    else:
        if args.no_ai:
            print("  ⚠️ --no-ai 模式，跳过 AI 打标，使用规则统计")
        else:
            print("  ⚠️ 未提供 API Key，使用规则统计 (设置 --api-key 或 OPENAI_API_KEY 启用 AI)")

        # 简单规则打标
        tagged = []
        for r in all_reviews:
            rating = r.get("rating", 0)
            sentiment = "positive" if rating >= 4 else "negative" if rating <= 2 else "neutral"
            tagged.append({
                "review": {k: v for k, v in r.items() if not k.startswith("_")},
                "tags": {
                    "sentiment": sentiment,
                    "pain_points": [],
                    "selling_points": [],
                    "use_cases": [],
                    "improvement_suggestions": [],
                    "summary": r.get("title", "")[:20],
                }
            })
        print(f"  ✅ 规则打标完成 ({len(tagged)} 条)")
    
    # === 阶段4: 关键词研究 ===
    print("\n--- 阶段4: 关键词研究 ---")
    
    primary_title = parsed["products"][0].get("title", "")
    search_query = parsed.get("search_query", args.input)
    
    keyword_data = research_keywords(
        reviews=all_reviews,
        product_title=primary_title,
        search_query=search_query,
        market=args.market,
        debug=args.debug,
    )
    
    # === 阶段5: 差评深度分析 & VOC聚类 ===
    print("\n--- 阶段5: 差评分析 & VOC 聚类 ---")
    
    if not args.no_ai and args.api_key:
        negative_analysis = analyze_negative_reviews(
            tagged_reviews=tagged,
            api_key=args.api_key,
            api_base=args.api_base,
            model=args.model,
            debug=args.debug,
        )
        
        voc_data = cluster_voc(
            tagged_reviews=tagged,
            api_key=args.api_key,
            api_base=args.api_base,
            model=args.model,
            debug=args.debug,
        )
    else:
        from collections import Counter
        pain_counter = Counter()
        for item in tagged:
            pain_counter.update(item["tags"].get("pain_points", []) if isinstance(item["tags"].get("pain_points"), list) else [])
        
        negative_analysis = {
            "total_negative": sum(1 for item in tagged if item["tags"].get("sentiment") == "negative"),
            "root_causes": [{"cause": p, "frequency": c, "severity": "major"} for p, c in pain_counter.most_common(10)],
            "severity_breakdown": {"critical": 0, "major": 0, "minor": 0},
            "improvement_priority": [],
            "sentiment_trend": "stable",
        }
        
        voc_data = {
            "clusters": [],
            "customer_expectations": [],
            "unmet_needs": [],
            "delighters": [],
        }
        print("  ✅ 规则统计完成")
    
    # === 阶段6: 竞品分析 ===
    print("\n--- 阶段6: 竞品分析 ---")
    
    competitor_data = analyze_competitors(
        primary_product=parsed["products"][0],
        search_query=search_query,
        market=args.market,
        max_competitors=5,
        debug=args.debug,
    )
    
    # === 阶段7: 新品机会分析 ===
    print("\n--- 阶段7: 新品机会分析 ---")
    
    opportunity_data = analyze_opportunities(
        primary_product=parsed["products"][0],
        tagged_reviews=tagged,
        keyword_data=keyword_data,
        competitor_data=competitor_data,
        voc_data=voc_data,
        api_key=args.api_key if not args.no_ai else None,
        api_base=args.api_base,
        model=args.model,
        debug=args.debug,
    )
    
    # === 阶段8: 生成报告 ===
    print("\n--- 阶段8: 生成 HTML 报告 ---")
    
    if not args.output:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"amazon_report_{ts}.html"
    
    # 组装产品数据
    product_data = {
        "primary_product": parsed["products"][0],
        "products": multi_reviews.get("products", {}),
        "primary_asin": parsed["primary_asin"],
        "search_query": search_query,
        "market": args.market,
    }
    
    output_path = generate_full_report(
        product_data=product_data,
        tagged_reviews=tagged,
        keyword_data=keyword_data,
        voc_data=voc_data,
        competitor_data=competitor_data,
        opportunity_data=opportunity_data,
        negative_analysis=negative_analysis,
        output_path=args.output,
    )
    
    # === 完成 ===
    print("\n" + "=" * 60)
    print("  🎉 分析完成！")
    print("=" * 60)
    print(f"\n📊 报告: {os.path.abspath(output_path)}")
    print(f"📈 产品: {parsed['products'][0]['title'][:60]}")
    print(f"💬 评论: {len(tagged)} 条")
    print(f"🔑 关键词: {len(keyword_data.get('high_frequency_keywords', []))} 个")
    print(f"🏪 竞品: {len(competitor_data.get('competitors', []))} 个")
    print(f"💡 机会评分: {opportunity_data.get('opportunity_scores', {}).get('overall_score', '-')}/10")
    print(f"\n🌐 在浏览器中打开报告查看完整分析")
    
    return output_path


if __name__ == "__main__":
    main()
