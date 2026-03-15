"""
B 站（Bilibili）课程数据爬虫

采集单位：
  - 优先以「合集（ugc_season）」为课程单位，season 内所有视频 → syllabus
  - 无合集的独立视频以 BV 号为课程单位，分P列表 → syllabus
  - course_id 规则：合集用 season_{id}，独立视频用 bvid

搜索策略（CS 优先）：
  - 先用知名课程代号/学校名精确搜索（MIT / UCB / CS61A 等）
  - 再用中文 CS 通用词兜底（操作系统 / 数据结构 等）
  - 去重：season_id 或 bvid 已存在则跳过；同一 season 被多个视频命中只爬一次

学期去重：
  - 同一课程不同学期（CS61A 2020Fall vs 2021Fall）视为不同记录，均保留
  - 标题中解析 year / semester 存入 metadata，便于后续过滤

限速策略（拟人化）：
  - 主请求间隔 2~6 s（BaseScraper.random_delay）
  - 同视频子请求间隔 0.5~1.5 s
  - 每处理 50 条合集后随机暂停 10~20 s
  - 每翻 3 页搜索结果多停一次

认证：
  - 将登录后的 Cookie 写入 .env 的 BILIBILI_COOKIE（含 SESSDATA / bili_jct）
"""

import hashlib
import json
import random
import re
import time
from urllib.parse import urlencode

from tqdm import tqdm

from config import BILIBILI_COOKIE, MAX_COURSES
from scrapers.base import BaseScraper
from utils.anti_detect import random_delay
from utils.storage import is_already_scraped, save_json, upsert_course

# ── wbi 签名混淆表 ─────────────────────────────────────────────────────────────
_MIXIN_KEY_ENC_TAB = [
    46, 47, 18,  2, 53,  8, 23, 32, 15, 50, 10, 31, 58,  3, 45, 35,
    27, 43,  5, 49, 33,  9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48,  7, 16, 24, 55, 40, 61, 26, 17,  0,  1, 60, 51, 30,  4,
    22, 25, 54, 21, 56, 59,  6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]

_BILIBILI_ORIGIN = "https://www.bilibili.com"

# ── CS 搜索关键词（精确 → 通用）──────────────────────────────────────────────
_CS_KEYWORDS = [
    # 顶校课号
    "CS61A", "CS61B", "CS61C", "CS162", "CS186", "CS188", "CS189",
    "CS231N", "CS224N", "CS285", "CS161",
    "6.824", "6.828", "6.006", "6.031", "6.034", "6.004",
    "15-445", "15-721", "10-601", "11-785",
    # 学校名 + 课程类型
    "MIT公开课", "UCB公开课", "Stanford公开课", "CMU公开课",
    "MIT课程", "伯克利CS",
    # 中文 CS 核心课
    "操作系统公开课", "计算机网络公开课", "数据结构与算法",
    "编译原理课", "计算机组成原理", "数据库系统",
    "机器学习公开课", "深度学习公开课", "计算机视觉课",
    "分布式系统", "计算机体系结构",
]

# 搜索分区 tid（知识区 + 科学科普 + 校园学习）
_TIDS = [36, 207, 201]


