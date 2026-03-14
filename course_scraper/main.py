"""
课程数据爬虫入口

用法：
  python main.py                     # 爬取所有平台
  python main.py --platform coursera # 只爬 Coursera
  python main.py --platform edx
  python main.py --platform mooc_cn
  python main.py --stats             # 查看当前爬取统计
"""
import argparse
import sys
from utils.storage import init_db, get_stats
from scrapers.coursera import CourseraScraper
from scrapers.edx import EdxScraper
from scrapers.mooc_china import MoocChinaScraper

SCRAPERS = {
    "coursera": CourseraScraper,
    "edx":      EdxScraper,
    "mooc_cn":  MoocChinaScraper,
}


def print_stats() -> None:
    stats = get_stats()
    total = sum(stats.values())
    print("\n── 当前爬取统计 ────────────────────")
    for platform, count in stats.items():
        print(f"  {platform:<12} : {count:>5} 门")
    print(f"  {'合计':<12} : {total:>5} 门")
    print("────────────────────────────────────\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="课程质量数据爬虫")
    parser.add_argument("--platform", choices=list(SCRAPERS.keys()), help="指定爬取平台")
    parser.add_argument("--stats", action="store_true", help="显示统计信息后退出")
    args = parser.parse_args()

    # 初始化数据库
    init_db()
    print("数据库初始化完成")

    if args.stats:
        print_stats()
        sys.exit(0)

    targets = [args.platform] if args.platform else list(SCRAPERS.keys())

    total_saved = 0
    for name in targets:
        print(f"\n{'='*40}")
        print(f"  平台: {name}")
        print(f"{'='*40}")
        scraper = SCRAPERS[name]()
        saved = scraper.run()
        total_saved += saved

    print(f"\n全部完成，本次共新增 {total_saved} 门课程")
    print_stats()


if __name__ == "__main__":
    main()
