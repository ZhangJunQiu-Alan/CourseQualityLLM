"""
反爬虫检测工具
- 随机 User-Agent 轮换
- 随机请求延迟
- 代理 IP 池轮换
- 请求头伪装
"""
import random
import time
import itertools
from typing import Optional
from config import DELAY_MIN, DELAY_MAX, PROXY_LIST

# 常见桌面浏览器 UA 池（定期更新）
_USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

# 代理池循环迭代器
_proxy_cycle = itertools.cycle(PROXY_LIST) if PROXY_LIST else None


def random_ua() -> str:
    """随机返回一个 User-Agent 字符串"""
    return random.choice(_USER_AGENTS)


def random_delay(extra_factor: float = 1.0) -> None:
    """随机等待，模拟人类浏览间隔"""
    delay = random.uniform(DELAY_MIN, DELAY_MAX) * extra_factor
    time.sleep(delay)


def get_proxy() -> Optional[dict]:
    """从代理池轮换取一个代理，若池为空则返回 None"""
    if _proxy_cycle is None:
        return None
    proxy_url = next(_proxy_cycle)
    return {"http": proxy_url, "https": proxy_url}


def build_headers(referer: str = "", extra: Optional[dict] = None) -> dict:
    """
    构造伪装请求头
    - 随机 UA
    - 常见浏览器请求头字段
    - 可选 Referer
    """
    headers = {
        "User-Agent": random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    }
    if referer:
        headers["Referer"] = referer
    if extra:
        headers.update(extra)
    return headers


def build_api_headers(origin: str = "", extra: Optional[dict] = None) -> dict:
    """构造 API 请求头（JSON 格式）"""
    headers = {
        "User-Agent": random_ua(),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    if origin:
        headers["Origin"] = origin
        headers["Referer"] = origin + "/"
    if extra:
        headers.update(extra)
    return headers
