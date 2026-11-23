import asyncio
from contextlib import contextmanager
from decimal import Decimal
import json
import logging
import os
import random
import re
import tempfile
import threading
import time
from typing import Any, Iterator, Optional
from urllib.parse import urljoin
import aiohttp
from bs4 import BeautifulSoup

from package.models.kenbiya import (
    KenbiyaInvestmentApartment,
    KenbiyaInvestmentBuilding,
    KenbiyaMansion,
    KenbiyaKodate,
    KenbiyaTochi,
)
from package.parser.baseParser import (
    ParserBase,
    ListItem,
    InvestmentParserBase,
    MansionParserBase,
    KodateParserBase,
    TochiParserBase,
    ListingEndedException,
    ServerBusyException,
    LoadPropertyPageException,
    ServerDownException,
    RateLimitedException,
)
from package.utils import converter

# SonarCloud S1192: Centralized string literal constants
INFO_GUIDE = "情報の見方"
INQUIRY_TEXT = "問い合わせる"
STRUCTURE_FLOOR = "建物構造/階数"
STRUCTURE_TEXT = "建物構造"
KENPEI_YOUSEKI_SLASH = "建ぺい/容積率"
KENPEI_YOUSEKI_FULL = "建ぺい率/容積率"
SOUKOSU_REGEX = r"総戸数(\d+)戸"
RATE_LIMITED_KENBIYA_PREFIX = "Rate limited (429) on Kenbiya: "
KENBIYA_HOME_URL = "https://www.kenbiya.com/"
_KENBIYA_RATIO_SPLIT_RE = re.compile(r"[／/・]")
_KENBIYA_MAGUCHI_RE = re.compile(
    r"(?:間口|接面)[\s：:約]{0,8}(\d{1,5}(?:\.\d{1,3})?)\s{0,3}[mｍ米]?"
)
_KENBIYA_WIDTH_LABEL_RE = re.compile(
    r"(?:道路幅員|幅員|幅)[\s：:約]{0,8}(\d{1,4}(?:\.\d{1,3})?)\s{0,3}[mｍ米]?"
)
_KENBIYA_WIDTH_DIR_RE = re.compile(
    r"(?:北東|北西|南東|南西|[北南東西])側?[\s：:約公私道]{0,10}(\d{1,4}(?:\.\d{1,3})?)\s{0,3}[mｍ米]"
)


