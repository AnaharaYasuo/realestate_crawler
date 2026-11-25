import logging
import os
import subprocess
import tempfile
import time

import requests

from package.api.api import (
    API_KEY_KENBIYA_INVEST_APARTMENT_DETAIL,
    API_KEY_KENBIYA_INVEST_APARTMENT_START,
    API_KEY_KENBIYA_INVEST_BUILDING_DETAIL,
    API_KEY_KENBIYA_INVEST_BUILDING_START,
    API_KEY_KENBIYA_KODATE_DETAIL,
    API_KEY_KENBIYA_KODATE_START,
    API_KEY_KENBIYA_MANSION_DETAIL,
    API_KEY_KENBIYA_MANSION_START,
    API_KEY_KENBIYA_TOCHI_DETAIL,
    API_KEY_KENBIYA_TOCHI_START,
    ParseDetailPageAsyncBase,
    ParseMiddlePageAsyncBase,
    _crawl_cooldown_controller,
)
from package.api.registry import ApiRegistry
from package.parser.kenbiyaParser import (
    KenbiyaInvestmentApartmentParser,
    KenbiyaInvestmentBuildingParser,
    KenbiyaKodateParser,
    KenbiyaMansionParser,
    KenbiyaParserBase,
    KenbiyaTochiParser,
)

DETAIL_PARALLEL_LIMIT = int(os.getenv("KENBIYA_DETAIL_PARALLEL_LIMIT", "5"))
MIDDLE_PARALLEL_LIMIT = 1
COOLDOWN_WORK_SECONDS = float(os.getenv("KENBIYA_COOLDOWN_WORK_SECONDS", "3600"))
COOLDOWN_REST_SECONDS = float(os.getenv("KENBIYA_COOLDOWN_REST_SECONDS", "1800"))


def _run_router_ssh(remote_cmd: str) -> str:
    host = os.getenv("GL_ROUTER_HOST", "").strip()
    pwd = os.getenv("GL_ROUTER_PASSWORD", "").strip()
    if not host or not pwd:
        return ""
    suffix = ".bat" if os.name == "nt" else ".sh"
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="ascii") as f:
        if os.name == "nt":
            f.write(f"@echo {pwd}\n")
        else:
            f.write(f"#!/bin/sh\necho '{pwd}'\n")
        ask_path = f.name
    try:
        if os.name != "nt":
            os.chmod(ask_path, 0o700)
        env = os.environ.copy()
        env["SSH_ASKPASS"] = ask_path
        env["SSH_ASKPASS_REQUIRE"] = "force"
        env["DISPLAY"] = "dummy:0"
        proc = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10", f"root@{host}", remote_cmd],
            env=env,
            timeout=30,
            check=False,
            capture_output=True,
            text=True,
        )
        return (proc.stdout or "").strip()
    except Exception as exc:
        logging.warning(f"[KENBIYA_PPPOE_SSH] Failed to run '{remote_cmd}' on {host}: {exc}")
        return ""
    finally:
        try:
            os.remove(ask_path)
        except OSError:
            pass


def _get_wan_pppoe_ip() -> str | None:
    """ルーター上の wan_pppoe インターフェースの現在のIPv4アドレスを取得する"""
    cmd = (
        "ubus call network.interface.wan_pppoe status 2>/dev/null "
        "| jsonfilter -e '@[\"ipv4-address\"][0].address' 2>/dev/null "
        "|| ip -4 -o addr show dev pppoe-wan_pppoe 2>/dev/null | awk '{print $4}' | cut -d/ -f1"
    )
    out = _run_router_ssh(cmd)
    if not out:
        return None
    for line in out.splitlines():
        candidate = line.strip()
        parts = candidate.split(".")
        if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            return candidate
    return None


_cooldown_leader_hosts: set[str] = set()


def _kenbiya_on_pause(host: str) -> None:
    is_leader = KenbiyaParserBase.begin_shared_cooldown_pause(COOLDOWN_REST_SECONDS)
    if not is_leader:
        logging.info(
            f"[KENBIYA_COOLDOWN_PAUSE] {host}: another process already paused wan_pppoe; syncing rest."
        )
        return
    _cooldown_leader_hosts.add(host)
    logging.info(f"[KENBIYA_COOLDOWN_PAUSE] {host}: disconnecting wan_pppoe (shared across all processes)...")
    _run_router_ssh("ifdown wan_pppoe")


