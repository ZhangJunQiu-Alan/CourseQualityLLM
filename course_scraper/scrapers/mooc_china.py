"""
中国大学 MOOC 爬虫（icourse163.org）

策略：
  1. 用 Playwright 访问搜索页，等待 mocSearchBean.searchCourse.rpc 请求触发，
     从请求头中提取 edu-script-token（= NTESSTUDYSI cookie = csrfKey）
  2. 将 cookie + edu-script-token 交给 requests.Session
  3. 主接口：POST /web/j/mocSearchBean.searchCourse.rpc?csrfKey=xxx
     参数：mocCourseQueryVo={"keyword":"","pageIndex":N,"orderBy":0,"stats":30,"pageSize":50}
  4. 从每条搜索结果直接提取课程信息（不需要详情接口）
"""
import re
import json
import asyncio
import random
import requests
from urllib.parse import quote
from tqdm import tqdm
from playwright.async_api import async_playwright
from utils.anti_detect import random_delay, random_ua
from utils.storage import is_already_scraped, upsert_course, save_json
from config import MOOC_CN_BASE, MAX_COURSES, TIMEOUT


class MoocChinaScraper:
    PLATFORM = "mooc_cn"

    def run(self) -> int:
        # ① 用 Playwright 触发搜索页，拿到 csrfKey + edu-script-token + cookies
        csrf_key, edu_token, cookies = asyncio.run(self._get_session())
        if not csrf_key:
            self.log("无法获取 csrfKey，退出")
            return 0
        self.log(f"csrfKey: {csrf_key}")

        # ② 构建 requests.Session
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "edu-script-token": edu_token or csrf_key,
            "Referer": f"{MOOC_CN_BASE}/search.htm",
            "Origin": MOOC_CN_BASE,
        })
        for c in cookies:
            session.cookies.set(c["name"], c["value"], domain=c.get("domain", ".icourse163.org"))

        # ③ 爬取课程（搜索+提取，不需要单独获取详情）
        self.log("开始爬取课程...")
        saved = self._fetch_and_save(session, csrf_key)
        self.log(f"完成，新增 {saved} 门课程")
        return saved

    # ── Playwright：触发搜索页获取 session ───────────────────────────────────

    async def _get_session(self) -> tuple[str, str, list]:
        """访问搜索页，等待 searchCourse RPC 请求，提取 csrfKey 和 edu-script-token"""
        for attempt in range(3):
            try:
                async with async_playwright() as pw:
                    browser = await pw.chromium.launch(
                        headless=True,
                        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
                    )
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
                        viewport={"width": 1366, "height": 768},
                        locale="zh-CN",
                    )
                    await context.add_init_script(
                        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
                    )
                    page = await context.new_page()

                    captured = {}
                    async def on_req(req):
                        if "mocSearchBean.searchCourse" in req.url and "csrfKey=" in req.url:
                            m = re.search(r'csrfKey=([a-f0-9]{32})', req.url)
                            if m:
                                captured["csrf"] = m.group(1)
                                captured["edu_token"] = req.headers.get("edu-script-token", m.group(1))
                    page.on("request", on_req)

                    self.log(f"加载搜索页（第 {attempt+1} 次）...")
                    await page.goto(MOOC_CN_BASE, wait_until="domcontentloaded", timeout=60000)
                    await asyncio.sleep(2)
                    await page.goto(
                        f"{MOOC_CN_BASE}/search.htm#/?query=&type=1",
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )
                    await asyncio.sleep(8)
                    await page.evaluate("window.scrollTo(0, 2000)")
                    await asyncio.sleep(3)

                    cookies = await context.cookies()
                    await browser.close()

                    csrf = captured.get("csrf")
                    edu = captured.get("edu_token", csrf)

                    # 备用：直接用 NTESSTUDYSI cookie
                    if not csrf:
                        csrf = next((c["value"] for c in cookies if c["name"] == "NTESSTUDYSI"), None)
                        edu = csrf

                    if csrf:
                        return csrf, edu or csrf, cookies

            except Exception as e:
                self.log(f"Playwright 异常（第 {attempt+1} 次）: {e}")
                await asyncio.sleep(5)

        return "", "", []

    # ── requests：批量爬取 ─────────────────────────────────────────────────

    def _search_courses(self, session: requests.Session, csrf_key: str,
                        page_idx: int, page_size: int = 50) -> list:
        """搜索接口，返回课程 item 列表，失败重试 3 次"""
        import time
        vo = json.dumps({
            "keyword": "",
            "pageIndex": page_idx,
            "highlight": False,
            "orderBy": 0,
            "stats": 30,
            "pageSize": page_size,
        })
        url = f"{MOOC_CN_BASE}/web/j/mocSearchBean.searchCourse.rpc?csrfKey={csrf_key}"
        for attempt in range(3):
            try:
                r = session.post(url, data=f"mocCourseQueryVo={quote(vo)}", timeout=TIMEOUT)
                r.raise_for_status()
                body = r.json()
                if body.get("code") == 0:
                    return (body.get("result") or {}).get("list", [])
                self.log(f"搜索失败 page={page_idx} code={body.get('code')}")
                return []
            except Exception as e:
                self.log(f"搜索异常 page={page_idx} 第{attempt+1}次: {e}")
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
        return []

    def _parse_course(self, item: dict) -> dict | None:
        """从搜索结果 item 解析课程数据"""
        try:
            mc = item.get("mocCourseCard") or {}
            dto = mc.get("mocCourseCardDto") or {}
            base = item.get("mocCourseKyCardBaseInfoDto") or {}

            course_id = str(dto.get("id") or item.get("courseId") or "")
            if not course_id:
                return None

            # 课程名
            title = (dto.get("name") or base.get("courseName")
                     or item.get("highlightName") or "")
            if not title:
                return None

            # 讲师
            teachers = mc.get("teacherDtoList") or []
            teacher_name = base.get("teacherName") or item.get("highlightTeacherNames", "").rstrip(";")
            if teachers:
                instructors = [
                    {
                        "name": t.get("name", ""),
                        "title": t.get("title", ""),
                        "institution": (t.get("school") or {}).get("name", "") if isinstance(t.get("school"), dict) else "",
                    }
                    for t in teachers
                ]
            else:
                instructors = [{"name": teacher_name, "title": "", "institution": ""}] if teacher_name else []

            # 机构
            school = mc.get("school") or {}
            school_name = (school.get("name") if isinstance(school, dict) else "") or item.get("highlightUniversity", "")
            institutions = [school_name] if school_name else []

            # 描述（来自搜索高亮内容）
            highlight = item.get("highlightContent") or ""
            description = re.sub(r'^spContent=', '', highlight).strip()

            # 学习人数
            enroll = base.get("enrollNum") or dto.get("learnedCount") or dto.get("learnerCount")

            # 标签
            tags = base.get("tags") or dto.get("mocTagDtos") or []
            if isinstance(tags, list):
                tag_names = [t.get("tagName") or t if isinstance(t, str) else "" for t in tags]
            else:
                tag_names = []

            return {
                "course_id":      course_id,
                "platform":       self.PLATFORM,
                "title":          title,
                "description":    description,
                "learning_goals": [],
                "prerequisites":  "",
                "difficulty":     "",
                "duration":       "",
                "language":       "zh-CN",
                "url":            f"{MOOC_CN_BASE}/learn/{course_id}",
                "instructors":    instructors,
                "institutions":   institutions,
                "rating": {
                    "avg":             dto.get("score"),
                    "count":           None,
                    "enrollment":      int(enroll) if enroll else None,
                    "completion_rate": None,
                },
                "syllabus":       [],
                "reviews":        [],
                "tags":           [t for t in tag_names if t],
            }
        except Exception as e:
            self.log(f"解析失败: {e}")
            return None

    def _fetch_and_save(self, session: requests.Session, csrf_key: str) -> int:
        saved = 0
        page_idx = 1
        target = MAX_COURSES["mooc_cn"]

        with tqdm(total=target, desc="中国大学MOOC") as pbar:
            while saved < target:
                items = self._search_courses(session, csrf_key, page_idx, page_size=50)
                if not items:
                    self.log(f"第 {page_idx} 页无数据，停止")
                    if page_idx > 1:
                        break
                    # 第1页无数据可能是会话失效，直接退出
                    break

                for item in items:
                    if saved >= target:
                        break
                    data = self._parse_course(item)
                    if not data:
                        continue
                    if is_already_scraped(self.PLATFORM, data["course_id"]):
                        pbar.update(1)
                        continue
                    upsert_course(self.PLATFORM, data)
                    save_json(self.PLATFORM, data)
                    saved += 1
                    pbar.update(1)

                page_idx += 1
                random_delay(extra_factor=0.2)  # 0.4~1.2s between pages

        return saved

    def log(self, msg: str) -> None:
        print(f"[mooc_cn] {msg}", flush=True)
