import os
from dotenv import load_dotenv

load_dotenv()

# ── 代理配置（可选，留空则不使用代理）──────────────────────────────────────────
# 格式: ["http://user:pass@ip:port", ...]
# 可对接付费代理服务，如快代理、芝麻代理等
PROXY_LIST: list[str] = [
    # "http://user:password@proxy_ip:port",
]

# ── 限速配置 ──────────────────────────────────────────────────────────────────
DELAY_MIN = 2.0   # 请求间最小等待秒数
DELAY_MAX = 6.0   # 请求间最大等待秒数
MAX_RETRIES = 3   # 最大重试次数
TIMEOUT = 30      # 请求超时秒数

# ── 并发配置 ──────────────────────────────────────────────────────────────────
CONCURRENT_REQUESTS = 2   # 同时并发请求数（保持低位避免封禁）

# ── 存储配置 ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR  = os.path.join(DATA_DIR, "raw")
DB_PATH  = os.path.join(DATA_DIR, "db", "courses.db")

# ── Coursera 认证 Cookie（填入 .env 的 COURSERA_COOKIE）─────────────────────
COURSERA_COOKIE: str = os.getenv("COURSERA_COOKIE", "")

# ── 爬取目标配置 ───────────────────────────────────────────────────────────────
COURSERA_API_BASE = "https://api.coursera.org/api"
EDX_API_BASE      = "https://www.edx.org/api/catalog/v2"
MOOC_CN_BASE      = "https://www.icourse163.org"

# ── 每个平台最大爬取数量 ───────────────────────────────────────────────────────
MAX_COURSES = {
    "coursera":  2000,
    "edx":       1000,
    "mooc_cn":   2000,
}
