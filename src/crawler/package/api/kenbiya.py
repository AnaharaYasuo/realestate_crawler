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
    DEFAULT_KENBIYA_PPPOE_WAIT_SECONDS,
    KenbiyaInvestmentApartmentParser,
    KenbiyaInvestmentBuildingParser,
    KenbiyaKodateParser,
    KenbiyaMansionParser,
    KenbiyaParserBase,
    KenbiyaTochiParser,
)

DETAIL_PARALLEL_LIMIT = int(os.getenv("KENBIYA_DETAIL_PARALLEL_LIMIT", "5"))
MIDDLE_PARALLEL_LIMIT = 1
COOLDOWN_WORK_SECONDS = float(os.getenv("KENBIYA_COOLDOWN_WORK_SECONDS", "0"))
COOLDOWN_REST_SECONDS = float(
    os.getenv(
        "KENBIYA_COOLDOWN_REST_SECONDS",
        str(int(DEFAULT_KENBIYA_PPPOE_WAIT_SECONDS)),
    )
)


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


def disconnect_wan_pppoe() -> str:
    """ルーター上の wan_pppoe を切断する共通ヘルパー"""
    return _run_router_ssh("ifdown wan_pppoe")


def reconnect_wan_pppoe() -> str:
    """ルーター上の wan_pppoe を再接続し、vpn-policy-routing をリロードする共通ヘルパー"""
    return _run_router_ssh("ifup wan_pppoe; sleep 5; /etc/init.d/vpn-policy-routing reload")


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


def _check_proxysql_select1(host: str = "127.0.0.1", port: int = 6033, timeout: int = 5) -> bool:
    """ProxySQL (127.0.0.1:6033) に対して SELECT 1 で疎通確認を行う"""
    try:
        import pymysql

        conn = pymysql.connect(
            host=host,
            port=port,
            user=os.getenv("DB_USER", ""),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", ""),
            connect_timeout=timeout,
            read_timeout=timeout,
        )
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            return True
        finally:
            conn.close()
    except Exception:
        return False


def _get_local_proxysql_target() -> tuple[str, int] | None:
    """ローカル ProxySQL 自動復旧の対象なら (host, port) を返し、対象外なら None を返す"""
    if os.getenv("IS_CLOUD") or os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB"):
        return None
    if os.getenv("KENBIYA_PROXYSQL_AUTO_RECOVERY_DISABLED", "false").lower() in ("true", "1"):
        return None
    db_host = os.getenv("DB_HOST", "127.0.0.1").strip()
    try:
        db_port = int(os.getenv("DB_PORT", "6033"))
    except ValueError:
        db_port = 6033
    if db_host not in ("127.0.0.1", "localhost") or db_port != 6033:
        return None
    return db_host, db_port


