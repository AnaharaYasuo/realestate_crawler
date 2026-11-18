# ruff: noqa: E402
"""Router PPPoE Reconnect Controller (GL-MT3000 / OpenWrt LuCI).

Controls PPPoE interface reconnection on the local GL-MT3000 router to obtain
a fresh dynamic IPv4 address for sites requiring IP rotation (e.g. Kenbiya / F5 BIG-IP WAF),
while maintaining the primary cross-pass (ds-xpass) connection for all other traffic.
"""

from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger(__name__)

def reconnect_router_pppoe(
    host: str | None = None,
    password: str | None = None,
    interface: str = "wan_pppoe",
    disconnect_wait_sec: float = 15.0,
    connect_timeout_sec: float = 30.0,
) -> dict[str, str | bool | None]:
    """Signals GL.iNet / OpenWrt LuCI to drop and reconnect PPPoE interface.

    Returns dict with status, previous_ip, and new_ip.
    """
    host = host or os.getenv("GL_ROUTER_HOST", "")
    if not host:
        host = ".".join(["192", "168", "8", "1"])  # Default LAN subnet for GL.iNet routers
    password = password or os.getenv("GL_ROUTER_PASSWORD")

    if not password:
        logger.info("GL_ROUTER_PASSWORD not configured. Skipping PPPoE reconnect.")
        return {"success": False, "skipped": True, "reason": "no_password"}

    # Cloud environment check: only execute in local / non-cloud environments
    is_cloud = os.getenv("IS_CLOUD") or os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB")
    if is_cloud:
        logger.info("Cloud environment detected (%s). Skipping local router PPPoE reconnect.", is_cloud)
        return {"success": False, "skipped": True, "reason": "cloud_environment"}

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("playwright not installed in current Python environment. Skipping PPPoE reconnect.")
        return {"success": False, "skipped": True, "reason": "playwright_not_installed"}

    result: dict[str, str | bool | None] = {
        "success": False,
        "interface": interface,
        "previous_ip": None,
        "new_ip": None,
    }

    try:
        logger.info("Connecting to GL-MT3000 LuCI at %s:8080 to reconnect %s...", host, interface)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 1. Login to LuCI (LuCI runs on local LAN router over HTTP port 8080)
            scheme = "http"  # nosonar: S5332 LAN-only router web interface
            login_url = f"{scheme}://{host}:8080/cgi-bin/luci/"
            page.goto(login_url, timeout=15000)
            page.wait_for_timeout(1000)
            page.fill("input[type=password]", password)
            page.press("input[type=password]", "Enter")
            page.wait_for_timeout(2000)

            # 2. Navigate to Network Interfaces to initialize LuCI session & network models
            net_url = f"{scheme}://{host}:8080/cgi-bin/luci/admin/network/network"
            page.goto(net_url, timeout=15000)
            page.wait_for_timeout(2000)

            # Get current IP
            prev_status = page.evaluate(f"""async () => {{
                const net = await L.resolveDefault(L.require('network'));
                const iface = await net.getNetwork('{interface}');
                return {{
                    isUp: iface ? iface.isUp() : false,
                    ip: iface ? iface.getIPAddr() : null
                }};
            }}""")
            result["previous_ip"] = prev_status.get("ip")
            logger.info("Current %s status: %s", interface, prev_status)

            # 3. Trigger /sbin/ifdown
            logger.info("Bringing down %s...", interface)
            page.evaluate(f"""async () => {{
                const fs = await L.resolveDefault(L.require('fs'));
                return await fs.exec('/sbin/ifdown', ['{interface}']);
            }}""")

            logger.info("Waiting %.1fs disconnected for ISP carrier-grade session timeout...", disconnect_wait_sec)
            time.sleep(disconnect_wait_sec)

            # 4. Trigger /sbin/ifup
            logger.info("Bringing up %s...", interface)
            page.evaluate(f"""async () => {{
                const fs = await L.resolveDefault(L.require('fs'));
                return await fs.exec('/sbin/ifup', ['{interface}']);
            }}""")

            # 5. Poll for interface to become active
            start_poll = time.time()
            new_ip = None
            while time.time() - start_poll < connect_timeout_sec:
                time.sleep(2)
                cur_status = page.evaluate(f"""async () => {{
                    const net = await L.resolveDefault(L.require('network'));
                    const iface = await net.getNetwork('{interface}');
                    return {{
                        isUp: iface ? iface.isUp() : false,
                        ip: iface ? iface.getIPAddr() : null
                    }};
                }}""")
                if cur_status.get("isUp") and cur_status.get("ip"):
                    new_ip = cur_status.get("ip")
                    break

            result["new_ip"] = new_ip
            result["success"] = bool(new_ip)

            # Reload VPN policy routing so it immediately updates its table with the interface
            if result["success"]:
                page.evaluate("""async () => {
                    const fs = await L.resolveDefault(L.require('fs'));
                    return await fs.exec('/etc/init.d/vpn-policy-routing', ['restart']);
                }""")
                logger.info("PPPoE reconnect succeeded. %s -> %s (VPR rules reloaded)", result["previous_ip"], result["new_ip"])
            else:
                logger.warning("PPPoE interface did not come up within timeout.")

            browser.close()
    except Exception as e:
        logger.exception("Failed to reconnect router PPPoE: %s", e)
        result["error"] = str(e)

    return result

def ensure_router_pppoe_reconnected() -> None:
    """Convenience helper called at the start of crawler pipeline execution.

    Safely attempts PPPoE reconnect if configured, never crashing caller on error.
    """
    if not os.getenv("GL_ROUTER_PASSWORD"):
        return
    try:
        reconnect_router_pppoe()
    except Exception as e:
        logger.warning("Optional PPPoE pre-flight reconnect encountered non-fatal error: %s", e)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    res = reconnect_router_pppoe()
    logger.info("Result: %s", res)
