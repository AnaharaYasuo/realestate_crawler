#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SonarCloud Local Guardrail: S3776 (Cognitive Complexity) & S8786 (Regex Backtracking/ReDoS)
Pre-commit / Pre-push static analysis engine.
"""

import ast
import argparse
import os
import re
import subprocess
import sys
from typing import List, Dict, Tuple, Any, Optional

DEFAULT_MAX_COMPLEXITY = 15

# Directories and paths excluded from Sonar scan (consistent with sonar-project.properties)
EXCLUDED_PATTERNS = [
    r"tests[/\\].*",
    r"migrations[/\\].*",
    r"Temp[/\\].*",
    r"logs[/\\].*",
    r"catboost_info[/\\].*",
    r"\.pytest_cache[/\\].*",
    r"docs[/\\].*",
    r"\.git[/\\].*",
]


class CognitiveComplexityVisitor(ast.NodeVisitor):
    """Calculates Sonar-compliant Cognitive Complexity for a function or method node."""

    def __init__(self):
        self.complexity = 0
        self.nesting_level = 0
        self.increments: List[Tuple[int, str, int]] = []

    def _add_increment(self, node: ast.AST, desc: str, nesting_cost: bool = True):
        points = 1 + (self.nesting_level if nesting_cost else 0)
        self.complexity += points
        lineno = getattr(node, "lineno", 0)
        self.increments.append((lineno, desc, points))

    def _visit_block(self, body: List[ast.stmt]):
        self.nesting_level += 1
        for stmt in body:
            self.visit(stmt)
        self.nesting_level -= 1

    def visit_If(self, node: ast.If):
        self._add_increment(node, "if statement", nesting_cost=True)
        self.visit(node.test)
        self._visit_block(node.body)

        # Process elif / else chains
        orelse = node.orelse
        while orelse and len(orelse) == 1 and isinstance(orelse[0], ast.If):
            elif_node = orelse[0]
            self._add_increment(elif_node, "elif statement", nesting_cost=False)
            self.visit(elif_node.test)
            self._visit_block(elif_node.body)
            orelse = elif_node.orelse

        if orelse:
            self._visit_block(orelse)

    def visit_For(self, node: ast.For):
        self._add_increment(node, "for loop", nesting_cost=True)
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_AsyncFor(self, node: ast.AsyncFor):
        self._add_increment(node, "async for loop", nesting_cost=True)
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_While(self, node: ast.While):
        self._add_increment(node, "while loop", nesting_cost=True)
        self.visit(node.test)
        self._visit_block(node.body)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        self._add_increment(node, "except handler", nesting_cost=True)
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_BoolOp(self, node: ast.BoolOp):
        op_count = len(node.values) - 1
        for _ in range(op_count):
            self._add_increment(node, f"{node.op.__class__.__name__.lower()} operator", nesting_cost=False)
        self.generic_visit(node)


def calculate_cognitive_complexity(func_node: ast.AST) -> Tuple[int, List[Tuple[int, str, int]]]:
    """Calculate cognitive complexity for a FunctionDef or AsyncFunctionDef node."""
    visitor = CognitiveComplexityVisitor()
    for stmt in getattr(func_node, "body", []):
        visitor.visit(stmt)
    return visitor.complexity, visitor.increments


# Regex patterns that indicate high ReDoS or super-linear backtracking risks (S8786)
RISKY_REGEX_PATTERNS = [
    (r"\([^)]*[\+\*]\)[\+\*]", "Nested quantifier e.g. (a+)+ or (x*)* causing exponential backtracking"),
    (r"\.\*[\?\s]*\(.*?\+.*?\)", "Greedy dot matching with sub-pattern repetition causing polynomial backtracking"),
    (r"\.\*.*?\.\*", "Multiple unanchored greedy dot wildcards causing catastrophic backtracking"),
    (r"\.\+.*?\.\+", "Multiple unanchored plus wildcards causing catastrophic backtracking"),
    (r"\.\*\?.*?\(\\\w\+\)", "Lazy dot with ambiguous token group causing super-linear runtime"),
]


def _extract_regex_pattern_from_call(node: ast.Call) -> Optional[str]:
    """Extract string pattern literal from a re.* call."""
    func = node.func
    func_name = getattr(func, "attr", None) or getattr(func, "id", None)
    if func_name not in ("compile", "search", "match", "findall", "finditer", "sub", "subn"):
        return None
    if not node.args:
        return None
    first_arg = node.args[0]
    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
        return first_arg.value
    return None


def _check_pattern_risk(regex_str: str) -> Optional[str]:
    """Check if regex string triggers any ReDoS risk rule."""
    for pattern, reason in RISKY_REGEX_PATTERNS:
        if re.search(pattern, regex_str):
            return reason
    return None


def detect_regex_redos_risks(source_code: str, filename: str = "") -> List[Dict[str, Any]]:
    """Scan source code AST for regex calls and check for backtracking/ReDoS patterns (S8786)."""
    issues = []
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return issues

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        regex_str = _extract_regex_pattern_from_call(node)
        if not regex_str:
            continue
        reason = _check_pattern_risk(regex_str)
        if not reason:
            continue

        issues.append({
            "file": filename,
            "line": getattr(node, "lineno", 0),
            "rule": "python:S8786",
            "severity": "MAJOR",
            "message": f"Simplify regular expression to prevent ReDoS / backtracking ({reason}): {regex_str!r}",
        })

    return issues


def scan_source_code(source_code: str, filename: str = "", max_complexity: int = DEFAULT_MAX_COMPLEXITY) -> List[Dict[str, Any]]:
    """Analyze Python source code for S3776 and S8786 violations."""
    issues = []
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        return [{
            "file": filename,
            "line": e.lineno or 1,
            "rule": "python:SyntaxError",
            "severity": "BLOCKER",
            "message": f"Syntax error: {e.msg}",
        }]

    # 1. Scan for Cognitive Complexity (S3776)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            score, details = calculate_cognitive_complexity(node)
            if score > max_complexity:
                issues.append({
                    "file": filename,
                    "line": getattr(node, "lineno", 0),
                    "rule": "python:S3776",
                    "severity": "CRITICAL",
                    "function": node.name,
                    "score": score,
                    "max_allowed": max_complexity,
                    "message": f"Refactor function '{node.name}' to reduce Cognitive Complexity from {score} to {max_complexity}.",
                    "details": details,
                })

    # 2. Scan for Regex Backtracking (S8786)
    issues.extend(detect_regex_redos_risks(source_code, filename=filename))
    return issues


def is_excluded_file(filepath: str) -> bool:
    """Check if filepath should be excluded according to SonarCloud exclusion rules."""
    norm_path = filepath.replace("\\", "/")
    for pattern in EXCLUDED_PATTERNS:
        if re.search(pattern, norm_path):
            return True
    return False


def scan_file(filepath: str, max_complexity: int = DEFAULT_MAX_COMPLEXITY) -> List[Dict[str, Any]]:
    """Scan a single Python file for Sonar issues."""
    if not os.path.exists(filepath) or is_excluded_file(filepath) or not filepath.endswith(".py"):
        return []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return [{
            "file": filepath,
            "line": 1,
            "rule": "python:FileReadError",
            "severity": "BLOCKER",
            "message": f"Failed to read file: {e}",
        }]

    return scan_source_code(content, filename=filepath, max_complexity=max_complexity)


def _run_git_cmd(args: List[str]) -> List[str]:
    """Execute git command and return list of output lines."""
    try:
        res = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        return res.stdout.splitlines() if res.returncode == 0 else []
    except Exception:
        return []


def get_git_diff_files() -> List[str]:
    """Get modified/added Python files comparing HEAD against origin/master and uncommitted changes."""
    files = set()
    # 1. Diff against origin/master if on branch
    for line in _run_git_cmd(["git", "diff", "--name-only", "origin/master...HEAD"]):
        if line.strip().endswith(".py"):
            files.add(line.strip())

    # 2. Working tree diff against HEAD
    for line in _run_git_cmd(["git", "diff", "--name-only", "HEAD"]):
        if line.strip().endswith(".py"):
            files.add(line.strip())

    # 3. Untracked files (newly created)
    for line in _run_git_cmd(["git", "status", "--porcelain"]):
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2 and parts[0] in ("??", "A") and parts[1].strip().endswith(".py"):
            files.add(parts[1].strip())

    return sorted(list(files))


def _determine_files_to_scan(args: argparse.Namespace) -> List[str]:
    """Resolve target files based on CLI arguments."""
    if args.file:
        return [args.file]
    if args.all:
        matched = []
        for root, _, filenames in os.walk("src"):
            for fname in filenames:
                if fname.endswith(".py"):
                    matched.append(os.path.join(root, fname))
        return matched
    return get_git_diff_files()


def _print_sonar_report(all_issues: List[Dict[str, Any]], scanned_count: int, max_complexity: int) -> int:
    """Print scan results summary and return exit code."""
    print(f"Scanned {scanned_count} file(s).")
    if not all_issues:
        print(" SUCCESS: All files passed SonarCloud local guardrail checks!")
        print("=" * 80)
        return 0

    print(f"\n FAILED: Found {len(all_issues)} issue(s) that would fail SonarCloud Quality Gate:\n")
    for issue in all_issues:
        print(f"  [{issue['severity']}] {issue['rule']}: {issue['file']}:{issue['line']}")
        print(f"    Message: {issue['message']}")
        if "function" in issue:
            print(f"    Target: def {issue['function']}()")
        print()

    print("=" * 80)
    print(" Hint: Refer to 'docs/implementation/sonar_guardrail_guide.md' for refactoring patterns.")
    print("=" * 80)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="SonarCloud Local Guardrail: S3776 & S8786 Fast Static Scanner")
    parser.add_argument("--diff", action="store_true", help="Scan only git changed files against origin/master")
    parser.add_argument("--all", action="store_true", help="Scan all python files under src/")
    parser.add_argument("--file", type=str, help="Scan a specific python file")
    parser.add_argument("--max-complexity", type=int, default=DEFAULT_MAX_COMPLEXITY, help="Max allowed cognitive complexity (default: 15)")
    args = parser.parse_args()

    files_to_scan = _determine_files_to_scan(args)
    if not files_to_scan:
        print(" No modified Python files found in git diff. Scan skipped.")
        return 0

    print("=" * 80)
    print(f" SonarCloud Local Guardrail (S3776 <= {args.max_complexity}, S8786 ReDoS Defense)")
    print("=" * 80)

    all_issues = []
    scanned_count = 0
    for fpath in files_to_scan:
        if is_excluded_file(fpath):
            continue
        scanned_count += 1
        issues = scan_file(fpath, max_complexity=args.max_complexity)
        if issues:
            all_issues.extend(issues)

    return _print_sonar_report(all_issues, scanned_count, args.max_complexity)


if __name__ == "__main__":
    sys.exit(main())
