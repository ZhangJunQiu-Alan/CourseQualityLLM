"""
爬虫基类
- 统一重试逻辑
- 代理轮换
- 限速
- 进度跟踪
"""
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from utils.anti_detect import build_api_headers, build_headers, random_delay, get_proxy
from config import MAX_RETRIES, TIMEOUT


class BaseScraper:
    PLATFORM = "base"

    def __init__(self):
        self.session = requests.Session()

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=4, max=30),
        retry=retry_if_exception_type((requests.RequestException, requests.Timeout)),
    )
    def get(self, url: str, params: dict = None, is_api: bool = True,
            referer: str = "", delay: bool = True) -> requests.Response:
        """
        发起 GET 请求，内置重试 + 代理 + UA 轮换
        delay=False → 跳过随机延迟（适合同一门课的多个子请求）
        """
        headers = build_api_headers(extra={}) if is_api else build_headers(referer=referer)
        proxy   = get_proxy()

        if delay:
            random_delay()

        resp = self.session.get(
            url,
            headers=headers,
            params=params,
            proxies=proxy,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp

    def log(self, msg: str) -> None:
        safe = f"[{self.PLATFORM}] {msg}".encode("gbk", errors="replace").decode("gbk")
        print(safe, flush=True)