def _kenbiya_on_resume(host: str) -> None:
    is_leader = host in _cooldown_leader_hosts
    _cooldown_leader_hosts.discard(host)
    if not is_leader:
        KenbiyaParserBase._waf_cookies = {}
        logging.info(f"[KENBIYA_COOLDOWN_RESUME] {host}: follower resuming after shared cooldown.")
        return
    try:
        logging.info(f"[KENBIYA_COOLDOWN_RESUME] {host}: reconnecting wan_pppoe, reloading routing table, and refreshing cookies...")
        _run_router_ssh("ifup wan_pppoe; sleep 5; /etc/init.d/vpn-policy-routing reload")
        time.sleep(2)
        try:
            resp = requests.get(
                f"https://{host}/pp0/",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
                timeout=15,
            )
            cookie_hdr = "; ".join(f"{k}={v}" for k, v in resp.cookies.items())
            if cookie_hdr:
                _crawl_cooldown_controller.set_cookie_header(host, cookie_hdr)
                logging.info(f"[KENBIYA_COOLDOWN_RESUME] {host}: refreshed {len(resp.cookies)} cookie(s).")
        except Exception as exc:
            logging.warning(f"[KENBIYA_COOLDOWN_RESUME] {host}: failed to refresh cookies: {exc}")
    finally:
        KenbiyaParserBase.end_shared_cooldown_pause()


class _KenbiyaDetailBase(ParseDetailPageAsyncBase):
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""
    def _get_cooldown_config(self): return (COOLDOWN_WORK_SECONDS, COOLDOWN_REST_SECONDS)
    def _get_cooldown_hooks(self): return (_kenbiya_on_pause, _kenbiya_on_resume)


# Mansion (/pp1/)
class ParseKenbiyaMansionDetailFuncAsync(_KenbiyaDetailBase):
    def _generateParser(self): return KenbiyaMansionParser()

class ParseKenbiyaMansionStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return KenbiyaMansionParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_KENBIYA_MANSION_DETAIL
    def _getNextPageApiKey(self): return API_KEY_KENBIYA_MANSION_START

# Kodate (/pp8/)
class ParseKenbiyaKodateDetailFuncAsync(_KenbiyaDetailBase):
    def _generateParser(self): return KenbiyaKodateParser()

class ParseKenbiyaKodateStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return KenbiyaKodateParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_KENBIYA_KODATE_DETAIL
    def _getNextPageApiKey(self): return API_KEY_KENBIYA_KODATE_START

# Tochi (/pp5/)
class ParseKenbiyaTochiDetailFuncAsync(_KenbiyaDetailBase):
    def _generateParser(self): return KenbiyaTochiParser()

class ParseKenbiyaTochiStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return KenbiyaTochiParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_KENBIYA_TOCHI_DETAIL
    def _getNextPageApiKey(self): return API_KEY_KENBIYA_TOCHI_START

# Investment Apartment (/pp2/)
class ParseKenbiyaInvestApartmentDetailFuncAsync(_KenbiyaDetailBase):
    def _generateParser(self): return KenbiyaInvestmentApartmentParser()

class ParseKenbiyaInvestApartmentStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return KenbiyaInvestmentApartmentParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_KENBIYA_INVEST_APARTMENT_DETAIL
    def _getNextPageApiKey(self): return API_KEY_KENBIYA_INVEST_APARTMENT_START

# Investment Building (/pp3/, /pp4/)
class ParseKenbiyaInvestBuildingDetailFuncAsync(_KenbiyaDetailBase):
    def _generateParser(self): return KenbiyaInvestmentBuildingParser()

class ParseKenbiyaInvestBuildingStartAsync(ParseMiddlePageAsyncBase):
    def _generateParser(self): return KenbiyaInvestmentBuildingParser()
    def _getParserFunc(self): return self.parser.parseRootPage
    def _getNextPageParserFunc(self): return self.parser.parseNextPage
    def _isBsMiddlePage(self): return True
    def _getLocalPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return MIDDLE_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 600
    def _getApiKey(self): return API_KEY_KENBIYA_INVEST_BUILDING_DETAIL
    def _getNextPageApiKey(self): return API_KEY_KENBIYA_INVEST_BUILDING_START

# Register
ApiRegistry.register(API_KEY_KENBIYA_MANSION_START, ParseKenbiyaMansionStartAsync)
ApiRegistry.register(API_KEY_KENBIYA_MANSION_DETAIL, ParseKenbiyaMansionDetailFuncAsync)
ApiRegistry.register(API_KEY_KENBIYA_KODATE_START, ParseKenbiyaKodateStartAsync)
ApiRegistry.register(API_KEY_KENBIYA_KODATE_DETAIL, ParseKenbiyaKodateDetailFuncAsync)
ApiRegistry.register(API_KEY_KENBIYA_TOCHI_START, ParseKenbiyaTochiStartAsync)
ApiRegistry.register(API_KEY_KENBIYA_TOCHI_DETAIL, ParseKenbiyaTochiDetailFuncAsync)
ApiRegistry.register(API_KEY_KENBIYA_INVEST_APARTMENT_START, ParseKenbiyaInvestApartmentStartAsync)
ApiRegistry.register(API_KEY_KENBIYA_INVEST_APARTMENT_DETAIL, ParseKenbiyaInvestApartmentDetailFuncAsync)
ApiRegistry.register(API_KEY_KENBIYA_INVEST_BUILDING_START, ParseKenbiyaInvestBuildingStartAsync)
ApiRegistry.register(API_KEY_KENBIYA_INVEST_BUILDING_DETAIL, ParseKenbiyaInvestBuildingDetailFuncAsync)
