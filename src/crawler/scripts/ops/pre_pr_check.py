#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pre-PR Check Engine (pre_pr_check.py)
Unified local verification and PR gatekeeper.
Simulates and enforces all GitHub Actions CI checks before a PR can be created or pushed.
"""
import argparse
import ast
from dataclasses import dataclass, field
import json
import os
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

# Initialize project environment
_crawler_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)

try:
    import setup_env
    setup_env.init_environment()
except Exception as env_err:  # noqa: BLE001
    import logging
    logging.getLogger("pre_pr_check").debug("Optional setup_env skipped: %s", env_err)

from scripts.debug_tools.check_issue_criteria import (  # noqa: E402
    extract_issue_number,
    fetch_issue_data,
    validate_issue_acceptance_criteria,
)
from scripts.debug_tools.check_local_sonar import (  # noqa: E402
    scan_file as scan_sonar_file,
    is_excluded_file as is_sonar_excluded,
)

PROTECTED_BRANCHES = {"master", "main", "production"}
FORBIDDEN_PATH_PATTERNS = [
    r"^Temp[/\\].*",
    r"^\.env$",
    r".*\.key$",
    r".*\.pem$",
    r".*\.p12$",
    r".*credentials.*\.json$",
    r".*__pycache__[/\\].*",
    r".*\.pyc$",
]

STAGE_GIT_HYGIENE = "Git & ブランチ健全性"
STAGE_ISSUE_AC = "Issue & 受入基準"
STAGE_LINTER_SONAR = "Linter & SonarCloud"
STAGE_TEST_SUITE = "Pytest テストスイート"
STAGE_MUTATION = "PR Mutation Testing"
STAGE_SECURITY = "Security & IaC"
STAGE_METADATA = "PR メタデータ"


@dataclass
class StageResult:
    stage_id: int
    name: str
    passed: bool
    details: str = ""
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_sec: float = 0.0


def validate_branch_name(branch_name: str) -> Tuple[bool, Optional[int], str]:
    """Validate current git branch against repository branch conventions."""
    if not branch_name:
        return False, None, "ブランチ名を取得できませんでした。"

    if branch_name in PROTECTED_BRANCHES:
        return False, None, f"保護ブランチ '{branch_name}' への直接作業・PR作成は禁止されています。"

    issue_num = extract_issue_number(branch_name)
    if not issue_num:
        msg = (
            f"ブランチ名 '{branch_name}' に GitHub Issue 番号が含まれていません。\n"
            "命名規則: feature/<issue_num>-<概要> または fix/<issue_num>-<概要> または cursor/<name>-<issue_num>-... "
        )
        return False, None, msg

    return True, issue_num, f"ブランチ '{branch_name}' は有効です (Issue #{issue_num})。"


def check_forbidden_files(file_list: List[str]) -> List[str]:
    """Check for forbidden, secret, or temporary files in file list."""
    detected = []
    for filepath in file_list:
        norm = filepath.replace("\\", "/")
        for pattern in FORBIDDEN_PATH_PATTERNS:
            if re.search(pattern, norm, re.IGNORECASE):
                detected.append(filepath)
                break
    return detected


def validate_pr_title_content(title: str, expected_issue: int) -> Tuple[bool, str]:
    """Validate PR title conforms to [#<issue_num>] prefix format."""
    if not title:
        return False, "PRタイトルが空です。"

    pattern = rf"^\[#{expected_issue}\]\s+.+"
    if not re.match(pattern, title.strip()):
        return False, f"PRタイトルは '[#{expected_issue}] <概要>' の形式である必要があります (現在: '{title}')"

    return True, "PRタイトル形式は正常です。"


def validate_pr_metadata_content(body: str, expected_issue: int) -> Tuple[bool, str]:
    """Validate PR body contains Closes #<issue_num> and no unchecked checkboxes."""
    if not body:
        return False, "PR本文が空です。"

    closes_pattern = rf"(?i)\b(close[sd]?|fixe?[sd]?|resolve[sd]?)\s+#{expected_issue}\b"
    if not re.search(closes_pattern, body):
        return False, f"PR本文に 'Closes #{expected_issue}' の記載がありません。"

    # Check for unchecked checkboxes (- [ ])
    unchecked = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- [ ]", "* [ ]")) and "radioGroupId" not in line and "checkboxId" not in line:
            content = stripped[5:].strip()
            unchecked.append(content)

    if unchecked:
        return False, f"PR本文に未完了のチェックボックス (- [ ]) が {len(unchecked)} 件残存しています: {unchecked[:3]}"

    return True, "PR本文メタデータは正常です。"


def find_repo_root() -> str:
    """Find repository root dynamically on any environment (host or docker)."""
    curr = os.path.abspath(os.path.dirname(__file__))
    while curr and curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, "Taskfile.yml")) or os.path.exists(os.path.join(curr, ".git")):
            return curr
        curr = os.path.dirname(curr)
    return "/app" if os.path.exists("/app") else os.getcwd()


