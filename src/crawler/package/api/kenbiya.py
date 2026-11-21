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
    KenbiyaTochiParser,
)

DETAIL_PARALLEL_LIMIT = int(os.getenv("KENBIYA_DETAIL_PARALLEL_LIMIT", "5"))
MIDDLE_PARALLEL_LIMIT = 1
COOLDOWN_WORK_SECONDS = float(os.getenv("KENBIYA_COOLDOWN_WORK_SECONDS", "3600"))
COOLDOWN_REST_SECONDS = float(os.getenv("KENBIYA_COOLDOWN_REST_SECONDS", "1800"))


def _run_router_ssh(remote_cmd: str) -> None:
    host = os.getenv("GL_ROUTER_HOST", "").strip()
    pwd = os.getenv("GL_ROUTER_PASSWORD", "").strip()
    if not host or not pwd:
        return
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
        subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10", f"root@{host}", remote_cmd],
            env=env,
            timeout=30,
            check=False,
        )
    except Exception as exc:
        logging.warning(f"[KENBIYA_PPPOE_SSH] Failed to run '{remote_cmd}' on {host}: {exc}")
    finally:
        try:
            os.remove(ask_path)
        except OSError:
            pass


def _kenbiya_on_pause(host: str) -> None:
    logging.info(f"[KENBIYA_COOLDOWN_PAUSE] {host}: disconnecting wan_pppoe...")
    _run_router_ssh("ifdown wan_pppoe")


def _kenbiya_on_resume(host: str) -> None:
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
class ParseKenbiyaKodateDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return KenbiyaKodateParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

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
class ParseKenbiyaTochiDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return KenbiyaTochiParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

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
class ParseKenbiyaInvestApartmentDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return KenbiyaInvestmentApartmentParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

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
class ParseKenbiyaInvestBuildingDetailFuncAsync(ParseDetailPageAsyncBase):
    def _generateParser(self): return KenbiyaInvestmentBuildingParser()
    def _getLocalPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getCloudPararellLimit(self): return DETAIL_PARALLEL_LIMIT
    def _getTimeOutSecond(self): return 60
    def _getApiKey(self): return ""

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
