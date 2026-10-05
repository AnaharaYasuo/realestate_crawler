"""
Terraform Cloud Run サービス構成の単体テスト。
Issue #670: feat(cloud-run): enable cpu_idle for crawler worker service
Issue #701: feat(terraform): configure cpu_idle for realestate-api and realestate-slack-agent services
"""
import os
import re


def get_repo_root():
    """リポジトリルートディレクトリを探索して返す"""
    cur = os.path.abspath(os.path.dirname(__file__))
    for _ in range(6):
        if os.path.exists(os.path.join(cur, "src")) and (
            os.path.exists(os.path.join(cur, ".git"))
            or os.path.exists(os.path.join(cur, "terraform"))
            or os.path.exists(os.path.join(cur, "Taskfile.yml"))
        ):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))


def _extract_resources_block(file_content: str) -> str:
    """HCLファイルから resources ブロックの内容を抽出する"""
    start_idx = file_content.find("resources {")
    assert start_idx != -1, "resources ブロックが見つかりません"
    brace_depth = 0
    content_chars = []
    found_first_brace = False
    for char in file_content[start_idx:]:
        if char == "{":
            brace_depth += 1
            found_first_brace = True
            continue
        elif char == "}":
            brace_depth -= 1
            if brace_depth == 0 and found_first_brace:
                break
        if found_first_brace:
            content_chars.append(char)
    return "".join(content_chars)


def test_realestate_api_service_cpu_idle_configured():
    """realestate-api サービスで cpu_idle = true が設定されていることを検証"""
    repo_root = get_repo_root()
    tf_path = os.path.join(repo_root, "terraform", "cloud_run_api_service.tf")
    assert os.path.exists(tf_path), f"cloud_run_api_service.tf が存在しません: {tf_path}"

    with open(tf_path, "r", encoding="utf-8") as f:
        content = f.read()

    resources_block = _extract_resources_block(content)
    assert "cpu_idle" in resources_block, "cloud_run_api_service.tf の resources に cpu_idle が指定されていません"
    assert re.search(r"cpu_idle\s*=\s*true", resources_block), "cpu_idle が true に設定されていません"


def test_realestate_slack_agent_service_cpu_idle_configured():
    """realestate-slack-agent サービスで cpu_idle = true が設定されていることを検証"""
    repo_root = get_repo_root()
    tf_path = os.path.join(repo_root, "terraform", "cloud_run_service.tf")
    assert os.path.exists(tf_path), f"cloud_run_service.tf が存在しません: {tf_path}"

    with open(tf_path, "r", encoding="utf-8") as f:
        content = f.read()

    resources_block = _extract_resources_block(content)
    assert "cpu_idle" in resources_block, "cloud_run_service.tf の resources に cpu_idle が指定されていません"
    assert re.search(r"cpu_idle\s*=\s*true", resources_block), "cpu_idle が true に設定されていません"


def test_realestate_crawler_worker_service_cpu_idle_configured():
    """realestate-crawler-worker サービスで cpu_idle = true が維持されていることを検証"""
    repo_root = get_repo_root()
    tf_path = os.path.join(repo_root, "terraform", "cloud_run_crawler_service.tf")
    assert os.path.exists(tf_path), f"cloud_run_crawler_service.tf が存在しません: {tf_path}"

    with open(tf_path, "r", encoding="utf-8") as f:
        content = f.read()

    resources_block = _extract_resources_block(content)
    assert "cpu_idle" in resources_block, "cloud_run_crawler_service.tf の resources に cpu_idle が指定されていません"
    assert re.search(r"cpu_idle\s*=\s*true", resources_block), "cpu_idle が true に設定されていません"