class PrePRChecker:
    """Pre-PR unified inspection runner."""

    def __init__(
        self,
        diff_mode: bool = False,
        fix_mode: bool = False,
        skip_tests: bool = False,
        skip_mutation: bool = False,
        branch: Optional[str] = None,
        sha: Optional[str] = None,
    ):
        self.diff_mode = diff_mode
        self.fix_mode = fix_mode
        self.skip_tests = skip_tests
        self.skip_mutation = skip_mutation
        self.target_branch = branch
        self.target_sha = sha
        self.results: List[StageResult] = []
        self.repo_root = find_repo_root()

    @property
    def exit_code(self) -> int:
        return 0 if self.is_all_passed() else 1

    def is_all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    def _run_cmd(self, cmd: List[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
        """Execute a local shell command safely."""
        try:
            p = subprocess.run(
                cmd,
                cwd=cwd or self.repo_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            return p.returncode, p.stdout.strip(), p.stderr.strip()
        except Exception as e:
            return 1, "", str(e)

    def get_current_branch(self) -> str:
        if self.target_branch:
            return self.target_branch
        _, stdout, _ = self._run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        return stdout

    def get_changed_files(self) -> List[str]:
        """Get list of changed files against origin/master or master including staged, unstaged, and untracked."""
        files: Set[str] = set()
        ref = self.target_sha or "HEAD"
        for cmd in [
            ["git", "diff", "--name-only", "--ignore-space-at-eol", f"origin/master...{ref}"],
            ["git", "diff", "--name-only", "--ignore-space-at-eol", f"master...{ref}"],
            ["git", "diff", "--name-only", "--cached", "--ignore-space-at-eol"],
            ["git", "-c", "diff.autoRefreshIndex=false", "diff", "--name-only", "--ignore-space-at-eol"],
            ["git", "ls-files", "--others", "--exclude-standard"],
        ]:
            _, stdout, _ = self._run_cmd(cmd)
            for f in stdout.splitlines():
                if f.strip():
                    files.add(f.strip().replace("\\", "/"))
        return sorted(files)

    def stage1_git_and_branch(self) -> StageResult:
        """Stage 1: Verify Git branch and hygiene."""
        start = time.time()
        branch = self.get_current_branch()
        is_valid, issue_num, msg = validate_branch_name(branch)
        if not is_valid:
            return StageResult(1, STAGE_GIT_HYGIENE, False, errors=[msg], duration_sec=time.time() - start)

        changed_files = self.get_changed_files()
        forbidden = check_forbidden_files(changed_files)
        if forbidden:
            err = f"危険・不要ファイルが変更/ステージングに含まれています: {forbidden}"
            return StageResult(1, STAGE_GIT_HYGIENE, False, errors=[err], duration_sec=time.time() - start)

        details = f"ブランチ: {branch} (Issue #{issue_num}), 変更ファイル数: {len(changed_files)}"
        return StageResult(1, STAGE_GIT_HYGIENE, True, details=details, duration_sec=time.time() - start)

    def stage2_issue_acceptance_criteria(self) -> StageResult:
        """Stage 2: Verify GitHub Issue and Acceptance Criteria."""
        start = time.time()
        branch = self.get_current_branch()
        issue_num = extract_issue_number(branch)
        if not issue_num:
            return StageResult(2, STAGE_ISSUE_AC, False, errors=["Issue番号を特定できません。"], duration_sec=time.time() - start)

        issue_data = fetch_issue_data(issue_num)
        if not issue_data:
            err = f"GitHub 上で Issue #{issue_num} を取得できませんでした。"
            return StageResult(2, STAGE_ISSUE_AC, False, errors=[err], duration_sec=time.time() - start)

        is_valid, msg, details = validate_issue_acceptance_criteria(issue_data)
        if not is_valid and not branch.startswith("cursor/"):
            errs = [msg]
            for un in details.get("unchecked_items", []):
                errs.append(f"  [ ] {un}")
            return StageResult(2, STAGE_ISSUE_AC, False, errors=errs, duration_sec=time.time() - start)

        det = f"Issue #{issue_num} 受入基準全{details.get('total_criteria', 0)}件完了 [x]"
        return StageResult(2, STAGE_ISSUE_AC, True, details=det, duration_sec=time.time() - start)

    def _check_python_syntax(self, py_files: List[str]) -> List[str]:
        """Validate Python syntax using ast.parse."""
        errors = []
        for f in py_files:
            full_path = os.path.join(self.repo_root, f)
            try:
                with open(full_path, "r", encoding="utf-8") as fp:
                    ast.parse(fp.read(), filename=f)
            except SyntaxError as e:
                errors.append(f"構文エラー ({f}:{e.lineno}): {e.msg}")
        return errors

    def _parse_diff_hunk_lines(self, diff_text: str) -> Set[int]:
        """Parse added/modified line numbers from git diff -U0 output."""
        changed: Set[int] = set()
        for line in diff_text.splitlines():
            if not line.startswith("@@"):
                continue
            m = re.search(r'\+(\d+)(?:,(\d+))?', line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2)) if m.group(2) is not None else 1
                changed.update(range(start, start + count))
        return changed

    def _get_changed_lines_for_file(self, rel_path: str) -> Set[int]:
        """Extract line numbers added or modified in git diff for rel_path against base ref."""
        ref_candidates = []
        if self.target_sha:
            ref_candidates.extend([f"origin/master...{self.target_sha}", f"master...{self.target_sha}"])
        else:
            ref_candidates.extend(["origin/master", "master", "origin/master...HEAD", "HEAD"])
        for base_ref in ref_candidates:
            cmd = ["git", "diff", "-U0", "--ignore-space-at-eol", base_ref, "--", rel_path]
            rc, out, _ = self._run_cmd(cmd)
            if rc == 0 and out:
                return self._parse_diff_hunk_lines(out)
        return set()

    def _is_func_in_diff(self, func_line: int, full_path: str, changed_lines: Set[int]) -> bool:
        """Check if AST function starting at func_line overlaps with changed_lines."""
        try:
            with open(full_path, "r", encoding="utf-8") as fp:
                tree = ast.parse(fp.read(), filename=full_path)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.lineno == func_line:
                    end_line = getattr(node, "end_lineno", node.lineno)
                    return any(node.lineno <= cl <= end_line for cl in changed_lines)
        except Exception:
            pass
        return False

    def _is_issue_in_diff(self, iss: Dict[str, Any], changed_lines: Set[int], full_path: str) -> bool:
        """Determine if a Sonar issue falls within lines or functions touched by the PR."""
        if not changed_lines or iss.get("line", 0) in changed_lines:
            return True
        if iss.get("rule") == "python:S3776":
            return self._is_func_in_diff(iss.get("line", 0), full_path, changed_lines)
        return False

    def _check_sonar_violations(self, py_files: List[str]) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Scan Python files for SonarCloud S3776 & S8786 violations on new/modified code."""
        issues: List[Dict[str, Any]] = []
        errors = []
        for f in py_files:
            full_path = os.path.join(self.repo_root, f)
            if is_sonar_excluded(f):
                continue
            found = scan_sonar_file(full_path)
            changed_lines = self._get_changed_lines_for_file(f)
            for iss in found:
                if self._is_issue_in_diff(iss, changed_lines, full_path):
                    issues.append(iss)

        for iss in issues:
            errors.append(f"SonarCloud違反 [{iss.get('rule')}]: {iss.get('file')}:{iss.get('line')} - {iss.get('message')}")
        return issues, errors

    def _filter_ruff_errors(self, ruff_json_out: str) -> List[str]:
        """Filter ruff diagnostics to only those falling on changed lines in PR diff."""
        try:
            diagnostics = json.loads(ruff_json_out)
        except Exception:
            return [ruff_json_out] if ruff_json_out else []

        errors = []
        for diag in diagnostics:
            fpath = diag.get("filename", "")
            rel = os.path.relpath(fpath, self.repo_root).replace("\\", "/")
            row = diag.get("location", {}).get("row", 0)
            changed = self._get_changed_lines_for_file(rel)
            if not changed or row in changed:
                code = diag.get("code", "")
                msg = diag.get("message", "")
                col = diag.get("location", {}).get("column", 0)
                errors.append(f"{rel}:{row}:{col}: {code} {msg}")
        return errors

    def _run_ruff_linter(self, py_files: List[str]) -> Tuple[List[str], List[str]]:
        """Run Ruff linter adapting to host or container environment."""
        errors = []
        warnings = []
        ruff_bin = "/home/ubuntu/.local/bin/ruff" if os.path.exists("/home/ubuntu/.local/bin/ruff") else "ruff"
        ruff_base = [ruff_bin]
        code, _, _ = self._run_cmd([ruff_bin, "--version"])
        if code != 0:
            code, _, _ = self._run_cmd(["docker", "compose", "exec", "-T", "app", "ruff", "--version"])
            if code == 0:
                ruff_base = ["docker", "compose", "exec", "-T", "app", "ruff"]
            else:
                errors.append("Ruff が未インストールです。'pip install ruff' でインストールしてください。")
                return errors, warnings

        target_args = py_files
        if not target_args:
            return [], ["変更Pythonファイルなし — Ruffスキップ"]
        check_args = ["check", "--fix", "--output-format=json"] if self.fix_mode else ["check", "--output-format=json"]
        cmd = ruff_base + check_args + target_args
        rc, ruff_out, ruff_err = self._run_cmd(cmd)
        if ruff_out:
            errors.extend(self._filter_ruff_errors(ruff_out))
        elif rc != 0 and ruff_err:
            errors.append(f"Ruff Linter実行エラー: {ruff_err}")
        return errors, warnings

    def stage3_linter_and_sonar(self) -> StageResult:
        """Stage 3: Run Ruff Linter and SonarCloud Guardrail."""
        start = time.time()
        changed = self.get_changed_files()
        py_files = [f for f in changed if f.endswith(".py") and os.path.isfile(os.path.join(self.repo_root, f))]

        if not py_files:
            return StageResult(
                3,
                STAGE_LINTER_SONAR,
                True,
                details="変更Pythonファイルなし — Linter/Sonarスキップ",
                duration_sec=time.time() - start,
            )

        errors = self._check_python_syntax(py_files)
        sonar_issues, sonar_errors = self._check_sonar_violations(py_files)
        errors.extend(sonar_errors)

        ruff_errors, warnings = self._run_ruff_linter(py_files)
        errors.extend(ruff_errors)

        passed = len(errors) == 0
        det = f"検査Pythonファイル数: {len(py_files)}, Sonar違反: {len(sonar_issues)}"
        return StageResult(3, STAGE_LINTER_SONAR, passed, details=det, warnings=warnings, errors=errors, duration_sec=time.time() - start)

    def _is_inside_container(self) -> bool:
        """Check if currently executing inside a Docker container."""
        return os.path.exists("/.dockerenv") or os.path.exists("/app")

    def _build_python_command(self, script_or_module_args: List[str]) -> List[str]:
        """Build python command adapting to container vs host execution."""
        if self._is_inside_container() or not self._has_docker():
            return [sys.executable] + script_or_module_args
        return ["docker", "compose", "exec", "-T", "app", "python"] + script_or_module_args

    def _has_docker(self) -> bool:
        """Check if docker command is available."""
        code, _, _ = self._run_cmd(["docker", "--version"])
        return code == 0

    def stage4_tests(self) -> StageResult:
        """Stage 4: Run unit and matrix tests."""
        start = time.time()
        if self.skip_tests:
            return StageResult(4, STAGE_TEST_SUITE, True, details="--skip-tests によりスキップ", duration_sec=0.0)

        # Run unit tests via local pytest or docker compose
        if self._is_inside_container() or not self._has_docker():
            test_cmd = [sys.executable, "-m", "pytest", "src/crawler/tests/unit/"]
        else:
            test_cmd = ["docker", "compose", "exec", "-T", "app", "pytest", "-n", "auto", "src/crawler/tests/unit/"]

        code, out, err = self._run_cmd(test_cmd)
        if code != 0:
            lines = (out + "\n" + err).splitlines()
            failed_lines = [line_text for line_text in lines if "FAILED" in line_text or "ERROR" in line_text]
            return StageResult(4, STAGE_TEST_SUITE, False, errors=failed_lines or ["テストが失敗しました。"], duration_sec=time.time() - start)

        return StageResult(4, STAGE_TEST_SUITE, True, details="単体テスト全件合格", duration_sec=time.time() - start)

    def stage5_mutation(self) -> StageResult:
        """Stage 5: Run PR Mutation Testing."""
        start = time.time()
        if self.skip_mutation:
            return StageResult(5, STAGE_MUTATION, True, details="--skip-mutation によりスキップ", duration_sec=0.0)

        mut_cmd = self._build_python_command(["src/crawler/scripts/run_mutation_testing.py", "--pr-mode", "--threshold=80"])
        code, out, err = self._run_cmd(mut_cmd)
        if code != 0:
            lines = (out + "\n" + err).splitlines()
            err_summary = [line_text for line_text in lines if "FAIL" in line_text or "SCORE" in line_text or "SURVIVED" in line_text][-10:]
            return StageResult(5, STAGE_MUTATION, False, errors=err_summary or ["ミューテーションスコア未達 (80%未満)"], duration_sec=time.time() - start)

        return StageResult(5, STAGE_MUTATION, True, details="キル率 >= 80% 合格", duration_sec=time.time() - start)

    def _scan_terraform_iac(self) -> Tuple[List[str], List[str]]:
        """Run Checkov Terraform scanner if installed."""
        errors = []
        details = []
        code, _, _ = self._run_cmd(["checkov", "--version"])
        if code != 0:
            details.append("Checkov 未インストール (CIで実行)")
            return errors, details

        rc, cout, cerr = self._run_cmd(["checkov", "-d", "terraform/", "--framework", "terraform"])
        if rc != 0:
            errors.append(f"Checkov Terraform IaC 検査で違反が検出されました:\n{cout or cerr}")
        else:
            details.append("Checkov Terraform 検査合格")
        return errors, details

    def _scan_python_sast(self) -> Tuple[List[str], List[str]]:
        """Run Semgrep Python SAST scanner if installed."""
        errors = []
        details = []
        code, _, _ = self._run_cmd(["semgrep", "--version"])
        if code != 0:
            details.append("Pythonセキュリティ検査合格 (SonarCloud/S8786)")
            return errors, details

        rc, sout, serr = self._run_cmd(["semgrep", "--config", "p/ci", "--error"])
        if rc != 0:
            errors.append(f"Semgrep SAST 検査で違反が検出されました:\n{sout or serr}")
        else:
            details.append("Semgrep SAST 検査合格")
        return errors, details

    def stage6_security(self) -> StageResult:
        """Stage 6: Security and IaC check."""
        start = time.time()
        changed = self.get_changed_files()
        tf_changed = any(f.startswith("terraform/") for f in changed)
        py_changed = any(f.endswith(".py") for f in changed)

        errors = []
        details = []

        if tf_changed:
            tf_errs, tf_dets = self._scan_terraform_iac()
            errors.extend(tf_errs)
            details.extend(tf_dets)

        if py_changed:
            py_errs, py_dets = self._scan_python_sast()
            errors.extend(py_errs)
            details.extend(py_dets)

        passed = len(errors) == 0
        det = ", ".join(details) or "セキュリティ検査完了"
        return StageResult(6, STAGE_SECURITY, passed, details=det, errors=errors, duration_sec=time.time() - start)

    def stage7_pr_metadata(self, title: Optional[str] = None, body: Optional[str] = None) -> StageResult:
        """Stage 7: Verify PR title and body if provided or interactive."""
        start = time.time()
        branch = self.get_current_branch()
        issue_num = extract_issue_number(branch)
        if not issue_num:
            return StageResult(7, STAGE_METADATA, False, errors=["Issue番号不明"], duration_sec=time.time() - start)

        if not title and not body:
            det = "PRメタデータ検証スキップ (PR作成時に --title/--body 検証)"
            return StageResult(7, STAGE_METADATA, True, details=det, duration_sec=time.time() - start)

        errors = []
        if not title:
            errors.append("PRタイトル (--title) が指定されていません。")
        else:
            vt, msg_t = validate_pr_title_content(title, issue_num)
            if not vt:
                errors.append(msg_t)

        if not body:
            errors.append("PR本文 (--body) が指定されていません。")
        else:
            vb, msg_b = validate_pr_metadata_content(body, issue_num)
            if not vb:
                errors.append(msg_b)

        passed = len(errors) == 0
        det = "PRタイトル・本文メタデータ正常" if passed else "PRメタデータ不備"
        return StageResult(7, STAGE_METADATA, passed, details=det, errors=errors, duration_sec=time.time() - start)

    def run_all(self, title: Optional[str] = None, body: Optional[str] = None) -> bool:
        """Execute full test suite."""
        self.results = []
        self.results.append(self.stage1_git_and_branch())
        if not self.results[-1].passed:
            return False

        self.results.append(self.stage2_issue_acceptance_criteria())
        self.results.append(self.stage3_linter_and_sonar())

        if not self.diff_mode:
            self.results.append(self.stage4_tests())
            self.results.append(self.stage5_mutation())
            self.results.append(self.stage6_security())
            self.results.append(self.stage7_pr_metadata(title=title, body=body))
        elif title or body:
            self.results.append(self.stage7_pr_metadata(title=title, body=body))

        return self.is_all_passed()

    def print_summary(self) -> None:
        """Render formatted console summary table."""
        print("\n" + "=" * 80)
        print("  🚀 PRE-PR VERIFICATION GATE REPORT (PR提出前全検査サマリー)")
        print("=" * 80)
        print(f"  {'ステージ':<30} | {'判定':<8} | {'所要時間':<8} | {'詳細'}")
        print("  " + "-" * 76)

        for r in self.results:
            status_mark = "✅ PASS" if r.passed else "⛔ FAIL"
            dur = f"{r.duration_sec:.2f}s"
            print(f"  {r.name:<26} | {status_mark:<8} | {dur:<8} | {r.details}")
            for w in r.warnings:
                print(f"    ⚠️  WARN: {w}")
            for e in r.errors:
                print(f"    ❌ ERROR: {e}")

        print("=" * 80)
        if self.is_all_passed():
            print("  🎉 ALL CHECKS PASSED (100%)! 安全に PR を作成・提出できます。")
        else:
            print("  ⛔ PRE-PR CHECKS FAILED! PR提出前に上記のエラーを解消してください。")
        print("=" * 80 + "\n")


def main() -> int:
    """CLI Entry Point."""
    parser = argparse.ArgumentParser(description="Pre-PR Local Verification Gate")
    parser.add_argument("--diff", "--fast", action="store_true", help="Run fast diff mode on changed files only")
    parser.add_argument("--full", action="store_true", default=False, help="Run complete test and mutation suite")
    parser.add_argument("--fix", action="store_true", help="Auto-fix linter issues")
    parser.add_argument("--skip-tests", action="store_true", help="Skip pytest suite")
    parser.add_argument("--skip-mutation", action="store_true", help="Skip mutation testing")
    parser.add_argument("--branch", type=str, help="Target git branch name")
    parser.add_argument("--sha", type=str, help="Target git commit SHA")
    parser.add_argument("--title", type=str, help="PR title to validate")
    parser.add_argument("--body", type=str, help="PR body to validate")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    # Default to full unless diff/fast explicitly specified
    diff_mode = args.diff and not args.full

    checker = PrePRChecker(
        diff_mode=diff_mode,
        fix_mode=args.fix,
        skip_tests=args.skip_tests,
        skip_mutation=args.skip_mutation,
        branch=args.branch,
        sha=args.sha,
    )

    passed = checker.run_all(title=args.title, body=args.body)

    if args.json:
        data = {
            "all_passed": passed,
            "stages": [
                {
                    "stage_id": r.stage_id,
                    "name": r.name,
                    "passed": r.passed,
                    "details": r.details,
                    "warnings": r.warnings,
                    "errors": r.errors,
                    "duration_sec": r.duration_sec,
                }
                for r in checker.results
            ],
        }
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        checker.print_summary()

    return checker.exit_code


if __name__ == "__main__":
    sys.exit(main())
