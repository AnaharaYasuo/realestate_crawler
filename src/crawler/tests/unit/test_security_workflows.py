"""
Trivy, Semgrep, Checkov, Prowler セキュリティ自動スキャンワークフローおよび関連設定の単体テスト。
Issue #250: [Feature] Setup Trivy & Semgrep security workflows, Checkov & Prowler GCP audit, and disable Snyk
"""
import os
from pathlib import Path
import yaml
from unittest.mock import AsyncMock, MagicMock
import pytest
from package.api.api import ApiAsyncProcBase
from package.parser.athomeParser import AthomeParser
from package.testing.mutation_engine import ASTMutationEngine, Mutant, MutationType


def get_repo_root():
    """リポジトリルートディレクトリを探索して返す"""
    cur = os.path.abspath(os.path.dirname(__file__))
    for _ in range(6):
        if os.path.exists(os.path.join(cur, "src")) and (
            os.path.exists(os.path.join(cur, ".git"))
            or os.path.exists(os.path.join(cur, "Taskfile.yml"))
            or os.path.exists(os.path.join(cur, ".github"))
        ):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))


def test_security_scan_workflow_exists_and_valid():
    """新規セキュリティワークフロー .github/workflows/security-scan.yml の構文と必須設定を検証"""
    repo_root = get_repo_root()
    workflow_path = os.path.join(repo_root, ".github", "workflows", "security-scan.yml")

    assert os.path.exists(workflow_path), f"security-scan.yml が存在しません: {workflow_path}"

    with open(workflow_path, "r", encoding="utf-8") as f:
        content = f.read()
        workflow = yaml.safe_load(content)

    assert isinstance(workflow, dict), "security-scan.yml の内容が辞書形式ではありません"

    # トリガー条件の検証
    triggers = workflow.get("on") or workflow.get(True)
    assert triggers is not None, "トリガー (on) が定義されていません"

    # PR トリガー
    pr_trigger = triggers.get("pull_request")
    assert pr_trigger is not None, "pull_request トリガーが定義されていません"
    pr_branches = pr_trigger.get("branches", [])
    assert "master" in pr_branches or "main" in pr_branches, "PRトリガーに対象ブランチ (master/main) が含まれている必要があります"

    # 権限の検証
    permissions = workflow.get("permissions", {})
    assert permissions.get("security-events") == "write", "security-events: write 権限が必要です"

    # ジョブ構成の検証
    jobs = workflow.get("jobs", {})
    assert len(jobs) >= 2, "Trivy と Semgrep などの並列ジョブが定義されている必要があります"

    # Trivy ジョブの検証
    trivy_job_name = next((k for k in jobs.keys() if "trivy" in k.lower()), None)
    assert trivy_job_name is not None, "Trivy ジョブが jobs 配下に存在しません"
    trivy_job = jobs[trivy_job_name]

    # Semgrep ジョブの検証
    semgrep_job_name = next((k for k in jobs.keys() if "semgrep" in k.lower()), None)
    assert semgrep_job_name is not None, "Semgrep ジョブが jobs 配下に存在しません"
    semgrep_job = jobs[semgrep_job_name]

    # 並列性の検証 (互いに依存関係 needs を持たないこと)
    assert "needs" not in trivy_job or trivy_job.get("needs") != semgrep_job_name, "Trivy ジョブが Semgrep に依存してはなりません"
    assert "needs" not in semgrep_job or semgrep_job.get("needs") != trivy_job_name, "Semgrep ジョブが Trivy に依存してはなりません"

    # Trivy ステップの検証
    trivy_steps = trivy_job.get("steps", [])
    trivy_scan_step = next((s for s in trivy_steps if "trivy-action" in s.get("uses", "") or "trivy" in s.get("name", "").lower()), None)
    assert trivy_scan_step is not None, "Trivy スキャンステップが見つかりません"

    with_params = trivy_scan_step.get("with", {})
    assert with_params.get("exit-code") == "1" or with_params.get("exit_code") == 1 or with_params.get("exit-code") == 1, "Trivy は脆弱性検出時に exit-code: '1' で失敗する設定が必要です"
    severity = str(with_params.get("severity", ""))
    assert "CRITICAL" in severity and "HIGH" in severity, "Trivy の severity に HIGH および CRITICAL が含まれている必要があります"
    assert with_params.get("format") == "sarif", "Trivy の format は sarif である必要があります"

    # Trivy upload-sarif ステップ
    trivy_sarif_upload = next((s for s in trivy_steps if "upload-sarif" in s.get("uses", "")), None)
    assert trivy_sarif_upload is not None, "Trivy ジョブ内に upload-sarif ステップが存在しません"
    assert "failure()" in str(trivy_sarif_upload.get("if", "")), "Trivy upload-sarif はエラー時にもアップロードされるよう if: success() || failure() が必要です"

    # Semgrep ステップの検証
    semgrep_steps = semgrep_job.get("steps", [])
    semgrep_scan_step = next((s for s in semgrep_steps if "semgrep" in s.get("run", "").lower() or "semgrep" in s.get("uses", "").lower()), None)
    assert semgrep_scan_step is not None, "Semgrep スキャンステップが見つかりません"

    semgrep_run = semgrep_scan_step.get("run", "")
    assert "--sarif" in semgrep_run, "Semgrep コマンドに --sarif が指定されている必要があります"
    assert "--error" in semgrep_run, "Semgrep コマンドに --error (終了コード1) が指定されている必要があります"
    assert "ERROR" in semgrep_run or "HIGH" in semgrep_run, "Semgrep コマンドに重大度 ERROR フィルタが指定されている必要があります"

    # Semgrep upload-sarif ステップ
    semgrep_sarif_upload = next((s for s in semgrep_steps if "upload-sarif" in s.get("uses", "")), None)
    assert semgrep_sarif_upload is not None, "Semgrep ジョブ内に upload-sarif ステップが存在しません"
    assert "failure()" in str(semgrep_sarif_upload.get("if", "")), "Semgrep upload-sarif はエラー時にもアップロードされるよう if: success() || failure() が必要です"

    # Checkov ジョブの検証 (存在する場合)
    checkov_job_name = next((k for k in jobs.keys() if "checkov" in k.lower()), None)
    if checkov_job_name:
        checkov_job = jobs[checkov_job_name]
        checkov_steps = checkov_job.get("steps", [])
        checkov_step = next((s for s in checkov_steps if "checkov" in s.get("uses", "") or "checkov" in s.get("run", "").lower()), None)
        assert checkov_step is not None, "Checkov スキャンステップが存在しません"


