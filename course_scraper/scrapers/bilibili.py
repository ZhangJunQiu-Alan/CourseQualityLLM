"""
B 站（Bilibili）课程数据爬虫

采集策略：
  - 在知识区（tid=36）多子分类 × 多关键词搜索，收集 BV 号
  - 逐条爬取：视频信息 / 标签 / 分P大纲 / 字幕（若有）/ 热门评论
  - 数据映射到与其他平台统一的 course schema

限速策略（拟人化）：
  - 每次 API 请求后随机延迟 2~6 s（继承自 BaseScraper.random_delay）
  - 同一视频的子请求（标签/字幕/评论）间隔 0.5~1.5 s（短停顿）
  - 每处理 50 条视频后随机暂停 10~20 s（模拟用户休息）
  - 搜索翻页每 3 页多停一次（模拟用户翻页浏览）

认证：
  - 将登录后的 Cookie（含 SESSDATA）写入 .env 的 BILIBILI_COOKIE
  - 未认证时字幕接口和部分高清信息不可用，评论可正常获取
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

# ── wbi 签名混淆表（B 站官方固定，2023 年起搜索接口必须携带签名）────────────
_MIXIN_KEY_ENC_TAB = [
    46, 47, 18,  2, 53,  8, 23, 32, 15, 50, 10, 31, 58,  3, 45, 35,
    27, 43,  5, 49, 33,  9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48,  7, 16, 24, 55, 40, 61, 26, 17,  0,  1, 60, 51, 30,  4,
    22, 25, 54, 21, 56, 59,  6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]

# 搜索关键词 × 知识区子分区 tid（笛卡尔积搜索，去重汇总）
_KEYWORDS = ["网课", "课程", "教程", "公开课", "系列课", "讲解"]
_TIDS = [
    36,   # 知识（大类，兜底）
    207,  # 校园学习
    208,  # 职业职场
    201,  # 科学科普
    124,  # 社科·法律·心理
    228,  # 财经商业
    209,  # 人文历史
    229,  # 野生技术协会
]

_BILIBILI_ORIGIN = "https://www.bilibili.com"


class BilibiliScraper(BaseScraper):
    PLATFORM = "bilibili"

    def __init__(self):
        super().__init__()
        self._wbi_img_key: str = ""
        self._wbi_sub_key: str = ""
        # 注入认证 Cookie 和浏览器特征头
        self.session.headers.update({
            "Origin":  _BILIBILI_ORIGIN,
            "Referer": _BILIBILI_ORIGIN + "/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        if BILIBILI_COOKIE:
            self.session.headers.update({"Cookie": BILIBILI_COOKIE})

    # ── wbi 签名 ──────────────────────────────────────────────────────────────

    def _refresh_wbi_keys(self) -> None:
        """从导航接口刷新 wbi img/sub key（每次运行获取一次）"""
        resp = self.get("https://api.bilibili.com/x/web-interface/nav", delay=False)
        wbi = resp.json().get("data", {}).get("wbi_img", {})
        self._wbi_img_key = wbi.get("img_url", "").rsplit("/", 1)[-1].split(".")[0]
        self._wbi_sub_key = wbi.get("sub_url", "").rsplit("/", 1)[-1].split(".")[0]

    def _mixin_key(self) -> str:
        raw = self._wbi_img_key + self._wbi_sub_key
        return "".join(raw[i] for i in _MIXIN_KEY_ENC_TAB if i < len(raw))[:32]

    def _sign(self, params: dict) -> dict:
        """对请求参数附加 wbi 签名（wts + w_rid）"""
        if not self._wbi_img_key:
            self._refresh_wbi_keys()
        signed = dict(sorted({**params, "wts": int(time.time())}.items()))
        # B 站要求过滤特殊字符再计算签名
        query = urlencode(
            {k: re.sub(r"[!'()*]", "", str(v)) for k, v in signed.items()}
        )
        signed["w_rid"] = hashlib.md5(
            (query + self._mixin_key()).encode()
        ).hexdigest()
        return signed

    # ── 搜索：收集 BV 号 ──────────────────────────────────────────────────────

    def _search_bvids(self, target: int) -> list[str]:
        """多关键词 × 多分区搜索，收集去重后的 BV 号列表"""
        bvids: set[str] = set()

        for keyword in _KEYWORDS:
            if len(bvids) >= target:
                break
            for tid in _TIDS:
                if len(bvids) >= target:
                    break
                page = 1
                while len(bvids) < target:
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
                        results = resp.json().get("data", {}).get("result", []) or []
                        if not results:
                            break
                        for item in results:
                            bvid = item.get("bvid", "")
                            if bvid:
                                bvids.add(bvid)
                        page += 1
                        # 每 3 页多停一次，模拟用户翻页浏览
                        if page % 3 == 0:
                            random_delay(extra_factor=1.8)
                    except Exception as e:
                        self.log(f"搜索异常 keyword={keyword} tid={tid} p={page}: {e}")
                        break

        return list(bvids)[:target]

    # ── 子请求：视频信息 / 标签 / 字幕 / 评论 ────────────────────────────────

    def _fetch_view(self, bvid: str) -> dict:
        """获取视频基础信息（标题、简介、分P列表、UP主、统计数据）"""
        try:
            resp = self.get(
                "https://api.bilibili.com/x/web-interface/view",
                params={"bvid": bvid},
                delay=False,
            )
            return resp.json().get("data", {}) or {}
        except Exception as e:
            self.log(f"view 接口失败 {bvid}: {e}")
            return {}

    def _fetch_tags(self, bvid: str) -> list[str]:
        """获取视频标签列表"""
        _short_pause()
        try:
            resp = self.get(
                "https://api.bilibili.com/x/tag/archive/tags",
                params={"bvid": bvid},
                delay=False,
            )
            tags = resp.json().get("data", []) or []
            return [t["tag_name"] for t in tags if t.get("tag_name")]
        except Exception:
            return []

    def _fetch_subtitle(self, bvid: str, cid: int) -> str:
        """获取字幕文本（需登录，无字幕时返回空字符串）"""
        _short_pause()
        try:
            resp = self.get(
                "https://api.bilibili.com/x/player/v2",
                params={"bvid": bvid, "cid": cid},
                delay=False,
            )
            subtitles = (
                resp.json()
                .get("data", {})
                .get("subtitle", {})
                .get("subtitles", [])
            ) or []
            if not subtitles:
                return ""
            # 中文字幕优先
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
            body = sub_resp.json().get("body", [])
            return " ".join(seg.get("content", "") for seg in body)
        except Exception:
            return ""

    def _fetch_comments(self, aid: int, limit: int = 20) -> list[dict]:
        """获取热门评论（按热度排序）"""
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
                    "rating":        None,   # B 站评论无星级评分
                    "content":       r.get("content", {}).get("message", ""),
                    "helpful_votes": r.get("like", 0),
                    "created_at":    str(r.get("ctime", "")),
                }
                for r in replies[:limit]
            ]
        except Exception as e:
            self.log(f"评论接口失败 aid={aid}: {e}")
            return []

    # ── 整合单条记录 ──────────────────────────────────────────────────────────

    def _build_course(self, bvid: str) -> dict | None:
        """抓取并整合一个视频的全部字段"""
        d = self._fetch_view(bvid)
        if not d:
            return None

        aid   = d.get("aid")
        stat  = d.get("stat", {})
        owner = d.get("owner", {})
        pages = d.get("pages", []) or []   # 分P列表

        tags          = self._fetch_tags(bvid)
        subtitle_text = self._fetch_subtitle(bvid, pages[0]["cid"]) if pages else ""
        comments      = self._fetch_comments(aid) if aid else []

        # 分P → syllabus（每个分P视作一节课）
        syllabus = [
            {
                "week":        i + 1,
                "title":       p.get("part") or f"P{i + 1}",
                "description": "",
                "duration":    f"{p.get('duration', 0)}s",
            }
            for i, p in enumerate(pages)
        ]

        return {
            "course_id":      bvid,
            "platform":       "bilibili",
            "title":          d.get("title", ""),
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
                "avg":             None,
                "count":           stat.get("reply", 0),
                "enrollment":      stat.get("view", 0),
                "completion_rate": None,
                # B 站独有互动指标
                "like":            stat.get("like", 0),
                "coin":            stat.get("coin", 0),
                "favorite":        stat.get("favorite", 0),
                "danmaku":         stat.get("danmaku", 0),
            },
            "syllabus":       syllabus,
            "reviews":        comments,
            # B 站附加字段（仅存 JSON，不入 DB）
            "subtitle_text":  subtitle_text,
            "cover":          d.get("pic", ""),
            "pub_date":       d.get("pubdate", 0),
        }

    # ── 入口 ─────────────────────────────────────────────────────────────────

    def run(self) -> int:
        target = MAX_COURSES.get("bilibili", 1000)

        self.log("初始化 wbi 签名密钥...")
        self._refresh_wbi_keys()

        self.log(f"开始搜索 B 站知识区视频（目标 {target} 条）...")
        bvids = self._search_bvids(target)
        self.log(f"去重后共 {len(bvids)} 个视频，开始爬取详情...")

        saved = 0
        for bvid in tqdm(bvids, desc="Bilibili"):
            if is_already_scraped("bilibili", bvid):
                continue

            course = self._build_course(bvid)
            if not course:
                continue

            save_json("bilibili", course)
            upsert_course("bilibili", course)
            saved += 1

            # 每 50 条随机长停顿（模拟用户中途休息）
            if saved % 50 == 0:
                pause = random.uniform(10, 20)
                self.log(f"已保存 {saved} 条，暂停 {pause:.1f}s...")
                time.sleep(pause)

        self.log(f"完成，本次新增 {saved} 门课程")
        return saved


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _short_pause() -> None:
    """同一视频子请求间的短暂停顿（0.5~1.5 s），避免突发并发"""
    time.sleep(random.uniform(0.5, 1.5))
