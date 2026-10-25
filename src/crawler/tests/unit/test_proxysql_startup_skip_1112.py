import os
import re
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
TERRAFORM_DIR = os.path.join(REPO_ROOT, "terraform")


def _read_proxysql_startup_script() -> str:
    proxysql_tf = os.path.join(TERRAFORM_DIR, "proxysql.tf")
    with open(proxysql_tf, encoding="utf-8") as f:
        content = f.read()
    match = re.search(r"metadata_startup_script\s*=\s*<<-EOF\n(.*?)\n\s*EOF\n", content, re.DOTALL)
    assert match, "proxysql.tf must define metadata_startup_script as a <<-EOF heredoc."
    return match.group(1)


def test_proxysql_startup_script_skips_apt_when_proxysql_installed():
    """Issue #1112: ProxySQL が既にインストール済みの場合は外部 apt-get / wget をスキップすること"""
    script = _read_proxysql_startup_script()
    assert "command -v proxysql" in script, "startup script must check if proxysql is installed using command -v."
    assert "Skipping apt package installation" in script, "startup script must output skip log when already installed."
    
    # if ! command -v proxysql ... else ... fi の構造が存在すること
    match = re.search(r"if\s+!\s+command\s+-v\s+proxysql\s*>\s*/dev/null\s*2>&1;\s*then(.*?)else(.*?)fi", script, re.DOTALL)
    assert match, "startup script must wrap apt/wget logic in command -v proxysql conditional."
    
    install_block = match.group(1)
    skip_block = match.group(2)
    
    assert "apt_retry update" in install_block, "install block must contain apt_retry update"
    assert "apt_retry install" in install_block, "install block must contain apt_retry install"
    assert "wget" in install_block, "install block must contain wget"
    assert "apt_retry" not in skip_block, "skip block must not contain any apt operations"
    assert "wget" not in skip_block, "skip block must not contain any wget operations"