def test_prowler_gcp_workflow_exists_and_valid():
    """Prowler GCP 監査ワークフロー .github/workflows/prowler-gcp-audit.yml の構文と必須設定を検証"""
    repo_root = get_repo_root()
    prowler_path = os.path.join(repo_root, ".github", "workflows", "prowler-gcp-audit.yml")

    assert os.path.exists(prowler_path), f"prowler-gcp-audit.yml が存在しません: {prowler_path}"

    with open(prowler_path, "r", encoding="utf-8") as f:
        workflow = yaml.safe_load(f)

    assert isinstance(workflow, dict), "prowler-gcp-audit.yml の内容が辞書形式ではありません"

    triggers = workflow.get("on") or workflow.get(True)
    assert "workflow_dispatch" in triggers or "schedule" in triggers, "Prowler は手動または定期スケジュールトリガーが必要です"

    permissions = workflow.get("permissions", {})
    assert permissions.get("id-token") == "write", "GCP Workload Identity 認証のための id-token: write が必要です"

    jobs = workflow.get("jobs", {})
    assert len(jobs) >= 1, "Prowler 実行ジョブが定義されている必要があります"


def test_snyk_workflow_is_disabled():
    """既存の snyk.yml において Snyk スキャンが一時無効化（コメントアウト等）されていることを検証"""
    repo_root = get_repo_root()
    snyk_path = os.path.join(repo_root, ".github", "workflows", "snyk.yml")

    if not os.path.exists(snyk_path):
        return

    with open(snyk_path, "r", encoding="utf-8") as f:
        content = f.read()

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            assert not stripped.startswith("snyk test"), f"アクティブな snyk test が残存しています: {line}"
            assert not stripped.startswith("snyk code test"), f"アクティブな snyk code test が残存しています: {line}"
            assert not stripped.startswith("snyk iac test"), f"アクティブな snyk iac test が残存しています: {line}"
            assert not stripped.startswith("snyk container test"), f"アクティブな snyk container test が残存しています: {line}"


