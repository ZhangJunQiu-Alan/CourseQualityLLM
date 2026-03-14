"""
Coursera 爬虫
使用 Coursera 公开 API：
  - /api/courses.v1          课程列表
  - /api/courses.v1/{id}     课程详情（大纲、讲师、学习目标）
  - /api/reviews.v1          学生评价

注：Coursera API 无需 token 即可访问基础字段
"""
from tqdm import tqdm
from scrapers.base import BaseScraper
from utils.anti_detect import random_delay
from utils.storage import is_already_scraped, upsert_course, save_json
from config import COURSERA_API_BASE, MAX_COURSES


class CourseraScraper(BaseScraper):
    PLATFORM = "coursera"

    # 课程列表：每页最多 100 条
    _LIST_FIELDS = ",".join([
        "name", "slug", "description", "primaryLanguages",
        "workload", "level", "photoUrl",
        "instructorIds", "partnerIds",
    ])
    _LIST_INCLUDES = "instructorIds,partnerIds"

    # 课程详情额外字段
    _DETAIL_FIELDS = ",".join([
        "name", "slug", "description", "primaryLanguages",
        "workload", "level", "promoPhoto", "instructorIds",
        "partnerIds", "domainTypes", "certificates",
    ])

    def run(self) -> int:
        """入口：爬取所有课程，返回成功爬取数"""
        self.log("开始爬取 Coursera 课程列表...")
        course_ids = self._fetch_all_ids()
        self.log(f"共获取 {len(course_ids)} 个课程 ID，开始爬取详情...")

        saved = 0
        for cid in tqdm(course_ids, desc="Coursera"):
            if is_already_scraped(self.PLATFORM, cid):
                continue
            random_delay(extra_factor=0.25)   # 官方 API 延迟 0.5-1.5s 即可
            data = self._fetch_detail(cid)
            if data:
                upsert_course(self.PLATFORM, data)
                save_json(self.PLATFORM, data)
                saved += 1

        self.log(f"完成，新增 {saved} 门课程")
        return saved

    # ── 私有方法 ──────────────────────────────────────────────────────────────

    def _fetch_all_ids(self) -> list[str]:
        """分页获取所有课程 ID"""
        ids = []
        start = 0
        limit = 100

        while len(ids) < MAX_COURSES["coursera"]:
            resp = self.get(
                f"{COURSERA_API_BASE}/courses.v1",
                params={
                    "fields": self._LIST_FIELDS,
                    "includes": self._LIST_INCLUDES,
                    "limit": limit,
                    "start": start,
                },
            )
            body = resp.json()
            elements = body.get("elements", [])
            if not elements:
                break

            ids.extend(e["id"] for e in elements)
            start += limit

            # 没有更多分页
            if not body.get("paging", {}).get("next"):
                break

        return ids[:MAX_COURSES["coursera"]]

    def _fetch_detail(self, course_id: str) -> dict | None:
        """获取单门课程的完整信息"""
        try:
            # ① 基本信息
            resp = self.get(
                f"{COURSERA_API_BASE}/courses.v1/{course_id}",
                params={"fields": self._DETAIL_FIELDS, "includes": "instructorIds,partnerIds"},
                delay=False,
            )
            body   = resp.json()
            raw    = body.get("elements", [{}])[0]
            linked = body.get("linked", {})

            instructors = self._parse_instructors(
                raw.get("instructorIds", []),
                linked.get("instructors.v1", [])
            )
            partners = self._parse_partners(
                raw.get("partnerIds", []),
                linked.get("partners.v1", [])
            )

            # ② 评分（reviewsummaries API）
            rating = self._fetch_rating(course_id)

            # ③ 大纲（onDemand modules API）
            syllabus = self._fetch_syllabus(course_id)

            # ④ 评论（部分课程可访问）
            reviews = self._fetch_reviews(course_id)

            return {
                "course_id":     course_id,
                "platform":      self.PLATFORM,
                "title":         raw.get("name", ""),
                "slug":          raw.get("slug", ""),
                "description":   raw.get("description", ""),
                "learning_goals": [],           # Coursera API 不直接暴露
                "prerequisites": "",
                "difficulty":    raw.get("level", ""),
                "duration":      raw.get("workload", ""),
                "language":      ", ".join(raw.get("primaryLanguages", [])),
                "url":           f"https://www.coursera.org/learn/{raw.get('slug', '')}",
                "instructors":   instructors,
                "institutions":  partners,
                "rating":        rating,
                "syllabus":      syllabus,
                "reviews":       reviews,
            }
        except Exception as e:
            self.log(f"详情获取失败 {course_id}: {e}")
            return None

    def _parse_instructors(self, ids: list, linked: list) -> list[dict]:
        linked_map = {i["id"]: i for i in linked}
        result = []
        for iid in ids:
            inst = linked_map.get(iid, {})
            result.append({
                "name":        inst.get("fullName", ""),
                "title":       inst.get("title", ""),
                "institution": inst.get("department", ""),
            })
        return result

    def _parse_partners(self, ids: list, linked: list) -> list[str]:
        linked_map = {p["id"]: p for p in linked}
        return [linked_map.get(pid, {}).get("name", "") for pid in ids]

    def _fetch_rating(self, course_id: str) -> dict:
        try:
            resp = self.get(
                f"{COURSERA_API_BASE}/reviewsummaries.v1/{course_id}",
                params={"fields": "averageFiveStarRating,totalRatingsCount"},
                delay=False,
            )
            el = resp.json().get("elements", [{}])[0]
            return {
                "avg":   el.get("averageFiveStarRating"),
                "count": el.get("totalRatingsCount"),
                "enrollment": None,
                "completion_rate": None,
            }
        except Exception:
            return {}

    def _fetch_syllabus(self, course_id: str) -> list[dict]:
        """获取课程周次/模块大纲"""
        try:
            resp = self.get(
                f"{COURSERA_API_BASE}/onDemandCourseMaterials.v2/{course_id}",
                params={"fields": "modules,lessons", "includes": "modules,lessons"},
                delay=False,
            )
            body    = resp.json()
            modules = body.get("linked", {}).get("onDemandCourseMaterials.v2.modules", [])
            result  = []
            for i, mod in enumerate(modules, 1):
                result.append({
                    "week":        i,
                    "title":       mod.get("name", ""),
                    "description": mod.get("description", ""),
                    "duration":    "",
                })
            return result
        except Exception:
            return []

    def _fetch_reviews(self, course_id: str) -> list[dict]:
        """获取前 20 条课程评论"""
        try:
            resp = self.get(
                f"{COURSERA_API_BASE}/reviews.v1",
                params={
                    "courseId": course_id,
                    "fields": "rating,reviewText,createdAt,helpfulVotes",
                    "limit": 20,
                },
                delay=False,
            )
            reviews = []
            for r in resp.json().get("elements", []):
                reviews.append({
                    "rating":         r.get("rating"),
                    "content":        r.get("reviewText", ""),
                    "helpful_votes":  r.get("helpfulVotes", 0),
                    "created_at":     str(r.get("createdAt", "")),
                })
            return reviews
        except Exception:
            return []
