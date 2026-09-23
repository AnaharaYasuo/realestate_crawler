"""
CI/CD高速化およびPRレビューゲート滞留根絶の単体テスト (Issue #368)。
受入基準:
- 【基準1】Dockerfileで `playwright install --with-deps chromium` を `COPY config/` / `COPY src/` 前に配置
- 【基準2】`.github/workflows/review-gate.yml` の `workflow_run.workflows` に Parser Tests と SonarCloud Analysis を追加
- 【基準3】`test.yml` と `sonar.yml` の重複テストを排除しカバレッジ連携
- 【基準4】`test.yml` の Unit / Mutation テストにおいて不要な MySQL 起動をスキップ
- 【基準5】プッシュ前ローカル事前検証タスク (`task ci:precheck`) の配備
"""
import os

import yaml


def get_repo_root():
    """リポジトリルートディレクトリを返す"""
    cur = os.path.abspath(os.path.dirname(__file__))
    for _ in range(6):
        if os.path.exists(os.path.join(cur, "Dockerfile")) and os.path.exists(os.path.join(cur, "Taskfile.yml")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))


def test_dockerfile_playwright_layer_cached_before_src_copy():
    """【基準1】Dockerfileで playwright install が COPY config/ / COPY src/ より前に配置されていることを検証"""
    repo_root = get_repo_root()
    dockerfile_path = os.path.join(repo_root, "Dockerfile")
    assert os.path.exists(dockerfile_path), f"Dockerfile が存在しません: {dockerfile_path}"

    with open(dockerfile_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()
    playwright_line = -1
    copy_src_line = -1
    copy_config_line = -1

    for idx, line in enumerate(lines):
        clean = line.strip()
        if clean.startswith("RUN playwright install --with-deps chromium"):
            playwright_line = idx
        elif clean.startswith(("COPY src/", "COPY src ")):
            copy_src_line = idx
        elif clean.startswith(("COPY config/", "COPY config ")):
            copy_config_line = idx

    assert playwright_line != -1, "Dockerfile に 'RUN playwright install --with-deps chromium' が見つかりません"
    assert copy_src_line != -1, "Dockerfile に 'COPY src/' が見つかりません"
    assert copy_config_line != -1, "Dockerfile に 'COPY config/' が見つかりません"

    assert playwright_line < copy_src_line, (
        f"playwright install (L{playwright_line+1}) は COPY src/ (L{copy_src_line+1}) より前に配置する必要があります"
    )
    assert playwright_line < copy_config_line, (
        f"playwright install (L{playwright_line+1}) は COPY config/ (L{copy_config_line+1}) より前に配置する必要があります"
    )


def test_review_gate_triggers_on_parser_tests_and_sonar():
    """【基準2】review-gate.yml の workflow_run.workflows に Parser Tests と SonarCloud Analysis が含まれ types: [completed] であることを検証"""
    repo_root = get_repo_root()
    gate_path = os.path.join(repo_root, ".github/workflows/review-gate.yml")
    assert os.path.exists(gate_path), f"review-gate.yml が存在しません: {gate_path}"

    with open(gate_path, "r", encoding="utf-8") as f:
        wf = yaml.safe_load(f)

    # on は YAML パーサーによっては True キーとしてロードされる場合がある
    on_trigger = wf.get("on") or wf.get(True) or {}
    assert isinstance(on_trigger, dict), "review-gate.yml の on トリガーが辞書形式ではありません"

    workflow_run = on_trigger.get("workflow_run", {})
    workflows = workflow_run.get("workflows", [])
    types = workflow_run.get("types", [])

    assert "completed" in types, "review-gate.yml の on.workflow_run.types に 'completed' が含まれていません"
    assert "Parser Tests" in workflows, (
        "review-gate.yml の on.workflow_run.workflows に 'Parser Tests' が含まれていません"
    )
    assert "SonarCloud Analysis" in workflows, (
        "review-gate.yml の on.workflow_run.workflows に 'SonarCloud Analysis' が含まれていません"
    )


def test_test_yml_skips_db_for_unit_and_mutation():
    """【基準4】test.yml において unit および mutation テストが needs_db: false かつ --no-deps で起動されることを検証"""
    repo_root = get_repo_root()
    test_yml_path = os.path.join(repo_root, ".github/workflows/test.yml")
    assert os.path.exists(test_yml_path), f"test.yml が存在しません: {test_yml_path}"

    with open(test_yml_path, "r", encoding="utf-8") as f:
        wf = yaml.safe_load(f)

    jobs = wf.get("jobs", {})
    test_matrix = jobs.get("test-matrix", {})
    strategy = test_matrix.get("strategy", {})
    matrix = strategy.get("matrix", {})
    includes = matrix.get("include", [])

    matrix_by_group = {item.get("group"): item for item in includes}

    assert "unit" in matrix_by_group, "test-matrix に group: unit が定義されていません"
    assert "mutation" in matrix_by_group, "test-matrix に group: mutation が定義されていません"
    assert "integration" in matrix_by_group, "test-matrix に group: integration が定義されていません"

    assert matrix_by_group["unit"].get("needs_db") is False, "group: unit は needs_db: false である必要があります"
    assert matrix_by_group["mutation"].get("needs_db") is False, "group: mutation は needs_db: false である必要があります"
    assert matrix_by_group["integration"].get("needs_db") is True, "group: integration は needs_db: true である必要があります"

    steps = test_matrix.get("steps", [])
    no_db_step = next((s for s in steps if s.get("name") == "Start app container (no DB)"), None)
    assert no_db_step is not None, "'Start app container (no DB)' ステップが見つかりません"
    assert "--no-deps" in no_db_step.get("run", ""), (
        "DB不要ステップに '--no-deps' オプションが指定されていません"
    )


def test_taskfile_has_ci_precheck():
    """【基準5】Taskfile.yml にローカル事前検証タスク ci:precheck が定義され、主要検証を含むことを検証"""
    repo_root = get_repo_root()
    taskfile_path = os.path.join(repo_root, "Taskfile.yml")
    assert os.path.exists(taskfile_path), f"Taskfile.yml が存在しません: {taskfile_path}"

    with open(taskfile_path, "r", encoding="utf-8") as f:
        taskfile = yaml.safe_load(f)

    tasks = taskfile.get("tasks", {})
    assert "ci:precheck" in tasks, "Taskfile.yml に 'ci:precheck' タスクが定義されていません"

    cmds = tasks["ci:precheck"].get("cmds", [])
    cmds_str = " ".join(cmds)
    assert "ruff check" in cmds_str, "ci:precheck に 'ruff check' が含まれていません"
    assert "check_local_sonar.py" in cmds_str, "ci:precheck に 'check_local_sonar.py' が含まれていません"
    assert "pytest" in cmds_str, "ci:precheck に 'pytest' が含まれていません"
    assert "run_mutation_testing.py" in cmds_str, "ci:precheck に 'run_mutation_testing.py' が含まれていません"