def test_dependabot_config_exists_and_valid():
    """Dependabot 設定ファイル .github/dependabot.yml が存在し有効な設定であることを検証"""
    repo_root = get_repo_root()
    dependabot_path = os.path.join(repo_root, ".github", "dependabot.yml")

    assert os.path.exists(dependabot_path), f"dependabot.yml が存在しません: {dependabot_path}"

    with open(dependabot_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    assert isinstance(config, dict), "dependabot.yml の内容が辞書形式ではありません"
    assert config.get("version") == 2, "dependabot.yml version は 2 である必要があります"

    updates = config.get("updates", [])
    assert len(updates) >= 2, "pip および terraform の更新設定が含まれている必要があります"

    ecosystems = [u.get("package-ecosystem") for u in updates]
    assert "pip" in ecosystems, "package-ecosystem に pip が設定されている必要があります"
    assert "terraform" in ecosystems, "package-ecosystem に terraform が設定されている必要があります"


def test_codeql_workflow_exists_and_valid():
    """GitHub CodeQL ワークフロー .github/workflows/codeql.yml の構文と必須設定を検証"""
    repo_root = get_repo_root()
    codeql_path = os.path.join(repo_root, ".github", "workflows", "codeql.yml")

    assert os.path.exists(codeql_path), f"codeql.yml が存在しません: {codeql_path}"

    with open(codeql_path, "r", encoding="utf-8") as f:
        workflow = yaml.safe_load(f)

    assert isinstance(workflow, dict), "codeql.yml の内容が辞書形式ではありません"

    triggers = workflow.get("on") or workflow.get(True)
    assert triggers is not None, "トリガー (on) が定義されていません"
    assert "pull_request" in triggers, "pull_request トリガーが定義されていません"

    permissions = workflow.get("permissions", {})
    assert permissions.get("security-events") == "write", "security-events: write 権限が必要です"

    jobs = workflow.get("jobs", {})
    assert "analyze" in jobs, "CodeQL analyze ジョブが定義されている必要があります"


def test_sonar_qualitygate_wait_configured():
    """SonarCloud ワークフローにおいて qualitygate.wait が設定されていることを検証"""
    repo_root = get_repo_root()
    sonar_path = os.path.join(repo_root, ".github", "workflows", "sonar.yml")

    assert os.path.exists(sonar_path), f"sonar.yml が存在しません: {sonar_path}"

    with open(sonar_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "-Dsonar.qualitygate.wait=true" in content, "sonar.yml に -Dsonar.qualitygate.wait=true が指定されている必要があります"


@pytest.mark.asyncio
async def test_athome_parser_human_mouse_move():
    """AthomeParser._humanMouseMove のマウス移動シミュレーションが例外なく完了することを検証"""
    class DummyAthomeParser(AthomeParser):
        def createEntity(self, *a, **k):
            pass

    parser = DummyAthomeParser()
    page = MagicMock()
    page.mouse = MagicMock()
    page.mouse.move = AsyncMock()
    await parser._humanMouseMove(page, 0, 0, 100, 100)
    assert page.mouse.move.called


def test_api_ssl_context():
    """ApiAsyncProcBase クラスの SSL コネクタ初期化が安全に構成されていることを検証"""
    class DummyProc(ApiAsyncProcBase):
        def _callApi(self, *a, **k): pass
        def _generateParser(self, *a, **k): pass
        def _getApiKey(self, *a, **k): pass
        def _getCloudPararellLimit(self, *a, **k): pass
        def _getLocalPararellLimit(self, *a, **k): pass
        def _getTimeOutSecond(self, *a, **k): pass
        def _getTreatPageArg(self, *a, **k): pass
        async def _treatPage(self, *a, **k): pass

    proc = DummyProc()
    loop = MagicMock()
    connector = proc._generateConnector(loop)
    assert connector is not None


def test_mutation_engine_run_test():
    """ASTMutationEngine のテスト実行と殺傷判定ロジックを検証"""
    engine = ASTMutationEngine()
    engine.apply_mutant = MagicMock(return_value="backup")
    engine.revert_mutant = MagicMock()
    mutant = Mutant(
        file_path="dummy.py",
        line_number=1,
        mutation_type=MutationType.COMPARE_OP,
        original_source="a > 1",
        mutated_source="a <= 1",
        ast_node_str="Gt -> LtE"
    )
    killed = engine.run_mutation_test(mutant, "python -c 'import sys; sys.exit(1)'")
    assert killed is True


def _load_workflow(name):
    path = Path(get_repo_root()) / ".github" / "workflows" / name
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _workflow_triggers(workflow):
    """PyYAML 1.1 treats the unquoted GitHub Actions key `on` as boolean True."""
    return workflow.get("on") or workflow.get(True)


def _find_step(job, *, uses=None, name=None):
    for step in job.get("steps", []):
        if uses and uses in step.get("uses", ""):
            return step
        if name and name.lower() in step.get("name", "").lower():
            return step
    raise AssertionError(f"step not found: uses={uses!r}, name={name!r}")


def test_security_scan_workflow_matches_issue_250_acceptance_criteria():
    workflow = _load_workflow("security-scan.yml")
    triggers = _workflow_triggers(workflow)

    assert set(triggers["push"]["branches"]) >= {"master"}
    assert set(triggers["pull_request"]["branches"]) >= {"master"}
    assert set(triggers["pull_request"]["types"]) == {"opened", "synchronize", "reopened"}
    assert workflow["permissions"] == {
        "contents": "read",
        "security-events": "write",
        "actions": "read",
    }

    jobs = workflow["jobs"]
    required_jobs = {"trivy-scan", "semgrep-scan", "checkov-scan"}
    assert required_jobs <= jobs.keys()
    assert all("needs" not in jobs[job_name] for job_name in required_jobs)

    trivy = _find_step(jobs["trivy-scan"], uses="aquasecurity/trivy-action")
    assert trivy["with"] == {
        "scan-type": "fs",
        "scan-ref": ".",
        "scanners": "vuln,misconfig",
        "severity": "HIGH,CRITICAL",
        "format": "sarif",
        "output": "trivy-results.sarif",
        "trivyignores": ".trivyignore",
        "exit-code": "1",
    }
    trivy_upload = _find_step(jobs["trivy-scan"], uses="upload-sarif")
    assert trivy_upload["with"] == {
        "sarif_file": "trivy-results.sarif",
        "category": "trivy",
    }
    assert trivy_upload["continue-on-error"] is True

    semgrep = _find_step(jobs["semgrep-scan"], name="Run Semgrep")
    command = semgrep["run"]
    for required_arg in [
        '--config "p/python"',
        '--config "p/owasp-top-ten"',
        '--config "p/security-audit"',
        "--severity ERROR",
        "--sarif",
        "--error",
        "--output /src/semgrep.sarif",
    ]:
        assert required_arg in command
    semgrep_upload = _find_step(jobs["semgrep-scan"], uses="upload-sarif")
    assert semgrep_upload["with"]["category"] == "semgrep"
    assert semgrep_upload["with"]["sarif_file"] == "semgrep.sarif"

    checkov = _find_step(jobs["checkov-scan"], uses="bridgecrewio/checkov-action")
    assert checkov["with"]["directory"] == "terraform"
    assert checkov["with"]["framework"] == "terraform"
    assert "sarif" in checkov["with"]["output_format"]
    assert "results.sarif" in checkov["with"]["output_file_path"]
    checkov_upload = _find_step(jobs["checkov-scan"], uses="upload-sarif")
    assert checkov_upload["with"]["category"] == "checkov"
    assert checkov_upload["with"]["sarif_file"] == "results.sarif"


def test_prowler_workflow_uses_weekly_wif_and_publishes_all_report_formats():
    workflow = _load_workflow("prowler-gcp-audit.yml")
    triggers = _workflow_triggers(workflow)

    assert triggers["schedule"] == [{"cron": "0 0 * * 1"}]
    severity = triggers["workflow_dispatch"]["inputs"]["severity"]
    assert severity["required"] is False
    assert severity["default"] == "critical,high"
    assert workflow["permissions"] == {
        "contents": "read",
        "id-token": "write",
        "security-events": "write",
    }

    job = workflow["jobs"]["prowler-gcp"]
    auth = _find_step(job, uses="google-github-actions/auth")
    assert auth["with"]["workload_identity_provider"] == "${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}"
    assert auth["with"]["service_account"] == "${{ secrets.GCP_SERVICE_ACCOUNT }}"
    assert "credentials_json" not in auth["with"]

    audit = _find_step(job, name="Run Prowler")
    for report_format in ["html", "csv", "json", "sarif"]:
        assert report_format in audit["run"]
    artifacts = _find_step(job, uses="actions/upload-artifact")
    assert artifacts["with"]["path"] == "prowler_output/"
    sarif = _find_step(job, uses="upload-sarif")
    assert sarif["with"]["category"] == "prowler-gcp"
    assert sarif["with"]["sarif_file"] == "prowler_output/"


def test_dependabot_config_covers_every_required_ecosystem_with_bounded_prs():
    config_path = Path(get_repo_root()) / ".github" / "dependabot.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    updates = {entry["package-ecosystem"]: entry for entry in config["updates"]}

    assert config["version"] == 2
    assert set(updates) == {"pip", "terraform", "npm", "github-actions", "docker"}
    assert updates["pip"]["directory"] == "/src/crawler"
    assert updates["terraform"]["directory"] == "/terraform"
    assert all(entry["schedule"]["interval"] in {"daily", "weekly"} for entry in updates.values())
    assert all(0 < entry["open-pull-requests-limit"] <= 10 for entry in updates.values())


def test_codeql_workflow_scans_python_and_actions_on_pr_push_and_schedule():
    workflow = _load_workflow("codeql.yml")
    triggers = _workflow_triggers(workflow)

    assert "master" in triggers["push"]["branches"]
    assert "master" in triggers["pull_request"]["branches"]
    assert triggers["schedule"]
    analyze = workflow["jobs"]["analyze"]
    assert set(analyze["strategy"]["matrix"]["language"]) == {"python", "actions"}
    init = _find_step(analyze, uses="github/codeql-action/init")
    assert init["with"]["languages"] == "${{ matrix.language }}"
    run = _find_step(analyze, uses="github/codeql-action/analyze")
    assert "matrix.language" in run["with"]["category"]


def test_local_security_tasks_and_ignore_files_match_ci_scope():
    repo_root = Path(get_repo_root())
    taskfile = yaml.safe_load((repo_root / "Taskfile.yml").read_text(encoding="utf-8"))
    tasks = taskfile["tasks"]

    assert {"trivy", "semgrep", "checkov", "prowler"} <= tasks.keys()
    assert "trivy fs" in tasks["trivy"]["cmds"][0]
    assert "--scanners vuln,misconfig" in tasks["trivy"]["cmds"][0]
    assert "semgrep scan" in tasks["semgrep"]["cmds"][0]
    assert "terraform/" in tasks["checkov"]["cmds"][0]
    assert "prowler" in tasks["prowler"]["cmds"][0]

    semgrep_ignored = {
        line.strip().rstrip("/")
        for line in (repo_root / ".semgrepignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert semgrep_ignored == {
        "src/crawler/scripts/ops",
        "src/crawler/scripts/node",
        "src/crawler/package/testing",
        "src/crawler/tests",
    }
    trivy_ignore = (repo_root / ".trivyignore").read_text(encoding="utf-8")
    assert "DS-0002" in trivy_ignore
    assert "DS-0026" in trivy_ignore


def test_review_gate_ignores_coderabbit_checkbox_metadata():
    review_gate = Path(get_repo_root()) / ".github" / "workflows" / "review-gate.yml"
    source = review_gate.read_text(encoding="utf-8")

    assert "line.includes('radioGroupId')" in source
    assert "line.includes('checkboxId')" in source
    assert "line.includes('Fix all pre-merge checks with AI')" in source

