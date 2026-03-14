"""
数据存储工具
- JSON 文件（原始备份）
- SQLite 数据库（结构化查询）
- 支持断点续爬（去重检测）
"""
import json
import sqlite3
import os
from datetime import datetime
from typing import Optional
from config import RAW_DIR, DB_PATH


# ── JSON 存储 ─────────────────────────────────────────────────────────────────

def save_json(platform: str, course: dict) -> None:
    """将单门课程保存为 JSON 文件"""
    platform_dir = os.path.join(RAW_DIR, platform)
    os.makedirs(platform_dir, exist_ok=True)
    course_id = str(course.get("id", course.get("course_id", "unknown")))
    path = os.path.join(platform_dir, f"{course_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(course, f, ensure_ascii=False, indent=2)


def save_json_batch(platform: str, courses: list[dict]) -> None:
    """将一批课程保存为单个 JSON 文件（快照）"""
    platform_dir = os.path.join(RAW_DIR, platform)
    os.makedirs(platform_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(platform_dir, f"batch_{timestamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(courses, f, ensure_ascii=False, indent=2)


# ── SQLite 存储 ────────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """初始化数据库表结构"""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS courses (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            platform        TEXT NOT NULL,
            course_id       TEXT NOT NULL,
            title           TEXT,
            description     TEXT,
            learning_goals  TEXT,       -- JSON array
            prerequisites   TEXT,
            difficulty      TEXT,
            duration        TEXT,
            language        TEXT,
            url             TEXT,
            UNIQUE(platform, course_id)
        );

        CREATE TABLE IF NOT EXISTS instructors (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            course_pk   INTEGER NOT NULL REFERENCES courses(id),
            name        TEXT,
            title       TEXT,
            institution TEXT
        );

        CREATE TABLE IF NOT EXISTS ratings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            course_pk       INTEGER NOT NULL REFERENCES courses(id),
            avg_rating      REAL,
            rating_count    INTEGER,
            enrollment      INTEGER,
            completion_rate REAL
        );

        CREATE TABLE IF NOT EXISTS syllabus (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            course_pk   INTEGER NOT NULL REFERENCES courses(id),
            week_num    INTEGER,
            title       TEXT,
            description TEXT,
            duration    TEXT
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            course_pk   INTEGER NOT NULL REFERENCES courses(id),
            rating      INTEGER,
            content     TEXT,
            helpful_votes INTEGER DEFAULT 0,
            created_at  TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_courses_platform ON courses(platform);
        CREATE INDEX IF NOT EXISTS idx_courses_course_id ON courses(platform, course_id);
    """)
    conn.commit()
    conn.close()


def is_already_scraped(platform: str, course_id: str) -> bool:
    """检查课程是否已爬取（断点续爬用）"""
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM courses WHERE platform=? AND course_id=?",
        (platform, str(course_id))
    ).fetchone()
    conn.close()
    return row is not None


def upsert_course(platform: str, data: dict) -> Optional[int]:
    """
    插入或更新一门课程（含关联数据）
    返回 course 主键 id
    """
    conn = get_connection()
    try:
        # 主表
        conn.execute("""
            INSERT INTO courses
                (platform, course_id, title, description, learning_goals,
                 prerequisites, difficulty, duration, language, url)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(platform, course_id) DO UPDATE SET
                title=excluded.title,
                description=excluded.description,
                learning_goals=excluded.learning_goals,
                prerequisites=excluded.prerequisites,
                difficulty=excluded.difficulty,
                duration=excluded.duration,
                language=excluded.language,
                url=excluded.url
        """, (
            platform,
            str(data.get("course_id", "")),
            data.get("title"),
            data.get("description"),
            json.dumps(data.get("learning_goals", []), ensure_ascii=False),
            data.get("prerequisites"),
            data.get("difficulty"),
            data.get("duration"),
            data.get("language"),
            data.get("url"),
        ))
        conn.commit()

        course_pk = conn.execute(
            "SELECT id FROM courses WHERE platform=? AND course_id=?",
            (platform, str(data.get("course_id", "")))
        ).fetchone()["id"]

        # 讲师
        for inst in data.get("instructors", []):
            conn.execute("""
                INSERT INTO instructors (course_pk, name, title, institution)
                VALUES (?,?,?,?)
            """, (course_pk, inst.get("name"), inst.get("title"), inst.get("institution")))

        # 评分
        r = data.get("rating", {})
        if r:
            conn.execute("""
                INSERT INTO ratings (course_pk, avg_rating, rating_count, enrollment, completion_rate)
                VALUES (?,?,?,?,?)
                ON CONFLICT DO NOTHING
            """, (course_pk, r.get("avg"), r.get("count"), r.get("enrollment"), r.get("completion_rate")))

        # 大纲
        for week in data.get("syllabus", []):
            conn.execute("""
                INSERT INTO syllabus (course_pk, week_num, title, description, duration)
                VALUES (?,?,?,?,?)
            """, (course_pk, week.get("week"), week.get("title"), week.get("description"), week.get("duration")))

        # 评论（取前 20 条）
        for review in data.get("reviews", [])[:20]:
            conn.execute("""
                INSERT INTO reviews (course_pk, rating, content, helpful_votes, created_at)
                VALUES (?,?,?,?,?)
            """, (course_pk, review.get("rating"), review.get("content"),
                  review.get("helpful_votes", 0), review.get("created_at")))

        conn.commit()
        return course_pk
    except Exception as e:
        conn.rollback()
        print(f"[storage] 写入失败: {e}")
        return None
    finally:
        conn.close()


def get_stats() -> dict:
    """返回各平台爬取统计"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT platform, COUNT(*) as cnt FROM courses GROUP BY platform"
    ).fetchall()
    conn.close()
    return {row["platform"]: row["cnt"] for row in rows}