class BilibiliScraper(BaseScraper):
    PLATFORM = "bilibili"

    def __init__(self):
        super().__init__()
        self._wbi_img_key: str = ""
        self._wbi_sub_key: str = ""
        # 已处理的 season_id / bvid 集合（本次运行内去重）
        self._seen_ids: set[str] = set()

        self.session.headers.update({
            "Origin":         _BILIBILI_ORIGIN,
            "Referer":        _BILIBILI_ORIGIN + "/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        if BILIBILI_COOKIE:
            self.session.headers.update({"Cookie": BILIBILI_COOKIE})

    # ── wbi 签名 ──────────────────────────────────────────────────────────────

    def _refresh_wbi_keys(self) -> None:
        resp = self.get("https://api.bilibili.com/x/web-interface/nav", delay=False)
        wbi = resp.json().get("data", {}).get("wbi_img", {})
        self._wbi_img_key = wbi.get("img_url", "").rsplit("/", 1)[-1].split(".")[0]
        self._wbi_sub_key = wbi.get("sub_url", "").rsplit("/", 1)[-1].split(".")[0]

    def _mixin_key(self) -> str:
        raw = self._wbi_img_key + self._wbi_sub_key
        return "".join(raw[i] for i in _MIXIN_KEY_ENC_TAB if i < len(raw))[:32]

    def _sign(self, params: dict) -> dict:
        if not self._wbi_img_key:
            self._refresh_wbi_keys()
        signed = dict(sorted({**params, "wts": int(time.time())}.items()))
        query = urlencode(
            {k: re.sub(r"[!'()*]", "", str(v)) for k, v in signed.items()}
        )
        signed["w_rid"] = hashlib.md5(
            (query + self._mixin_key()).encode()
        ).hexdigest()
        return signed

    # ── 搜索：收集 (bvid, 来源关键词) ────────────────────────────────────────

    def _search_bvids(self, target: int) -> list[tuple[str, str]]:
        """多关键词搜索，返回 (bvid, keyword) 列表，按关键词相关度排序"""
        results: list[tuple[str, str]] = []
        seen_bvids: set[str] = set()

        for keyword in _CS_KEYWORDS:
            if len(results) >= target * 3:   # 留足候选量（season 合并会缩量）
                break
            self.log(f"搜索关键词: 【{keyword}】 已收集 {len(results)} 个候选")
            for tid in _TIDS:
                page = 1
                MAX_PAGES = 5   # 每个关键词最多翻 5 页，避免卡死
                while page <= MAX_PAGES and len(results) < target * 3:
                    params = self._sign({
                        "search_type": "video",
                        "keyword":     keyword,
                        "tids":        tid,
                        "page":        page,
                        "page_size":   50,
                        "order":       "totalrank",
                    })
                    try:
                        resp = self.get(
                            "https://api.bilibili.com/x/web-interface/search/type",
                            params=params,
                        )
                        items = resp.json().get("data", {}).get("result", []) or []
                        if not items:
                            break
                        new_count = 0
                        for item in items:
                            bvid = item.get("bvid", "")
                            if bvid and bvid not in seen_bvids:
                                seen_bvids.add(bvid)
                                results.append((bvid, keyword))
                                new_count += 1
                        self.log(f"  tid={tid} p={page}: +{new_count} 个（累计 {len(results)}）")
                        page += 1
                        if page % 3 == 0:
                            random_delay(extra_factor=1.5)
                    except Exception as e:
                        self.log(f"搜索异常 [{keyword}] tid={tid} p={page}: {e}")
                        break
                break   # 每个关键词只跑第一个 tid

        return results

    # ── 视频详情（含 ugc_season 字段）────────────────────────────────────────

    def _fetch_view(self, bvid: str) -> dict:
        try:
            resp = self.get(
                "https://api.bilibili.com/x/web-interface/view",
                params={"bvid": bvid},
                delay=False,
            )
            return resp.json().get("data", {}) or {}
        except Exception as e:
            self.log(f"view 失败 {bvid}: {e}")
            return {}

    # ── 合集完整视频列表 ──────────────────────────────────────────────────────

    def _fetch_season_videos(self, mid: int, season_id: int) -> list[dict]:
        """获取合集内全部视频（分页拉取）"""
        videos = []
        page_num = 1
        while True:
            _short_pause()
            try:
                resp = self.get(
                    "https://api.bilibili.com/x/polymer/web-space/seasons_archives_list",
                    params={
                        "mid":       mid,
                        "season_id": season_id,
                        "page_num":  page_num,
                        "page_size": 100,
                    },
                    delay=False,
                )
                body = resp.json().get("data", {}) or {}
                archives = body.get("archives", []) or []
                if not archives:
                    break
                videos.extend(archives)
                meta = body.get("page", {})
                total = meta.get("total", 0)
                if len(videos) >= total:
                    break
                page_num += 1
            except Exception as e:
                self.log(f"season 视频列表失败 season_id={season_id}: {e}")
                break
        return videos

    # ── 标签 / 字幕 / 评论 ───────────────────────────────────────────────────

    def _fetch_tags(self, bvid: str) -> list[str]:
        _short_pause()
        try:
            resp = self.get(
                "https://api.bilibili.com/x/tag/archive/tags",
                params={"bvid": bvid},
                delay=False,
            )
            return [t["tag_name"] for t in (resp.json().get("data") or []) if t.get("tag_name")]
        except Exception:
            return []

    def _fetch_subtitle(self, bvid: str, cid: int) -> str:
        """获取第一个分P字幕全文（需登录）"""
        _short_pause()
        try:
            resp = self.get(
                "https://api.bilibili.com/x/player/v2",
                params={"bvid": bvid, "cid": cid},
                delay=False,
            )
            subtitles = (
                resp.json().get("data", {}).get("subtitle", {}).get("subtitles", [])
            ) or []
            if not subtitles:
                return ""
            url = next(
                (s["subtitle_url"] for s in subtitles if "zh" in s.get("lan", "")),
                subtitles[0].get("subtitle_url", ""),
            )
            if not url:
                return ""
            if url.startswith("//"):
                url = "https:" + url
            sub_resp = self.session.get(url, timeout=15)
            sub_resp.raise_for_status()
            return " ".join(
                seg.get("content", "") for seg in sub_resp.json().get("body", [])
            )
        except Exception:
            return ""

    def _fetch_comments(self, aid: int, limit: int = 20) -> list[dict]:
        _short_pause()
        try:
            resp = self.get(
                "https://api.bilibili.com/x/v2/reply/main",
                params={"type": 1, "oid": aid, "mode": 3, "ps": min(limit, 20)},
                delay=False,
            )
            replies = resp.json().get("data", {}).get("replies", []) or []
            return [
                {
                    "rating":        None,
                    "content":       r.get("content", {}).get("message", ""),
                    "helpful_votes": r.get("like", 0),
                    "created_at":    str(r.get("ctime", "")),
                }
                for r in replies[:limit]
            ]
        except Exception:
            return []

    # ── 学期解析 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_semester(title: str) -> dict:
        """从标题提取 year / semester，便于区分同课程不同学期"""
        year_m = re.search(r"\b(20\d{2})\b", title)
        year = year_m.group(1) if year_m else None

        semester = None
        for pattern, name in [
            (r"\b[Ff]all\b",   "Fall"),
            (r"\b[Ss]pring\b", "Spring"),
            (r"\b[Ss]ummer\b", "Summer"),
            (r"秋[季学]?",     "Fall"),
            (r"春[季学]?",     "Spring"),
            (r"夏[季学]?",     "Summer"),
            (r"上[半]?[学]?期", "Spring"),
            (r"下[半]?[学]?期", "Fall"),
        ]:
            if re.search(pattern, title):
                semester = name
                break

        return {"year": year, "semester": semester}

    # ── 整合：合集模式 ────────────────────────────────────────────────────────

    def _build_from_season(
        self, season: dict, owner: dict, first_bvid: str, keyword: str
    ) -> dict | None:
        season_id  = season.get("id")
        course_id  = f"season_{season_id}"
        mid        = owner.get("mid", 0)

        # 拉取合集内全部视频（分P 更全）
        archives = self._fetch_season_videos(mid, season_id)
        if not archives:
            # 退化：用 season.sections 中的 episodes
            episodes = []
            for sec in season.get("sections", []):
                episodes.extend(sec.get("episodes", []))
            archives = [
                {"bvid": ep.get("bvid", ""), "title": ep.get("title", ""),
                 "duration": ep.get("arc", {}).get("duration", 0)}
                for ep in episodes
            ]

        syllabus = [
            {
                "week":        i + 1,
                "title":       a.get("title", f"P{i + 1}"),
                "description": "",
                "duration":    f"{a.get('duration', 0)}s",
            }
            for i, a in enumerate(archives)
        ]

        tags          = self._fetch_tags(first_bvid)
        subtitle_text = ""
        # 仅当合集较小（≤50个视频）时抓第一节字幕，避免过多请求
        if archives and len(archives) <= 50:
            first_cid = archives[0].get("cid", 0)
            if first_cid:
                subtitle_text = self._fetch_subtitle(first_bvid, first_cid)

        # 用合集第一个视频的 aid 获取评论
        first_aid = archives[0].get("aid", 0) if archives else 0
        comments  = self._fetch_comments(first_aid) if first_aid else []

        title    = season.get("title", "")
        sem_info = self._parse_semester(title)

        stat = season.get("stat", {})
        return {
            "course_id":      course_id,
            "platform":       "bilibili",
            "title":          title,
            "slug":           f"season_{season_id}",
            "description":    season.get("intro", ""),
            "learning_goals": tags,
            "prerequisites":  "",
            "difficulty":     "",
            "duration":       f"{sum(a.get('duration', 0) for a in archives)}s",
            "language":       "zh",
            "url":            f"https://www.bilibili.com/video/{first_bvid}",
            "instructors":    [{"name": owner.get("name", ""), "title": "UP主", "institution": ""}],
            "institutions":   [owner.get("name", "")],
            "rating": {
                "avg":        None,
                "count":      stat.get("reply", 0),
                "enrollment": stat.get("view", 0),
                "completion_rate": None,
                "like":       stat.get("like", 0),
                "coin":       stat.get("coin", 0),
                "favorite":   stat.get("fav", 0),
                "danmaku":    stat.get("danmaku", 0),
            },
            "syllabus":       syllabus,
            "reviews":        comments,
            # 附加元数据
            "subtitle_text":  subtitle_text,
            "cover":          season.get("cover", ""),
            "season_id":      season_id,
            "episode_count":  len(archives),
            "search_keyword": keyword,
            "year":           sem_info["year"],
            "semester":       sem_info["semester"],
        }

    # ── 整合：独立视频模式（无合集）──────────────────────────────────────────

    def _build_from_video(self, bvid: str, d: dict, keyword: str) -> dict | None:
        aid   = d.get("aid")
        stat  = d.get("stat", {})
        owner = d.get("owner", {})
        pages = d.get("pages", []) or []

        tags          = self._fetch_tags(bvid)
        subtitle_text = self._fetch_subtitle(bvid, pages[0]["cid"]) if pages else ""
        comments      = self._fetch_comments(aid) if aid else []

        syllabus = [
            {
                "week":        i + 1,
                "title":       p.get("part") or f"P{i + 1}",
                "description": "",
                "duration":    f"{p.get('duration', 0)}s",
            }
            for i, p in enumerate(pages)
        ]

        title    = d.get("title", "")
        sem_info = self._parse_semester(title)

        return {
            "course_id":      bvid,
            "platform":       "bilibili",
            "title":          title,
            "slug":           bvid,
            "description":    d.get("desc", ""),
            "learning_goals": tags,
            "prerequisites":  "",
            "difficulty":     "",
            "duration":       f"{d.get('duration', 0)}s",
            "language":       "zh",
            "url":            f"https://www.bilibili.com/video/{bvid}",
            "instructors":    [{"name": owner.get("name", ""), "title": "UP主", "institution": ""}],
            "institutions":   [owner.get("name", "")],
            "rating": {
                "avg":        None,
                "count":      stat.get("reply", 0),
                "enrollment": stat.get("view", 0),
                "completion_rate": None,
                "like":       stat.get("like", 0),
                "coin":       stat.get("coin", 0),
                "favorite":   stat.get("favorite", 0),
                "danmaku":    stat.get("danmaku", 0),
            },
            "syllabus":       syllabus,
            "reviews":        comments,
            "subtitle_text":  subtitle_text,
            "cover":          d.get("pic", ""),
            "season_id":      None,
            "episode_count":  len(pages),
            "search_keyword": keyword,
            "year":           sem_info["year"],
            "semester":       sem_info["semester"],
        }

    # ── 入口 ─────────────────────────────────────────────────────────────────

    def run(self) -> int:
        target = MAX_COURSES.get("bilibili", 1000)

        self.log("初始化 wbi 签名密钥...")
        self._refresh_wbi_keys()

        self.log(f"开始搜索 B 站 CS 课程（目标 {target} 条）...")
        candidates = self._search_bvids(target)
        self.log(f"候选视频 {len(candidates)} 个，开始处理（合集去重）...")

        saved = 0
        for bvid, keyword in tqdm(candidates, desc="Bilibili-CS"):
            if saved >= target:
                break

            # 获取视频详情，判断是否属于合集
            d = self._fetch_view(bvid)
            if not d:
                continue

            season = d.get("ugc_season", {})
            if season and season.get("id"):
                # ── 合集模式 ──────────────────────────────────────────────
                season_id  = season.get("id")
                course_id  = f"season_{season_id}"

                if course_id in self._seen_ids:
                    continue
                self._seen_ids.add(course_id)

                if is_already_scraped("bilibili", course_id):
                    continue

                course = self._build_from_season(season, d.get("owner", {}), bvid, keyword)
            else:
                # ── 独立视频模式 ───────────────────────────────────────────
                if bvid in self._seen_ids:
                    continue
                self._seen_ids.add(bvid)

                if is_already_scraped("bilibili", bvid):
                    continue

                # 独立视频分P少于 3 的很可能不是课程，跳过
                if len(d.get("pages", [])) < 3:
                    continue

                course = self._build_from_video(bvid, d, keyword)

            if not course:
                continue

            save_json("bilibili", course)
            upsert_course("bilibili", course)
            saved += 1

            ep = course.get("episode_count", 0)
            sem = f" [{course.get('year','')} {course.get('semester','')}]".strip("[] ")
            self.log(f"  [{saved:>4}] {course['title'][:45]}  ({ep}集){' '+sem if sem else ''}")

            # 每 50 条长停顿
            if saved % 50 == 0:
                pause = random.uniform(10, 20)
                self.log(f"已保存 {saved} 条，暂停 {pause:.1f}s...")
                time.sleep(pause)

        self.log(f"完成，本次新增 {saved} 门课程")
        return saved


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _short_pause() -> None:
    """同一视频子请求间的短暂停顿（0.5~1.5 s）"""
    time.sleep(random.uniform(0.5, 1.5))