class KenbiyaParserBase(ParserBase):
    """
    健美家 (Kenbiya) 全種別共通基底パーサー
    共通HTTP通信、429対策ヘッダー、dl > dt / dd パースロジックを集約
    """

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    ]
    _ua_counter = 0

    @classmethod
    def _get_next_user_agent(cls) -> str:
        ua = KenbiyaParserBase.USER_AGENTS[
            KenbiyaParserBase._ua_counter % len(KenbiyaParserBase.USER_AGENTS)
        ]
        KenbiyaParserBase._ua_counter += 1
        return ua

    def getCharset(self):
        return "utf-8"

    async def _handle_response(
        self,
        response: aiohttp.ClientResponse,
        url: str,
        attempt: int,
        max_timeouts: int,
    ) -> Optional[bytes]:
        status = response.status
        if status == 200:
            self.consecutive_timeouts = 0
            return await response.read()
        if status in (404, 410):
            raise ListingEndedException(
                f"Property page returned HTTP status {status}: {url}"
            )
        if status in (500, 502, 503, 504):
            if status == 503 and await self._handle_503_with_pppoe_recovery(url):
                return None
            raise ServerBusyException(
                f"Property page returned HTTP status {status}: {url}"
            )
        if status == 429:
            backoff = min(30, 2 ** (attempt + 1))
            logging.warning(
                f"{RATE_LIMITED_KENBIYA_PREFIX}{url}. Backing off {backoff}s"
            )
            if attempt == max_timeouts - 1:
                raise RateLimitedException(f"{RATE_LIMITED_KENBIYA_PREFIX}{url}")
            await asyncio.sleep(backoff)
            return None
        raise LoadPropertyPageException(f"Failed to fetch {url} with status {status}")

    _request_lock = threading.Lock()
    _last_request_time: float = 0.0

    @classmethod
    def get_proxy_url(cls) -> str | None:
        """健美家専用Proxy設定、または住宅用Proxy共通設定からURLを取得（未設定時はNone）"""
        return os.getenv("KENBIYA_PROXY_URL") or os.getenv("RESIDENTIAL_PROXY_URL") or None

    @classmethod
    def _build_playwright_proxy_config(cls) -> dict[str, str] | None:
        """Playwright用プロキシ設定辞書を構築（認証情報含む）"""
        raw_proxy = cls.get_proxy_url()
        if not raw_proxy:
            return None
        from urllib.parse import urlparse
        parsed = urlparse(raw_proxy)
        if not parsed.hostname:
            return None
        server = f"{parsed.scheme or 'http'}://{parsed.hostname}"
        if parsed.port:
            server += f":{parsed.port}"
        cfg: dict[str, str] = {"server": server}
        if parsed.username:
            cfg["username"] = parsed.username
        if parsed.password:
            cfg["password"] = parsed.password
        return cfg

    @classmethod
    def _get_rate_limit_state_path(cls) -> str:
        return os.getenv(
            "KENBIYA_RATE_LIMIT_STATE_FILE",
            os.path.join(tempfile.gettempdir(), "kenbiya_rate_limit.json"),
        )

    @classmethod
    def _is_cross_process_coordination_enabled(cls) -> bool:
        if os.getenv("KENBIYA_THROTTLE_DISABLED", "false").lower() in ("true", "1"):
            return False
        if os.getenv("KENBIYA_CROSS_PROCESS_LOCK_DISABLED", "false").lower() in (
            "true",
            "1",
        ):
            return False
        if os.getenv("PYTEST_CURRENT_TEST") and not os.getenv(
            "KENBIYA_RATE_LIMIT_STATE_FILE"
        ):
            return False
        return True

    @staticmethod
    def _try_lock_handle(fh: Any) -> bool:
        try:
            if os.name == "nt":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    @staticmethod
    def _try_unlock_handle(fh: Any) -> None:
        try:
            if os.name == "nt":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass

    @classmethod
    @contextmanager
    def _acquire_file_lock(cls, lock_path: str, timeout: float = 5.0) -> Iterator[None]:
        os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
        fh = open(lock_path, "a+b")
        locked = False
        deadline = time.monotonic() + timeout
        try:
            while not locked:
                locked = cls._try_lock_handle(fh)
                if locked or time.monotonic() >= deadline:
                    break
                time.sleep(0.02)
            yield
        finally:
            if locked:
                cls._try_unlock_handle(fh)
            fh.close()

    @classmethod
    def _read_shared_state(cls, state_path: str) -> dict[str, Any]:
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    raw_ts = data.get("request_timestamps", [])
                    timestamps = [
                        float(t) for t in raw_ts if isinstance(t, (int, float))
                    ]
                    return {
                        "last_request_time": float(data.get("last_request_time", 0.0)),
                        "circuit_open_until": float(data.get("circuit_open_until", 0.0)),
                        "rotating_until": float(data.get("rotating_until", 0.0)),
                        "request_timestamps": timestamps,
                        "total_requests": int(data.get("total_requests", 0)),
                    }
        except (OSError, ValueError, TypeError):
            pass
        return {
            "last_request_time": 0.0,
            "circuit_open_until": 0.0,
            "rotating_until": 0.0,
            "request_timestamps": [],
            "total_requests": 0,
        }

    @classmethod
    def _write_shared_state(cls, state_path: str, state: dict[str, Any]) -> None:
        try:
            os.makedirs(os.path.dirname(state_path) or ".", exist_ok=True)
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state, f)
        except OSError as e:
            logging.debug(f"Failed to write Kenbiya shared rate-limit state: {e}")

    @classmethod
    async def _rotate_pppoe_ip(
        cls, trigger_url: str, wait_sec: float, state_path: str, lock_path: str
    ) -> None:
        """503検知時のIPローテーション: wan_pppoeを切断し指定時間スリープ後に再接続する（プロセスは維持）"""
        try:
            from package.api.kenbiya import _run_router_ssh

            logging.warning(
                f"[Kenbiya503Recovery] HTTP 503 detected ({trigger_url}); disconnecting wan_pppoe and sleeping {wait_sec:.0f}s..."
            )
            _run_router_ssh("ifdown wan_pppoe")
            if wait_sec > 0:
                await asyncio.sleep(wait_sec)
            logging.info(
                "[Kenbiya503Recovery] Reconnecting wan_pppoe and reloading routing to resume..."
            )
            _run_router_ssh("ifup wan_pppoe; sleep 5; /etc/init.d/vpn-policy-routing reload")
            KenbiyaParserBase._waf_cookies = {}
        except Exception as exc:
            logging.warning(
                f"[Kenbiya503Recovery] PPPoE rotation failed: {exc}"
            )
        finally:
            with KenbiyaParserBase._request_lock, cls._acquire_file_lock(lock_path):
                state = cls._read_shared_state(state_path)
                state["rotating_until"] = 0.0
                state["last_request_time"] = time.time()
                state["request_timestamps"] = []
                cls._write_shared_state(state_path, state)

    @classmethod
    async def _handle_503_with_pppoe_recovery(cls, url: str) -> bool:
        """HTTP 503受信時にプロセスを終了せず、PPPoE解放・指定時間スリープ・再接続で復旧する。
        復旧を実行・待機した場合はTrue（呼び出し元で同一URLをリトライ）、無効時はFalseを返す。
        """
        if not cls._is_cross_process_coordination_enabled():
            return False
        if os.getenv("KENBIYA_503_PPPOE_RECOVERY_DISABLED", "false").lower() in (
            "true",
            "1",
        ):
            return False
        try:
            wait_sec = float(os.getenv("KENBIYA_PPPOE_ROTATE_WAIT_SEC", "1200"))
        except ValueError:
            wait_sec = 1200.0
        state_path = cls._get_rate_limit_state_path()
        lock_path = f"{state_path}.lock"
        should_rotate = False
        sleep_duration = 0.0

        with KenbiyaParserBase._request_lock, cls._acquire_file_lock(lock_path):
            now_wall = time.time()
            state = cls._read_shared_state(state_path)
            rotating_until = state.get("rotating_until", 0.0)
            if rotating_until > now_wall:
                sleep_duration = rotating_until - now_wall
            else:
                should_rotate = True
                state["rotating_until"] = now_wall + wait_sec + 15.0
                state["last_request_time"] = state["rotating_until"]
                state["request_timestamps"] = []
                cls._write_shared_state(state_path, state)

        if should_rotate:
            await cls._rotate_pppoe_ip(url, wait_sec, state_path, lock_path)
        elif sleep_duration > 0:
            logging.info(
                f"[Kenbiya503Recovery] Another process is rotating wan_pppoe; sleeping {sleep_duration:.1f}s before resuming ({url})"
            )
            await asyncio.sleep(sleep_duration)
        return True

    @classmethod
    def _disconnect_pppoe_on_503(cls, url: str) -> None:
        """503停止時にルーターの wan_pppoe を切断する（IPローテーション・過負荷保護）"""
        if os.getenv("KENBIYA_503_PPPOE_DISCONNECT_DISABLED", "false").lower() in (
            "true",
            "1",
        ):
            return
        try:
            from package.api.kenbiya import _run_router_ssh

            logging.warning(
                f"[Kenbiya503Circuit] Disconnecting wan_pppoe due to HTTP 503 ({url})"
            )
            _run_router_ssh("ifdown wan_pppoe")
        except Exception as exc:
            logging.warning(
                f"[Kenbiya503Circuit] Failed to disconnect wan_pppoe on 503: {exc}"
            )

    @classmethod
    def _record_503_circuit_open(cls, url: str) -> None:
        """HTTP 503検知時に全プロセス共通のクールダウン時刻を記録し、wan_pppoeを切断する"""
        if not cls._is_cross_process_coordination_enabled():
            return
        try:
            cooldown_sec = float(os.getenv("KENBIYA_503_CIRCUIT_COOLDOWN_SEC", "120"))
        except ValueError:
            cooldown_sec = 120.0
        if cooldown_sec <= 0:
            return
        state_path = cls._get_rate_limit_state_path()
        lock_path = f"{state_path}.lock"
        now_wall = time.time()
        open_until = now_wall + cooldown_sec
        should_disconnect = False
        with KenbiyaParserBase._request_lock, cls._acquire_file_lock(lock_path):
            state = cls._read_shared_state(state_path)
            prev_open_until = state.get("circuit_open_until", 0.0)
            if prev_open_until <= now_wall:
                should_disconnect = True
            state["circuit_open_until"] = max(prev_open_until, open_until)
            cls._write_shared_state(state_path, state)
        logging.warning(
            f"[Kenbiya503Circuit] Opened shared 503 circuit breaker for {cooldown_sec:.0f}s (trigger: {url})"
        )
        if should_disconnect:
            cls._disconnect_pppoe_on_503(url)

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        try:
            return int(os.getenv(name, str(default)))
        except ValueError:
            return default

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        try:
            return float(os.getenv(name, str(default)))
        except ValueError:
            return default

    @classmethod
    def _compute_shared_throttle_delay(
        cls, state: dict[str, Any], now_wall: float, min_interval: float, jitter: float
    ) -> float:
        circuit_open_until = state.get("circuit_open_until", 0.0)
        if circuit_open_until > now_wall:
            remaining = circuit_open_until - now_wall
            raise ServerBusyException(
                f"Kenbiya shared 503 circuit breaker active ({remaining:.1f}s remaining)"
            )
        rotating_until = state.get("rotating_until", 0.0)
        if rotating_until > now_wall:
            return rotating_until - now_wall

        last_wall = state.get("last_request_time", 0.0)
        target_wall = max(now_wall, last_wall + min_interval + jitter)

        max_rpm = cls._env_int("KENBIYA_GLOBAL_MAX_RPM", 20)
        window_start = target_wall - 60.0
        recent_ts = [t for t in state.get("request_timestamps", []) if t > window_start]
        if max_rpm > 0 and len(recent_ts) >= max_rpm:
            oldest_in_window = recent_ts[len(recent_ts) - max_rpm]
            target_wall = max(
                target_wall, oldest_in_window + 60.0 + random.uniform(0.5, 1.5)
            )

        total_requests = int(state.get("total_requests", 0)) + 1
        pause_every = cls._env_int("KENBIYA_LONG_PAUSE_EVERY", 40)
        if pause_every > 0 and total_requests % pause_every == 0:
            pause_sec = cls._env_float("KENBIYA_LONG_PAUSE_SEC", 15.0)
            if pause_sec > 0:
                target_wall += pause_sec + random.uniform(0.0, 5.0)

        recent_ts.append(target_wall)
        state["request_timestamps"] = recent_ts[-200:]
        state["total_requests"] = total_requests
        state["last_request_time"] = target_wall
        return target_wall - now_wall

    @classmethod
    async def _throttle_before_request(cls) -> None:
        """リクエスト送信間隔を全プロセス共通のファイルロックで担保し、503サーキットブレーカーを共有する"""
        if os.getenv("KENBIYA_THROTTLE_DISABLED", "false").lower() in ("true", "1"):
            return
        min_interval = cls._env_float("KENBIYA_MIN_INTERVAL", 1.0)
        jitter = random.uniform(1.5, 2.5)

        if cls._is_cross_process_coordination_enabled():
            state_path = cls._get_rate_limit_state_path()
            lock_path = f"{state_path}.lock"
            with KenbiyaParserBase._request_lock, cls._acquire_file_lock(lock_path):
                state = cls._read_shared_state(state_path)
                sleep_duration = cls._compute_shared_throttle_delay(
                    state, time.time(), min_interval, jitter
                )
                cls._write_shared_state(state_path, state)
            if sleep_duration > 0:
                await asyncio.sleep(sleep_duration)
            return

        with KenbiyaParserBase._request_lock:
            now = time.monotonic()
            target_time = max(
                now, KenbiyaParserBase._last_request_time + min_interval + jitter
            )
            sleep_duration = target_time - now
            KenbiyaParserBase._last_request_time = target_time
        if sleep_duration > 0:
            await asyncio.sleep(sleep_duration)

    @staticmethod
    async def _goto_with_home_warmup(page: Any, url: str) -> None:
        if url.rstrip("/") != KENBIYA_HOME_URL.rstrip("/"):
            await page.goto(KENBIYA_HOME_URL, wait_until="domcontentloaded", timeout=20000)
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)

    async def _fetch_with_playwright(self, url: str) -> bytes:
        from playwright.async_api import async_playwright

        logging.info(f"Kenbiya Playwright fallback fetching: {url}")
        pw_proxy = self._build_playwright_proxy_config()
        launch_kwargs: dict[str, Any] = {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        }
        if pw_proxy:
            launch_kwargs["proxy"] = pw_proxy
            logging.info("Kenbiya Playwright launched with residential proxy")

        async with async_playwright() as p:
            browser = await p.chromium.launch(**launch_kwargs)
            try:
                context = await browser.new_context(
                    user_agent=self._get_next_user_agent(),
                    viewport={"width": 1920, "height": 1080},
                    locale="ja-JP",
                    timezone_id="Asia/Tokyo",
                )
                try:
                    await context.add_init_script(
                        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
                    )
                    page = await context.new_page()

                    # ギガ浪費防止・高速化: 画像、フォント、メディア、スタイルシート等の不要アセットをルート遮断 (Issue #1484, #1486)
                    STATIC_ASSET_PATTERN = re.compile(
                        r"\.(png|jpg|jpeg|gif|webp|svg|ico|css|woff2?|ttf|eot)(\?.*)?$",
                        re.IGNORECASE,
                    )

                    async def _block_unnecessary_resources(route):
                        req = route.request
                        res_type = getattr(req, "resource_type", "")
                        req_url = getattr(req, "url", "")
                        if res_type in {"image", "media", "font", "stylesheet", "other"} or isinstance(req_url, str) and STATIC_ASSET_PATTERN.search(req_url):
                            await route.abort()
                        else:
                            await route.continue_()

                    await page.route(
                        STATIC_ASSET_PATTERN,
                        _block_unnecessary_resources,
                    )
                    try:
                        await self._goto_with_home_warmup(page, url)
                        await page.wait_for_timeout(1500)
                        content_str = await page.content()
                        return content_str.encode("utf-8")
                    finally:
                        await page.close()
                finally:
                    await context.close()
            finally:
                await browser.close()

    async def _try_playwright_on_403(
        self, session: aiohttp.ClientSession, status: int, url: str
    ) -> bytes | None:
        if status not in (403, 429) or not isinstance(session, aiohttp.ClientSession):
            return None
        try:
            pw_bytes = await self._fetch_with_playwright(url)
            if pw_bytes and b"403 Forbidden" not in pw_bytes[:512] and b"429 Too Many Requests" not in pw_bytes[:512]:
                return pw_bytes
        except Exception as pw_err:
            logging.warning(f"Kenbiya Playwright fallback failed for {url}: {pw_err}")
        return None

    async def _handle_response_or_403(
        self,
        session: aiohttp.ClientSession,
        response: aiohttp.ClientResponse,
        url: str,
        attempt: int,
        max_timeouts: int,
    ) -> Optional[bytes]:
        if response.status in (403, 429):
            pw_content = await self._try_playwright_on_403(session, response.status, url)
            if pw_content is not None:
                return pw_content
            if response.status == 403:
                raise ServerBusyException(f"Kenbiya WAF/403 blocked: {url}")
        return await self._handle_response(response, url, attempt, max_timeouts)

    _waf_cookies: dict[str, str] = {}
    _waf_user_agent: str | None = None

    @classmethod
    async def _warmup_waf_cookies(cls, force: bool = False) -> None:
        """実 Chrome で WAF 通過済み Cookie と User-Agent を取得・キャッシュする。"""
        if os.getenv("KENBIYA_WAF_WARMUP_DISABLED", "false").lower() in ("true", "1"):
            return
        if cls._waf_cookies and not force:
            return
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    channel="chrome",
                    headless=False,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                try:
                    context = await browser.new_context()
                    page = await context.new_page()
                    await page.add_init_script(
                        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                    )
                    await page.goto(KENBIYA_HOME_URL, timeout=15000)
                    ua = await page.evaluate("navigator.userAgent")
                    cookies = {c["name"]: c["value"] for c in await context.cookies()}
                    if cookies:
                        cls._waf_cookies = cookies
                    if ua:
                        cls._waf_user_agent = ua
                finally:
                    await browser.close()
        except Exception as e:
            logging.warning(f"Kenbiya WAF cookie warmup skipped: {e}")

    _IMPERSONATE_PROFILES = (
        "edge99", "edge101",
        "chrome110", "chrome116", "chrome119", "chrome120", "chrome123", "chrome124",
        "chrome131", "chrome133a", "chrome136", "chrome142", "chrome145", "chrome146",
        "safari15_3", "safari15_5", "safari17_0", "safari18_0", "safari184",
        "firefox133", "firefox135", "firefox144", "firefox147",
    )
    _ACCEPT_LANGUAGES = (
        "ja,en-US;q=0.9,en;q=0.8",
        "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
        "ja;q=1.0,en;q=0.5",
        "ja-JP,ja;q=0.9",
        "ja,en;q=0.9,en-US;q=0.8",
        "ja-JP,en-US;q=0.9,en;q=0.8",
        "ja;q=0.9,en-US;q=0.8,en;q=0.7",
        "ja-JP,ja;q=0.8,en-US;q=0.6,en;q=0.4",
    )

    _REFERERS = (
        KENBIYA_HOME_URL,
        "https://www.kenbiya.com/pp1/",
        "https://www.kenbiya.com/pp8/",
        "https://www.google.co.jp/",
        "https://www.google.com/",
    )
    _ACCEPT_ENCODINGS = (
        "gzip, deflate, br, zstd",
        "gzip, deflate, br",
        "gzip, deflate",
    )

    _session_impersonate: str | None = None
    _session_accept_language: str | None = None

    async def _get_with_curl_cffi(
        self, url: str, headers: dict[str, str], proxy_url: str | None
    ) -> tuple[int, bytes]:
        from curl_cffi.requests import AsyncSession

        await self._warmup_waf_cookies()
        if KenbiyaParserBase._session_impersonate is None:
            KenbiyaParserBase._session_impersonate = os.getenv(
                "KENBIYA_IMPERSONATE"
            ) or random.choice(self._IMPERSONATE_PROFILES)
        if KenbiyaParserBase._session_accept_language is None:
            KenbiyaParserBase._session_accept_language = random.choice(
                self._ACCEPT_LANGUAGES
            )
        impersonate = os.getenv("KENBIYA_IMPERSONATE") or KenbiyaParserBase._session_impersonate
        req_headers = dict(headers)
        req_headers.setdefault("Accept-Language", KenbiyaParserBase._session_accept_language)
        req_headers.setdefault("Accept-Encoding", random.choice(self._ACCEPT_ENCODINGS))
        req_headers.setdefault("Referer", random.choice(self._REFERERS))
        req_headers.setdefault("DNT", "1")
        req_headers.setdefault("Upgrade-Insecure-Requests", "1")
        if self._waf_user_agent:
            req_headers["User-Agent"] = self._waf_user_agent
        async with AsyncSession(impersonate=impersonate) as cffi_session:
            req_kwargs: dict[str, Any] = {
                "headers": req_headers,
                "timeout": 15,
            }
            if self._waf_cookies:
                req_kwargs["cookies"] = dict(self._waf_cookies)
            if proxy_url:
                req_kwargs["proxy"] = proxy_url
            resp = await cffi_session.get(url, **req_kwargs)
            return resp.status_code, resp.content

    async def _handle_curl_cffi_response(
        self, last_status: int, raw_bytes: bytes, url: str
    ) -> bytes | None:
        if last_status == 200:
            self.consecutive_timeouts = 0
            return raw_bytes
        if last_status == 403:
            KenbiyaParserBase._waf_cookies = {}
            pw_content = await self._fetch_with_playwright(url)
            if pw_content is not None:
                return pw_content
        if last_status == 404:
            raise ListingEndedException(f"Listing ended (404): {url}")
        if last_status == 429:
            KenbiyaParserBase._waf_cookies = {}
            await asyncio.sleep(3)
            return None
        if last_status in (500, 502, 503, 504):
            if last_status == 503 and await self._handle_503_with_pppoe_recovery(url):
                return None
            raise ServerBusyException(f"HTTP {last_status} for {url}")
        raise LoadPropertyPageException(f"HTTP {last_status} for {url}")

    async def _get_with_aiohttp(
        self,
        session: aiohttp.ClientSession,
        url: str,
        headers: dict[str, str],
        proxy_url: str | None,
        attempt: int,
        max_timeouts: int,
    ) -> tuple[int, bytes | None]:
        get_kwargs: dict[str, Any] = {
            "headers": headers,
            "timeout": aiohttp.ClientTimeout(total=15),
        }
        if proxy_url:
            get_kwargs["proxy"] = proxy_url
        last_status: int | None = None
        content: bytes | None = None
        async with session.get(url, **get_kwargs) as response:
            last_status = response.status
            content = await self._handle_response_or_403(
                session, response, url, attempt, max_timeouts
            )
        return last_status, content

    async def _getContent(self, session: aiohttp.ClientSession, url: str) -> bytes:
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }
        max_timeouts = getattr(self, "MAX_CONSECUTIVE_TIMEOUTS", 3)
        last_status = None
        proxy_url = self.get_proxy_url()
        import importlib.util

        use_curl_cffi = (
            type(session) is aiohttp.ClientSession
            and os.getenv("KENBIYA_USE_CURL_CFFI", "true").lower() in ("true", "1")
            and importlib.util.find_spec("curl_cffi") is not None
        )
        for attempt in range(max_timeouts):
            headers["User-Agent"] = self._get_next_user_agent()
            await self._throttle_before_request()
            try:
                if use_curl_cffi:
                    last_status, raw_bytes = await self._get_with_curl_cffi(
                        url, headers, proxy_url
                    )
                    content = await self._handle_curl_cffi_response(
                        last_status, raw_bytes, url
                    )
                else:
                    last_status, content = await self._get_with_aiohttp(
                        session, url, headers, proxy_url, attempt, max_timeouts
                    )
                if content is not None:
                    return content
            except (
                RateLimitedException,
                ListingEndedException,
                ServerBusyException,
                LoadPropertyPageException,
                ServerDownException,
            ):
                raise
            except (aiohttp.ClientError, OSError) as e:
                self.consecutive_timeouts = getattr(self, "consecutive_timeouts", 0) + 1
                if self.consecutive_timeouts >= max_timeouts:
                    raise ServerDownException(
                        f"Kenbiya server unresponsive after {self.consecutive_timeouts} consecutive timeouts: {e}"
                    )
                await asyncio.sleep(1)
        if last_status == 429:
            raise RateLimitedException(f"{RATE_LIMITED_KENBIYA_PREFIX}{url}")
        raise LoadPropertyPageException(f"Exceeded max retries for {url}")

    BASE_URL = "https://www.kenbiya.com"

    async def parsePropertyListPage(self, response: BeautifulSoup):
        detail_links = set()
        for a in response.find_all("a", href=re.compile(r"/pp\d+/.*?/re_\w+/")):
            raw_href = a.get("href")
            if not raw_href:
                continue
            href = raw_href[0] if isinstance(raw_href, list) else str(raw_href)
            full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
            if full_url not in detail_links:
                detail_links.add(full_url)
                price = self._extract_card_price(a)
                yield ListItem(url=full_url, price=price)

    def _find_next_by_text(self, response: BeautifulSoup) -> str:
        for a in response.find_all("a"):
            if a is None:
                continue
            text = a.get_text(strip=True)
            if ("次へ" in text or "次のページ" in text or text == ">") and a.has_attr(
                "href"
            ):
                href = str(a["href"])
                return urljoin(self.BASE_URL, href)
        return ""

    async def parseNextPage(self, response: BeautifulSoup):
        # ページネーション: li.next a, a[rel="next"], または「次へ」リンク
        next_tag = response.select_one('li.next a, a[rel="next"], a.next')
        if next_tag is not None:
            href = next_tag.get("href")
            if href:
                return urljoin(self.BASE_URL, str(href))
        return self._find_next_by_text(response)

    async def parseRootPage(self, response: BeautifulSoup):
        yielded = 0
        async for item in self.parsePropertyListPage(response):
            yielded += 1
            yield item
        if yielded == 0:
            raise ServerBusyException(
                "Kenbiya root page returned 0 items (WAF/blocked)"
            )

    @staticmethod
    def _clean_spec_value(text: str) -> str:
        """項目の見方・用語解説などのヘルプ文を除去または除外してスペック値を返す"""
        if not text:
            return ""
        clean = text.strip()
        # 1. ヘルプリンク付加テキスト（情報の見方を表示 等）を除去
        for link_word in ["情報の見方を表示", "見方を表示", "マークを表示"]:
            for pattern in [f"({link_word})", f"（{link_word}）", link_word]:
                clean = clean.replace(pattern, "").strip()
        # 2. 説明文そのものである場合は空文字を返す（スペック値ではない）
        if clean.endswith(("を表示。", "を表示", "マークを表示")):
            return ""
        return clean

    @staticmethod
    def _is_excluded_spec_container(elem) -> bool:
        """用語解説・ガイド領域（box_outline, guide, help, glossary 等）配下かを判定"""
        for parent in elem.parents:
            if not parent or not hasattr(parent, "get"):
                continue
            p_classes = " ".join(parent.get("class", []) or [])
            p_id = parent.get("id", "") or ""
            if (
                any(
                    k in p_classes
                    for k in ["guide", "help", "glossary", "explanation", "box_outline"]
                )
                or "guide" in p_id
            ):
                return True
        return False

    def _parse_dl_specs(self, response: Any, specs: dict) -> None:
        for dl in response.find_all("dl"):
            if self._is_excluded_spec_container(dl):
                continue
            for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
                key = dt.get_text(strip=True)
                val = dd.get_text(" ", strip=True)
                cleaned_val = self._clean_spec_value(val)
                if key and cleaned_val and key not in specs:
                    specs[key] = cleaned_val

    def _parse_tr_specs(self, response: Any, specs: dict) -> None:
        for tr in response.find_all("tr"):
            parent = tr.find_parent("table")
            if parent and self._is_excluded_spec_container(parent):
                continue
            th, td = tr.find("th"), tr.find("td")
            if th and td:
                key = th.get_text(strip=True)
                val = td.get_text(" ", strip=True)
                cleaned_val = self._clean_spec_value(val)
                if key and cleaned_val and key not in specs:
                    specs[key] = cleaned_val

    def _get_specs(self, response: BeautifulSoup) -> dict:
        """dl > dt / dd または table から key-value スペック辞書を構築"""
        specs = {}
        if not response:
            return specs
        # 正規スペック領域 (div.property) があれば優先して走査
        property_container = response.select_one("div.property")
        if property_container:
            self._parse_dl_specs(property_container, specs)
            self._parse_tr_specs(property_container, specs)
        self._parse_dl_specs(response, specs)
        self._parse_tr_specs(response, specs)
        return specs

    # 共通パースメソッド群
    def _extract_fallback_price_raw(self, response: BeautifulSoup) -> str:
        if not response:
            return ""
        # 対象物件の詳細領域 (div.property, #property_detail 等) を特定して探索
        container = response.select_one(
            "div.property, #property_detail, .property-header, .property_detail"
        )
        if not container:
            return ""
        price_el = container.select_one(
            ".price, .mod-price, span.price, .property_price, em.price"
        )
        return price_el.get_text(strip=True) if price_el else ""

    def _parsePrice(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = specs.get("価格", "")
        if not raw and response:
            raw = self._extract_fallback_price_raw(response)
        return converter.parse_price(raw)

    def _parsePriceStr(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = specs.get("価格", "")
        if not raw and response:
            raw = self._extract_fallback_price_raw(response)
        return raw

    def _parseAddress(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = specs.get("住所", "") or specs.get("所在地", "")
        for noise in ["地図", "周辺環境", "周辺地図"]:
            raw = raw.replace(noise, "").strip()
        return raw

    def _parsePropertyName(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        name = specs.get("物件名", "") or specs.get("名称", "")
        if not name:
            title = response.find("title")
            if title:
                title_text = title.get_text(strip=True)
                name = (
                    title_text.split("｜")[0].strip()
                    if "｜" in title_text
                    else title_text
                )
        return name

    def _parseTransport1(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        return (
            specs.get("交通", "")
            or specs.get("アクセス", "")
            or specs.get("最寄駅", "")
        )

    def _parseRights(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("土地権利", "")

    def _parseSetsudou(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("接道状況", "")

    def _parseYoutoChiiki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("用途地域", "")

    def _parseCurrentStatus(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        status = specs.get("現況", "") or specs.get("入居状況", "")
        for noise in ["入居状況を問い合わせる", INFO_GUIDE]:
            status = status.replace(noise, "").strip()
        return status

    def _parseGenkyo(self, response: BeautifulSoup, specs=None):
        return self._parseCurrentStatus(response, specs)

    def _parseHikiwatashi(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("引渡", "")

    def _parseChimoku(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        return specs.get("地目", "")

    def _parseGrossYield(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = (
            specs.get("満室時利回り", "")
            or specs.get("表面利回り", "")
            or specs.get("利回り", "")
        )
        for noise in ["利回りの詳細を問い合わせる", INFO_GUIDE]:
            raw = raw.replace(noise, "").strip()
        return converter.parse_ratio(raw)

    def _parseAnnualRent(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        rent_str = (
            specs.get("満室時年収/月収", "")
            or specs.get("満室時年収", "")
            or specs.get("想定年収", "")
        )
        if "/" in rent_str:
            annual_part = rent_str.split("/")[0].strip()
        else:
            annual_part = rent_str
        for noise in [INFO_GUIDE, INQUIRY_TEXT]:
            annual_part = annual_part.replace(noise, "").strip()
        return converter.parse_price(annual_part)

    def _parseMonthlyRent(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        rent_str = specs.get("満室時年収/月収", "")
        if "/" in rent_str:
            monthly_part = rent_str.split("/")[1].strip()
            for noise in [INFO_GUIDE, INQUIRY_TEXT]:
                monthly_part = monthly_part.replace(noise, "").strip()
            val = converter.parse_price(monthly_part)
            if val:
                return val
        annual = self._parseAnnualRent(response, specs)
        return int(annual / 12) if annual else None

    def _parseChikunengetsu(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = specs.get("築年月", "")
        return converter.parse_chikunengetsu(raw)

    def _parseKouzou(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        kouzou = (
            specs.get(STRUCTURE_FLOOR, "")
            or specs.get(STRUCTURE_TEXT, "")
            or specs.get("構造", "")
        )
        if "総戸数" in kouzou:
            kouzou = kouzou.split("総戸数")[0]
        return kouzou.strip()

    def _parseTochiMenseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = specs.get("土地面積", "")
        return converter.parse_menseki(raw)

    def _parseTatemonoMenseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = specs.get("建物面積", "") or specs.get("延床面積", "")
        return converter.parse_menseki(raw)

    def _parseKenpei(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = self._extract_kenpei_from_specs(specs) or specs.get(
            KENPEI_YOUSEKI_SLASH, ""
        )
        return converter.parse_ratio(raw)

    def _parseYouseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        raw = self._extract_youseki_from_specs(specs) or specs.get(
            KENPEI_YOUSEKI_SLASH, ""
        )
        if raw and _KENBIYA_RATIO_SPLIT_RE.search(raw):
            parts = _KENBIYA_RATIO_SPLIT_RE.split(raw)
            if len(parts) >= 2:
                return converter.parse_ratio(parts[1])
        return converter.parse_ratio(raw)

    def _parseMaguchi(self, response: BeautifulSoup, specs=None) -> Optional[Decimal]:
        specs = specs or self._get_specs(response)
        direct = specs.get("間口", "") or specs.get("接面", "")
        if direct:
            parsed = self._extract_maguchi_decimal(direct, allow_bare_meter=True)
            if parsed is not None:
                return parsed
        setsudou_val = (
            specs.get("接道状況", "")
            or specs.get("道路付け", "")
            or specs.get("接道", "")
        )
        if setsudou_val:
            m = _KENBIYA_MAGUCHI_RE.search(setsudou_val)
            if m:
                return Decimal(m.group(1))
        return None

    def _parseRoadWidth(self, response: BeautifulSoup, specs=None) -> Optional[Decimal]:
        specs = specs or self._get_specs(response)
        for k in ("道路幅員", "幅員", "道路幅"):
            direct = specs.get(k, "")
            if direct:
                m_dir = re.search(r"(\d{1,4}(?:\.\d{1,3})?)", direct)
                if m_dir:
                    return Decimal(m_dir.group(1))
        setsudou_val = (
            specs.get("接道状況", "")
            or specs.get("道路付け", "")
            or specs.get("接道", "")
        )
        if setsudou_val:
            m = _KENBIYA_WIDTH_LABEL_RE.search(
                setsudou_val
            ) or _KENBIYA_WIDTH_DIR_RE.search(setsudou_val)
            if m:
                return Decimal(m.group(1))
        return None

    def _parse_traffic(self, item, traffic_text: str):
        """健美家の交通情報テキストから沿線・駅・徒歩分数を抽出"""
        matches = re.finditer(
            r"([^\s]+?(?:線|ライン|ライナー|鉄道|メトロ))\s+([^\s]+?駅)\s*(?:徒歩)?(\d+)分?",
            traffic_text,
        )
        idx = 1
        for m in matches:
            railway = m.group(1).strip()
            station = m.group(2).strip()
            if station.endswith("駅"):
                station = station[:-1].strip()
            walk = int(m.group(3))

            if idx == 1:
                item.railway1 = railway
                item.station1 = station
                item.railwayWalkMinute1 = walk
                item.walkMinutes1 = walk
            elif idx == 2:
                item.railway2 = railway
                item.station2 = station
                item.railwayWalkMinute2 = walk
                item.walkMinutes2 = walk
            elif idx == 3:
                item.railway3 = railway
                item.station3 = station
                item.railwayWalkMinute3 = walk
                item.walkMinutes3 = walk
            idx += 1

    def _populate_common_fields(self, item, response: BeautifulSoup, specs=None):
        """全種別共通プロパティの自動バインド（コード重複削減）"""
        specs = specs or self._get_specs(response)
        item.price = self._parsePrice(response, specs)
        item.priceStr = self._parsePriceStr(response, specs)
        item.address = self._parseAddress(response, specs)
        item.propertyName = self._parsePropertyName(response, specs)
        item.tochikenri = self._parseRights(response, specs)
        item.setsudou = self._parseSetsudou(response, specs)
        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.currentStatus = self._parseCurrentStatus(response, specs)
        item.genkyo = item.currentStatus
        item.hikiwatashi = self._parseHikiwatashi(response, specs)
        item.chimoku = self._parseChimoku(response, specs)
        item.grossYield = self._parseGrossYield(response, specs)
        item.annualRent = self._parseAnnualRent(response, specs)

        maguchi_val = self._parseMaguchi(response, specs)
        if maguchi_val is not None:
            item.maguchi = maguchi_val
            item.maguchiStr = f"{maguchi_val}m"
        road_width_val = self._parseRoadWidth(response, specs)
        if road_width_val is not None:
            item.roadWidth = road_width_val
            item.roadWidthStr = f"{road_width_val}m"

        traffic_text = (
            specs.get("交通", "")
            or specs.get("アクセス", "")
            or specs.get("最寄駅", "")
        )
        if traffic_text:
            item.traffic = traffic_text
            self._parse_traffic(item, traffic_text)
        return specs

    def _populate_building_specs(self, item, response: BeautifulSoup, specs):
        """一棟アパート・一棟ビル共通スペックのバインド"""
        item.monthlyRent = self._parseMonthlyRent(response, specs)
        item.chikunengetsu = self._parseChikunengetsu(response, specs)
        item.chikunengetsuStr = specs.get("築年月", "")

        raw_kouzou = specs.get(STRUCTURE_TEXT, "") or specs.get(STRUCTURE_FLOOR, "")
        item.kouzou = self._parseKouzou(response, specs)
        soukosu_match = re.search(SOUKOSU_REGEX, raw_kouzou)
        if soukosu_match:
            item.soukosu = int(soukosu_match.group(1))
            item.soukosuStr = f"{item.soukosu}戸"

        item.tochiMenseki = self._parseTochiMenseki(response, specs)
        item.tochiMensekiStr = specs.get("土地面積", "")
        item.tatemonoMenseki = self._parseTatemonoMenseki(response, specs)
        item.tatemonoMensekiStr = specs.get("建物面積", "")

        item.kenpei = self._parseKenpei(response, specs)
        item.youseki = self._parseYouseki(response, specs)
        kenpei_youseki = specs.get(KENPEI_YOUSEKI_SLASH, "") or specs.get(
            KENPEI_YOUSEKI_FULL, ""
        )
        if "/" in kenpei_youseki:
            parts = kenpei_youseki.split("/")
            item.kenpeiStr = parts[0].strip()
            item.yousekiStr = parts[1].strip()

        item.madori = specs.get("間取り", "")


class KenbiyaInvestmentApartmentParser(KenbiyaParserBase, InvestmentParserBase):
    """
    健美家 (Kenbiya) 投資用一棟アパート向けパーサー (/pp2/)
    """

    property_type = "investmentapartment"

    def createEntity(self) -> KenbiyaInvestmentApartment:
        return KenbiyaInvestmentApartment()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        specs = self._populate_common_fields(item, response)
        self._populate_building_specs(item, response, specs)
        item.propertyType = "Apartment"
        return item


class KenbiyaInvestmentBuildingParser(KenbiyaParserBase, InvestmentParserBase):
    """
    健美家 (Kenbiya) 投資用一棟マンション・ビル向けパーサー (/pp3/, /pp4/)
    """

    property_type = "investmentbuilding"

    def createEntity(self) -> KenbiyaInvestmentBuilding:
        return KenbiyaInvestmentBuilding()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        specs = self._populate_common_fields(item, response)
        self._populate_building_specs(item, response, specs)
        item.propertyType = "Building"
        return item


class KenbiyaMansionParser(KenbiyaParserBase, MansionParserBase):
    """
    健美家 (Kenbiya) 区分マンション向けパーサー (/pp1/)
    """

    property_type = "mansion"

    def createEntity(self) -> KenbiyaMansion:
        return KenbiyaMansion()

    def _parseMadori(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        val = specs.get("間取り", "") or specs.get("間取", "")
        if not val:
            return ""
        for token in val.split():
            clean_tok = "".join(c for c in token if c.isalnum())
            if clean_tok in ("ワンルーム", "1R") or any(
                clean_tok.endswith(suffix)
                for suffix in ("R", "K", "DK", "LDK", "SLDK", "SK")
            ):
                return clean_tok
        return val.split()[0]

    def _parseSenyuMenseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        val = specs.get("専有面積", "")
        if not val:
            return None
        val_main = val.split("（")[0].split("(")[0]
        return converter.parse_menseki(val_main.replace("m²", "㎡"))

    def _parseBalconyMenseki(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        val = specs.get("専有面積", "") or specs.get("バルコニー面積", "")
        if "バルコニー" in val:
            b_part = val.split("バルコニー")[1].split("）")[0].split(")")[0]
            return converter.parse_menseki(b_part.replace("m²", "㎡"))
        return None

    def _parseFloor(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        val = (
            specs.get(STRUCTURE_FLOOR, "")
            or specs.get("階数", "")
            or specs.get("所在階", "")
        )
        if "/" in val:
            val = val.split("/")[0]
        digits = "".join(c for c in val if c.isdigit())
        return int(digits) if digits else None

    def _parseTotalFloor(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        val = (
            specs.get(STRUCTURE_FLOOR, "")
            or specs.get("階数", "")
            or specs.get("総階数", "")
        )
        if "/" in val:
            part = val.split("/")[1].split("階")[0]
            digits = "".join(c for c in part if c.isdigit())
            if digits:
                return int(digits)
        if "地上" in val:
            part = val.split("地上")[1].split("階")[0]
            digits = "".join(c for c in part if c.isdigit())
            if digits:
                return int(digits)
        return None

    def _parseSouKosu(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        val = specs.get(STRUCTURE_FLOOR, "") or specs.get("総戸数", "")
        m = re.search(SOUKOSU_REGEX, val)
        return int(m.group(1)) if m else None

    def _parseDirection(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        val = (
            specs.get("間取り", "")
            or specs.get("向き", "")
            or specs.get("主要採光面", "")
        )
        m = re.search(r"(南東|南西|北東|北西|東|西|南|北)向き", val)
        if m:
            return m.group(1)
        m2 = re.search(r"(南東|南西|北東|北西|東|西|南|北)", val)
        return m2.group(1) if m2 else ""

    def _parseManagementFee(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        val = specs.get("管理費/修繕積立", "") or specs.get("管理費", "")
        if "/" in val:
            part = val.split("/")[0].strip()
            return converter.parse_yen(part)
        return converter.parse_yen(val) if val else None

    _parseMaintenanceFee = _parseManagementFee

    def _parseReserveFund(self, response: BeautifulSoup, specs=None):
        specs = specs or self._get_specs(response)
        val = (
            specs.get("管理費/修繕積立", "")
            or specs.get("修繕積立金", "")
            or specs.get("修繕積立", "")
        )
        if "/" in val:
            part = val.split("/")[1].strip()
            return converter.parse_yen(part)
        return converter.parse_yen(val) if val else None

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        specs = self._populate_common_fields(item, response)
        item.monthlyRent = self._parseMonthlyRent(response, specs)
        item.chikunengetsu = self._parseChikunengetsu(response, specs)
        item.chikunengetsuStr = specs.get("築年月", "")

        item.kouzou = self._parseKouzou(response, specs)
        item.madori = self._parseMadori(response, specs)
        item.senyuMenseki = self._parseSenyuMenseki(response, specs)
        item.senyuMensekiStr = specs.get("専有面積", "")
        item.balconyMenseki = self._parseBalconyMenseki(response, specs)

        item.floor = self._parseFloor(response, specs)
        if item.floor:
            item.floorStr = f"{item.floor}階"
        item.totalFloor = self._parseTotalFloor(response, specs)
        if item.totalFloor:
            item.totalFloorStr = f"{item.totalFloor}階建"

        item.soukosu = self._parseSouKosu(response, specs)
        if item.soukosu:
            item.soukosuStr = f"{item.soukosu}戸"

        item.direction = self._parseDirection(response, specs)
        item.kanrihi = self._parseMaintenanceFee(response, specs)
        item.shuzenTsumitate = self._parseReserveFund(response, specs)

        item.kenpei = self._parseKenpei(response, specs)
        item.youseki = self._parseYouseki(response, specs)
        item.youtoChiiki = self._parseYoutoChiiki(response, specs)
        item.propertyType = "Mansion"

        return item


class KenbiyaKodateParser(KenbiyaParserBase, KodateParserBase):
    """
    健美家 (Kenbiya) 戸建賃貸向けパーサー (/pp8/)
    """

    property_type = "kodate"

    def createEntity(self) -> KenbiyaKodate:
        return KenbiyaKodate()

    def _parseMadori(self, response: BeautifulSoup, specs=None) -> str:
        specs = specs or self._get_specs(response)
        return specs.get("間取り", "") or specs.get("間取", "")

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        specs = self._populate_common_fields(item, response)
        item.monthlyRent = self._parseMonthlyRent(response, specs)
        item.chikunengetsu = self._parseChikunengetsu(response, specs)
        item.chikunengetsuStr = specs.get("築年月", "")

        item.kouzou = self._parseKouzou(response, specs)
        item.madori = self._parseMadori(response, specs)
        item.tochiMenseki = self._parseTochiMenseki(response, specs)
        item.tochiMensekiStr = specs.get("土地面積", "")
        item.tatemonoMenseki = self._parseTatemonoMenseki(response, specs)
        item.tatemonoMensekiStr = specs.get("建物面積", "")

        item.kenpei = self._parseKenpei(response, specs)
        item.youseki = self._parseYouseki(response, specs)
        item.propertyType = "Kodate"

        return item


class KenbiyaTochiParser(KenbiyaParserBase, TochiParserBase):
    """
    健美家 (Kenbiya) 投資用土地・事業用土地向けパーサー (/pp5/)
    """

    property_type = "tochi"

    def createEntity(self) -> KenbiyaTochi:
        return KenbiyaTochi()

    def _parseMaguchi(self, response: BeautifulSoup, specs=None):
        return super()._parseMaguchi(response, specs)

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        specs = self._populate_common_fields(item, response)
        item.tochiMenseki = self._parseTochiMenseki(response, specs)
        item.tochiMensekiStr = specs.get("土地面積", "")

        item.kenpei = self._parseKenpei(response, specs)
        item.youseki = self._parseYouseki(response, specs)
        item.propertyType = "Tochi"

        return item