def _start_proxysql_vm_if_needed(gcloud_bin: str, vm_name: str, vm_zone: str) -> None:
    desc = subprocess.run(
        [gcloud_bin, "compute", "instances", "describe", vm_name, f"--zone={vm_zone}", "--format=value(status)"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    status = (desc.stdout or "").strip()
    if status == "RUNNING":
        return
    logging.info(f"[KENBIYA_PROXYSQL_RECOVERY] Starting {vm_name} (status={status or 'UNKNOWN'})...")
    subprocess.run(
        [gcloud_bin, "compute", "instances", "start", vm_name, f"--zone={vm_zone}"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    time.sleep(15)


def _launch_proxysql_iap_tunnel(gcloud_bin: str, vm_name: str, vm_zone: str, db_host: str, db_port: int) -> None:
    logging.info(f"[KENBIYA_PROXYSQL_RECOVERY] Starting IAP tunnel to {vm_name}:6033...")
    popen_kwargs: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )
    else:
        popen_kwargs["start_new_session"] = True
    subprocess.Popen(
        [
            gcloud_bin,
            "compute",
            "start-iap-tunnel",
            vm_name,
            "6033",
            f"--local-host-port={db_host}:{db_port}",
            f"--zone={vm_zone}",
        ],
        **popen_kwargs,
    )


def _ensure_proxysql_tunnel_ready() -> bool:
    """wan_pppoe 再接続後に ProxySQL VM および IAP トンネル (127.0.0.1:6033) の疎通を確認し、
    未起動・切断状態であれば VM 起動および IAP トンネル再確立を自動実行する。
    """
    target = _get_local_proxysql_target()
    if target is None:
        return True
    db_host, db_port = target
    if _check_proxysql_select1(db_host, db_port):
        return True

    logging.warning(
        "[KENBIYA_PROXYSQL_RECOVERY] ProxySQL tunnel (127.0.0.1:6033) is unreachable; checking VM and restarting IAP tunnel..."
    )
    gcloud_bin = "gcloud.cmd" if os.name == "nt" else "gcloud"
    vm_name = os.getenv("PROXYSQL_VM_NAME", "proxysql-instance-prod")
    vm_zone = os.getenv("PROXYSQL_VM_ZONE", "asia-northeast1-a")
    try:
        _start_proxysql_vm_if_needed(gcloud_bin, vm_name, vm_zone)
        _launch_proxysql_iap_tunnel(gcloud_bin, vm_name, vm_zone, db_host, db_port)
        for _ in range(10):
            time.sleep(3)
            if _check_proxysql_select1(db_host, db_port):
                logging.info("[KENBIYA_PROXYSQL_RECOVERY] ProxySQL IAP tunnel recovered (SELECT 1 OK).")
                return True
        logging.warning("[KENBIYA_PROXYSQL_RECOVERY] ProxySQL IAP tunnel did not become ready within 30s.")
        return False
    except Exception as exc:
        logging.warning(f"[KENBIYA_PROXYSQL_RECOVERY] Failed to recover ProxySQL tunnel: {exc}")
        return False


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
    disconnect_wan_pppoe()


def _kenbiya_on_resume(host: str) -> None:
    is_leader = host in _cooldown_leader_hosts
    _cooldown_leader_hosts.discard(host)
    if not is_leader:
        KenbiyaParserBase._waf_cookies = {}
        logging.info(f"[KENBIYA_COOLDOWN_RESUME] {host}: follower resuming after shared cooldown.")
        return
    try:
        logging.info(f"[KENBIYA_COOLDOWN_RESUME] {host}: reconnecting wan_pppoe, reloading routing table, and refreshing cookies...")
        reconnect_wan_pppoe()
        _ensure_proxysql_tunnel_ready()
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
    def _get_cooldown_config(self):
        return (COOLDOWN_WORK_SECONDS, COOLDOWN_REST_SECONDS) if COOLDOWN_WORK_SECONDS > 0 else None
    def _get_cooldown_hooks(self): return (_kenbiya_on_pause, _kenbiya_on_resume)


class _KenbiyaStartBase(ParseMiddlePageAsyncBase):
    """健美家一覧巡回基底クラス: 2フェーズ（一覧全件巡回→詳細取得）で詳細ワーカーとのレート競合を排除する。"""

    def _defer_detail_dispatch_until_list_complete(self) -> bool:
        return True


# Mansion (/pp1/)
class ParseKenbiyaMansionDetailFuncAsync(_KenbiyaDetailBase):
    def _generateParser(self): return KenbiyaMansionParser()

class ParseKenbiyaMansionStartAsync(_KenbiyaStartBase):
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

class ParseKenbiyaKodateStartAsync(_KenbiyaStartBase):
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

class ParseKenbiyaTochiStartAsync(_KenbiyaStartBase):
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

class ParseKenbiyaInvestApartmentStartAsync(_KenbiyaStartBase):
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

class ParseKenbiyaInvestBuildingStartAsync(_KenbiyaStartBase):
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
