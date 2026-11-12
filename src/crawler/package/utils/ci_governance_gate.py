"""CI Governance 4-Gate Evaluator (Issue #1395).

Pure standard-library module executed via stdin/stdout by `.github/workflows/issue-gate.yml`
(`Verify GitHub Issue Association`, enforced on `master` with `enforce_admins: true`) to mechanically prevent ANY deviation from:
  - Gate A: Issue-Driven Development (Closes/Fixes/Resolves #N, [#N] title, branch N token, OPEN Issue, issue.created_at <= pr.created_at)
  - Gate B: Acceptance Criteria & PR Checklist Completion (total > 0 & 0 unchecked in Issue, 0 unchecked in PR body)
  - Gate C: Spec-Driven Development / SDD (7-domain docs/[1-7]_*/*.md required when code/infra/CI/.agents change)
  - Gate D: Test-Driven Development / TDD (src/crawler/tests/**/*.py required when executable .py or workflow .yml/.yaml change)
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime

CLOSING_ISSUE_RE = re.compile(r"\b(?:close[sd]?|fixe?[sd]?|resolve[sd]?)\s+#(\d+)\b", re.IGNORECASE)
TITLE_PREFIX_RE = re.compile(r"^\[#(\d+)\]\s+\S")
TESTS_DIR_PREFIX = "src/crawler/tests/"


def _verdict(
    passed: bool,
    *,
    issue_number: int | None = None,
    auto_close: bool = False,
    fail_reason: str = "",
    comment_body: str = "",
) -> dict:
    return {
        "passed": passed,
        "issue_number": issue_number,
        "auto_close": auto_close,
        "fail_reason": fail_reason,
        "comment_body": comment_body,
    }


def _parse_iso_timestamp(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized)


def _branch_contains_exact_issue(head_ref: str, issue_number: int) -> bool:
    tokens = re.findall(r"\d+", head_ref)
    return any(int(tok) == issue_number and tok == str(issue_number) for tok in tokens)


def _strip_fenced_code_blocks(markdown_text: str) -> list[str]:
    in_fence = False
    kept: list[str] = []
    for line in markdown_text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if not in_fence:
            kept.append(line)
    return kept


def _parse_checkbox_line(raw_line: str) -> tuple[str, str] | None:
    stripped = raw_line.strip()
    if len(stripped) < 4 or stripped[0] not in ("-", "*"):
        return None
    rest = stripped[1:].lstrip()
    if len(rest) < 3 or rest[0] != "[" or rest[2] != "]":
        return None
    marker = rest[1]
    if marker not in (" ", "x", "X"):
        return None
    item = rest[3:].strip()
    if not item:
        return None
    return marker, item


def _extract_checkboxes(lines: list[str]) -> tuple[list[str], list[str]]:
    checked: list[str] = []
    unchecked: list[str] = []
    for raw_line in lines:
        parsed = _parse_checkbox_line(raw_line)
        if parsed is None:
            continue
        status, item = parsed
        if status.lower() == "x":
            checked.append(item)
        else:
            unchecked.append(item)
    return checked, unchecked


def _is_seven_domain_spec(path: str) -> bool:
    if not path.endswith(".md"):
        return False
    parts = path.split("/")
    if len(parts) < 3 or parts[0] != "docs":
        return False
    domain = parts[1]
    return len(domain) >= 3 and domain[0] in "1234567" and domain[1] == "_"


def _is_unit_test_file(path: str) -> bool:
    return path.startswith(TESTS_DIR_PREFIX) and path.endswith(".py") and len(path) > len(TESTS_DIR_PREFIX) + 3


def _check_pr_metadata_and_issue_link(pr: dict, owner: str, repo: str) -> tuple[int | None, dict | None]:
    body = str(pr.get("body") or "")
    body_match = CLOSING_ISSUE_RE.search(body)
    if not body_match:
        msg = (
            "⛔ **PR自動クローズ (Issue未紐付け)**: Issueなしの Pull Request は禁止されています。\n\n"
            f"1. [GitHub Issues](https://github.com/{owner}/{repo}/issues) で OPEN チケットを先行起票してください。\n"
            "2. PR 本文に `Closes #<Issue番号>`、タイトル先頭に `[#<Issue番号>] ` を明記して Reopen してください。"
        )
        return None, _verdict(
            False,
            auto_close=True,
            fail_reason="Issue-Driven Violation: No explicit Closes/Fixes/Resolves #<IssueNumber> in PR body.",
            comment_body=msg,
        )

    issue_number = int(body_match.group(1))
    title = str(pr.get("title") or "")
    title_match = TITLE_PREFIX_RE.match(title)
    if not title_match or int(title_match.group(1)) != issue_number:
        msg = (
            f"⛔ **マージ不可 (PRタイトル規約違反)**: PRタイトル先頭は `[#{issue_number}] <要約>` 形式で、"
            f"本文の `Closes #{issue_number}` と完全一致している必要があります（現在: `{title}`）。"
        )
        return issue_number, _verdict(
            False,
            issue_number=issue_number,
            fail_reason=f"Issue-Driven Violation: PR title must start with '[#{issue_number}] ' matching PR body.",
            comment_body=msg,
        )

    head_ref = str(pr.get("head_ref") or "")
    if not _branch_contains_exact_issue(head_ref, issue_number):
        msg = (
            f"⛔ **マージ不可 (ブランチ名不整合)**: 作業ブランチ `{head_ref}` に Issue 番号 `{issue_number}` が"
            "独立トークンとして含まれていません。"
        )
        return issue_number, _verdict(
            False,
            issue_number=issue_number,
            fail_reason=f"Issue-Driven Violation: Source branch '{head_ref}' does not match Issue #{issue_number}.",
            comment_body=msg,
        )

    return issue_number, None


def _check_issue_state_and_chronology(pr: dict, issue: dict, issue_number: int) -> dict | None:
    if not issue.get("exists", False):
        return _verdict(
            False,
            issue_number=issue_number,
            auto_close=True,
            fail_reason=f"Issue-Driven Violation: Issue #{issue_number} does not exist.",
            comment_body=f"⛔ **PR自動クローズ (無効なIssue番号)**: Issue #{issue_number} が存在しません。",
        )

    if issue.get("is_pull_request", False):
        return _verdict(
            False,
            issue_number=issue_number,
            auto_close=True,
            fail_reason=f"Issue-Driven Violation: #{issue_number} is a Pull Request, not a GitHub Issue.",
            comment_body=f"⛔ **PR自動クローズ (PR番号誤指定)**: #{issue_number} は Issue ではなく Pull Request です。",
        )

    state = str(issue.get("state") or "")
    if state != "open":
        return _verdict(
            False,
            issue_number=issue_number,
            auto_close=True,
            fail_reason=f"Issue-Driven Violation: Issue #{issue_number} is not open (state={state}).",
            comment_body=f"⛔ **PR自動クローズ (クローズ済みIssue指定)**: Issue #{issue_number} は `{state}` 状態です。",
        )

    issue_created = _parse_iso_timestamp(str(issue.get("created_at") or ""))
    pr_created = _parse_iso_timestamp(str(pr.get("created_at") or ""))
    if issue_created > pr_created:
        msg = (
            f"⛔ **マージ不可 (事後Issue起票違反)**: Issue #{issue_number} の作成時刻 (`{issue.get('created_at')}`) が "
            f"PR 作成時刻 (`{pr.get('created_at')}`) より後になっています。必ず Issue 先行起票を厳守してください。"
        )
        return _verdict(
            False,
            issue_number=issue_number,
            fail_reason=f"Issue-First Violation: Issue #{issue_number} was created after PR creation.",
            comment_body=msg,
        )

    return None


def _check_criteria_and_pr_checklist(pr: dict, issue: dict, issue_number: int) -> dict | None:
    issue_lines = _strip_fenced_code_blocks(str(issue.get("body") or ""))
    checked, unchecked = _extract_checkboxes(issue_lines)
    total = len(checked) + len(unchecked)
    if total == 0:
        return _verdict(
            False,
            issue_number=issue_number,
            fail_reason=f"Issue #{issue_number} does not define any Acceptance Criteria checkboxes.",
            comment_body=f"⛔ **マージ不可 (受入基準未定義)**: Issue #{issue_number} に受入基準チェックボックスがありません。",
        )

    if unchecked:
        items = "\n".join(f"- ☐ {item}" for item in unchecked)
        return _verdict(
            False,
            issue_number=issue_number,
            fail_reason=f"Issue #{issue_number} has {len(unchecked)} unchecked Acceptance Criteria.",
            comment_body=(
                f"⛔ **マージ不可 (受入基準未達)**: Issue #{issue_number} に未完了の受入基準があります "
                f"({len(checked)}/{total} 完了)。\n\n{items}"
            ),
        )

    pr_lines = _strip_fenced_code_blocks(str(pr.get("body") or ""))
    _, pr_unchecked = _extract_checkboxes(pr_lines)
    if pr_unchecked:
        return _verdict(
            False,
            issue_number=issue_number,
            fail_reason=f"PR body contains {len(pr_unchecked)} unchecked checklist item(s).",
            comment_body="⛔ **マージ不可 (PRチェックリスト未完了)**: PR 本文内に未完了チェックリスト項目が残っています。",
        )

    return None


def _requires_sdd_spec(path: str) -> bool:
    if path.startswith("src/") and not path.startswith(TESTS_DIR_PREFIX):
        return True
    return path.startswith(("terraform/", ".github/workflows/", ".agents/"))


def _requires_tdd_test(path: str) -> bool:
    if path.startswith("src/") and not path.startswith(TESTS_DIR_PREFIX) and path.endswith(".py"):
        return True
    if path.startswith(".agents/scripts/") and path.endswith(".py"):
        return True
    return path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml"))


def _check_sdd_and_tdd_files(files: list[str], issue_number: int) -> dict | None:
    norm_files = [f.replace("\\", "/").removeprefix("./") for f in files]
    needs_sdd = any(_requires_sdd_spec(f) for f in norm_files)
    has_7_domain_spec = any(_is_seven_domain_spec(f) for f in norm_files)
    if needs_sdd and not has_7_domain_spec:
        msg = (
            "⛔ **マージ不可 (SDD / スペックドリブン違反)**: 実装コード・インフラ・CI・エージェント設定の変更が含まれていますが、"
            "7大ドメイン正本仕様書（`docs/1_architecture/` 〜 `docs/7_operations_and_improvement/*.md`）の更新がありません。"
        )
        return _verdict(
            False,
            issue_number=issue_number,
            fail_reason="SDD Violation: Missing 7-domain SSOT specification update (docs/1_... through docs/7_.../*.md).",
            comment_body=msg,
        )

    needs_tdd = any(_requires_tdd_test(f) for f in norm_files)
    has_unit_test = any(_is_unit_test_file(f) for f in norm_files)
    if needs_tdd and not has_unit_test:
        msg = (
            "⛔ **マージ不可 (TDD / テストドリブン違反)**: 実行コードまたは CI ワークフローの変更が含まれていますが、"
            "`src/crawler/tests/**/*.py` 配下の単体テスト追加・更新が含まれていません。"
        )
        return _verdict(
            False,
            issue_number=issue_number,
            fail_reason="TDD Violation: Missing unit test addition/update under src/crawler/tests/**/*.py.",
            comment_body=msg,
        )

    return None


def evaluate_pr_governance(payload: dict) -> dict:
    pr = payload.get("pr") or {}
    if str(pr.get("user_login") or "") == "dependabot[bot]":
        return _verdict(True)

    owner = str(payload.get("repo_owner") or "")
    repo = str(payload.get("repo_name") or "")
    issue_number, meta_err = _check_pr_metadata_and_issue_link(pr, owner, repo)
    if meta_err is not None or issue_number is None:
        return meta_err  # type: ignore[return-value]

    issue = payload.get("issue") or {}
    issue_err = _check_issue_state_and_chronology(pr, issue, issue_number)
    if issue_err is not None:
        return issue_err

    criteria_err = _check_criteria_and_pr_checklist(pr, issue, issue_number)
    if criteria_err is not None:
        return criteria_err

    files = [str(f) for f in (payload.get("files") or [])]
    sdd_tdd_err = _check_sdd_and_tdd_files(files, issue_number)
    if sdd_tdd_err is not None:
        return sdd_tdd_err

    return _verdict(True, issue_number=issue_number)


def run_stdio(raw_json: str) -> str:
    payload = json.loads(raw_json)
    verdict = evaluate_pr_governance(payload)
    return json.dumps(verdict, ensure_ascii=False)


if __name__ == "__main__":  # pragma: no cover
    sys.stdout.write(run_stdio(sys.stdin.read()))
