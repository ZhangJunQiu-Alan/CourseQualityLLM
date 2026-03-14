"""
edX 爬虫（Algolia Search API）
edX 前端使用 Algolia 作为课程搜索后端，凭证可从前端 JS 中提取。
直接调用 Algolia API，无需登录，速度快、结构化强。

Index: rv_product_summary  App: IGSYV1Z1XI
"""
import re
import time
import random
from tqdm import tqdm
from scrapers.base import BaseScraper
from utils.storage import is_already_scraped, upsert_course, save_json
from utils.anti_detect import random_delay
from config import MAX_COURSES

ALGOLIA_APP_ID  = "IGSYV1Z1XI"
ALGOLIA_API_KEY = "6658746ce52e30dacfdd8ba5f8e8cf18"   # public search-only key
ALGOLIA_URL     = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/rv_product_summary/query"

RETRIEVE_ATTRS = [
    "objectID", "productName", "productType", "productSlug",
    "shortDescription", "fullDescription", "productOverview",
    "level", "language", "weeksToComplete", "weeksToCompleteMin", "weeksToCompleteMax",
    "minHoursEffortPerWeek", "maxHoursEffortPerWeek",
    "partner", "partnerName", "partnerKeys",
    "staff", "skills", "tags",
    "recentEnrollmentCount", "availability", "externalUrl",
]


class EdxScraper(BaseScraper):
    PLATFORM = "edx"

    def run(self) -> int:
        self.log("开始通过 Algolia API 爬取 edX 课程...")

        saved      = 0
        hits_per   = 50
        page_num   = 0
        total_done = 0

        # 先查一次获取总数
        first = self._query_algolia(page=0, hits_per_page=1)
        nb_pages  = min(first.get("nbPages", 1), MAX_COURSES["edx"] // hits_per + 1)
        nb_hits   = first.get("nbHits", 0)
        self.log(f"共 {nb_hits} 门课程，预计爬取最多 {MAX_COURSES['edx']} 门")

        with tqdm(total=min(nb_hits, MAX_COURSES["edx"]), desc="edX") as pbar:
            while total_done < MAX_COURSES["edx"] and page_num < nb_pages:
                data = self._query_algolia(page=page_num, hits_per_page=hits_per)
                hits = data.get("hits", [])
                if not hits:
                    break

                for item in hits:
                    if total_done >= MAX_COURSES["edx"]:
                        break
                    cid = item.get("objectID", "")
                    if not cid or is_already_scraped(self.PLATFORM, cid):
                        pbar.update(1)
                        total_done += 1
                        continue

                    parsed = self._parse(item)
                    if parsed:
                        upsert_course(self.PLATFORM, parsed)
                        save_json(self.PLATFORM, parsed)
                        saved += 1

                    pbar.update(1)
                    total_done += 1

                page_num += 1
                random_delay()   # 礼貌性限速

        self.log(f"完成，新增 {saved} 门课程")
        return saved

    def _query_algolia(self, page: int, hits_per_page: int) -> dict:
        """调用 Algolia Search API（POST JSON）"""
        from utils.anti_detect import build_headers, get_proxy
        from config import TIMEOUT

        r = self.session.post(
            ALGOLIA_URL,
            params={
                "x-algolia-application-id": ALGOLIA_APP_ID,
                "x-algolia-api-key":        ALGOLIA_API_KEY,
            },
            json={
                "query":             "",
                "filters":           "productType:Course",
                "hitsPerPage":       hits_per_page,
                "page":              page,
                "attributesToRetrieve": RETRIEVE_ATTRS,
            },
            headers=build_headers(),
            proxies=get_proxy(),
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    def _parse(self, item: dict) -> dict | None:
        try:
            # 讲师
            instructors = []
            for staff in item.get("staff", []) or []:
                if isinstance(staff, dict):
                    instructors.append({
                        "name":        staff.get("name", ""),
                        "title":       "",
                        "institution": item.get("partnerName", ""),
                    })
                elif isinstance(staff, str):
                    instructors.append({"name": staff, "title": "", "institution": ""})

            # 学时
            weeks = item.get("weeksToComplete") or item.get("weeksToCompleteMin")
            mn    = item.get("minHoursEffortPerWeek")
            mx    = item.get("maxHoursEffortPerWeek")
            duration = f"{weeks} 周" if weeks else ""
            if mn and mx:
                duration += f"，每周 {mn}-{mx} 小时"

            # 学习目标（从 fullDescription 中暂无结构化字段）
            description = _strip_html(
                item.get("fullDescription") or item.get("shortDescription", "")
            )

            return {
                "course_id":      item.get("objectID", ""),
                "platform":       self.PLATFORM,
                "title":          item.get("productName", ""),
                "description":    description,
                "learning_goals": item.get("skills", []),
                "prerequisites":  "",
                "difficulty":     item.get("level", ""),
                "duration":       duration,
                "language":       _to_str(item.get("language", "")),
                "url":            _to_str(item.get("externalUrl", f"https://www.edx.org/learn/{item.get('productSlug','')}")),
                "instructors":    instructors,
                "institutions":   [item.get("partnerName", "")],
                "rating": {
                    "avg":             None,
                    "count":           None,
                    "enrollment":      item.get("recentEnrollmentCount"),
                    "completion_rate": None,
                },
                "syllabus": [],
                "reviews":  [],
            }
        except Exception as e:
            self.log(f"解析失败 {item.get('objectID','')}: {e}")
            return None


def _strip_html(text: str) -> str:
    """简单去除 HTML 标签"""
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _to_str(val) -> str:
    """确保值是字符串，list 则取第一个元素"""
    if isinstance(val, list):
        return val[0] if val else ""
    return str(val) if val is not None else ""
