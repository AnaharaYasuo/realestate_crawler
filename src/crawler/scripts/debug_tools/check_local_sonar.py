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
from typing import List, Dict, Tuple, Any, Optional, Set

DEFAULT_MAX_COMPLEXITY = 15
MAX_REGEX_LENGTH = 500

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

RE_FUNCS = {"compile", "search", "match", "fullmatch", "split", "findall", "finditer", "sub", "subn"}


class CognitiveComplexityVisitor(ast.NodeVisitor):
    """Calculates Sonar-compliant Cognitive Complexity for a function or method node."""

    def __init__(self):
        """Initialize complexity score and nesting tracking state."""
        self.complexity = 0
        self.nesting_level = 0
        self.increments: List[Tuple[int, str, int]] = []

    def _add_increment(self, node: ast.AST, desc: str, nesting_cost: bool = True):
        """Add complexity increment with optional nesting penalty."""
        points = 1 + (self.nesting_level if nesting_cost else 0)
        self.complexity += points
        lineno = getattr(node, "lineno", 0)
        self.increments.append((lineno, desc, points))

    def _visit_block(self, body: List[ast.stmt]):
        """Visit a nested block of statements with incremented nesting level."""
        self.nesting_level += 1
        for stmt in body:
            self.visit(stmt)
        self.nesting_level -= 1

    def visit_If(self, node: ast.If):
        """Score if statement, test expression, and elif/else branches."""
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
        """Score for loop and traverse its body."""
        self._add_increment(node, "for loop", nesting_cost=True)
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_AsyncFor(self, node: ast.AsyncFor):
        """Score async for loop and traverse its body."""
        self._add_increment(node, "async for loop", nesting_cost=True)
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_While(self, node: ast.While):
        """Score while loop, test condition, body, and orelse block."""
        self._add_increment(node, "while loop", nesting_cost=True)
        self.visit(node.test)
        self._visit_block(node.body)
        if node.orelse:
            self._visit_block(node.orelse)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        """Score exception handler and traverse its body."""
        self._add_increment(node, "except handler", nesting_cost=True)
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_BoolOp(self, node: ast.BoolOp):
        """Score each boolean operator (and / or) in a compound expression."""
        op_count = len(node.values) - 1
        for _ in range(op_count):
            self._add_increment(node, f"{node.op.__class__.__name__.lower()} operator", nesting_cost=False)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Stop traversing into nested function definitions so each function is scored independently."""
        pass

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Stop traversing into nested async function definitions so each function is scored independently."""
        pass


def calculate_cognitive_complexity(func_node: ast.AST) -> Tuple[int, List[Tuple[int, str, int]]]:
    """Calculate cognitive complexity for a FunctionDef or AsyncFunctionDef node."""
    visitor = CognitiveComplexityVisitor()
    for stmt in getattr(func_node, "body", []):
        visitor.visit(stmt)
    return visitor.complexity, visitor.increments


def _extract_regex_pattern_from_call(node: ast.Call) -> Optional[str]:
    """Extract string pattern literal from a re.* call or imported regex function call."""
    func = node.func
    func_name = getattr(func, "attr", None) or getattr(func, "id", None)
    if func_name not in RE_FUNCS:
        return None

    # Verify if it's an attribute access like re.search or direct call like search
    if isinstance(func, ast.Attribute):
        value = func.value
        # Check module name
        mod_name = getattr(value, "id", None)
        if mod_name not in ("re", "regex"):
            return None

    # Check keyword arguments (pattern="...")
    for kw in node.keywords:
        if kw.arg == "pattern" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value

    # Check first positional argument
    if node.args:
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            return first_arg.value

    return None


def _check_pattern_risk(regex_str: str) -> Optional[str]:
    """Check if regex string triggers any ReDoS risk rule with input length guards."""
    if len(regex_str) > MAX_REGEX_LENGTH:
        return f"Pattern length ({len(regex_str)}) exceeds maximum safe length ({MAX_REGEX_LENGTH})"

    # 1. Nested quantifier e.g. (a+)+ or (x*)*
    if re.search(r"\([^()]{1,50}[+*]\)[+*]", regex_str):
        return "Nested quantifier e.g. (a+)+ or (x*)* causing exponential backtracking"

    # 2. Multiple unanchored greedy dot or plus wildcards (including mixed .* and .+)
    if regex_str.count(".*") + regex_str.count(".+") >= 2:
        return "Multiple unanchored greedy wildcards causing catastrophic backtracking"

    # 3. Greedy dot with repetition sub-pattern
    if ".*" in regex_str and re.search(r"\([^()]{1,50}\+[^()]{0,50}\)", regex_str):
        return "Greedy dot matching with sub-pattern repetition causing polynomial backtracking"

    # 4. Lazy dot with ambiguous token group
    if ".*?" in regex_str and (r"(\d+)" in regex_str or r"(\w+)" in regex_str):
        return "Lazy dot with ambiguous token group causing super-linear runtime"

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

    # 3. Scan for Code Smells: S1192 (duplicated literals) & S7508 (redundant calls)
    issues.extend(detect_sonar_code_smells(tree, filename=filename))
    return issues


def _collect_docstring_nodes(tree: ast.AST) -> Set[int]:
    """Collect line numbers of docstrings in AST to exclude from duplicate literal checks."""
    doc_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                doc_lines.add(getattr(node.body[0].value, "lineno", 0))
    return doc_lines


def _check_s7508_redundant_calls(tree: ast.AST, filename: str) -> List[Dict[str, Any]]:
    """Scan for S7508: sorted(list(...)) or sorted(set(...))."""
    issues = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "sorted"
            and node.args
            and isinstance(node.args[0], ast.Call)
            and isinstance(node.args[0].func, ast.Name)
            and node.args[0].func.id in ("list", "set")
        ):
            issues.append({
                "file": filename,
                "line": getattr(node, "lineno", 1),
                "rule": "python:S7508",
                "severity": "MINOR",
                "message": f"Remove redundant call '{node.args[0].func.id}()' before sorted().",
            })
    return issues


def _extract_chained_string_methods(node: ast.BoolOp) -> List[str]:
    """Extract string method names from chained Or boolean expression."""
    if not isinstance(node.op, ast.Or):
        return []
    funcs = []
    for v in node.values:
        if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.func.attr in ("startswith", "endswith"):
            funcs.append(v.func.attr)
    return funcs


def _check_s8513_chained_startswith(tree: ast.AST, filename: str) -> List[Dict[str, Any]]:
    """Scan for S8513: chained startswith or endswith with or operator."""
    issues = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.BoolOp):
            continue
        funcs = _extract_chained_string_methods(node)
        if len(funcs) >= 2 and len(set(funcs)) == 1:
            issues.append({
                "file": filename,
                "line": getattr(node, "lineno", 1),
                "rule": "python:S8513",
                "severity": "MAJOR",
                "message": f"Replace chained '{funcs[0]}' calls with a single call using a tuple argument.",
            })
    return issues


def _is_s1192_candidate(val: str) -> bool:
    """Check if string literal qualifies as S1192 duplication candidate."""
    if len(val) < 12 or val.startswith(("-", "__")):
        return False
    # Only flag multi-word sentences, Japanese phrases, or longer descriptive literals
    return " " in val or "\n" in val or any(ord(ch) > 0x3000 for ch in val)


def _check_s1192_duplicated_literals(tree: ast.AST, filename: str, doc_lines: Set[int]) -> List[Dict[str, Any]]:
    """Scan for S1192: duplicated human-readable string literals >= 3 times."""
    if is_excluded_file(filename):
        return []

    str_counts: Dict[str, List[int]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            lineno = getattr(node, "lineno", 0)
            if lineno in doc_lines:
                continue
            val = node.value.strip()
            if _is_s1192_candidate(val):
                str_counts.setdefault(val, []).append(lineno)

    issues = []
    for val, lines in str_counts.items():
        if len(lines) >= 3:
            issues.append({
                "file": filename,
                "line": lines[0],
                "rule": "python:S1192",
                "severity": "CRITICAL",
                "message": f"Define a constant instead of duplicating this literal '{val[:30]}' {len(lines)} times (lines: {lines[:4]}).",
            })
    return issues


def detect_sonar_code_smells(tree: ast.AST, filename: str = "") -> List[Dict[str, Any]]:
    """Detect SonarCloud S1192 (duplicated literals), S7508 (redundant calls), S8513 (chained startswith)."""
    doc_lines = _collect_docstring_nodes(tree)
    issues = _check_s7508_redundant_calls(tree, filename)
    issues.extend(_check_s8513_chained_startswith(tree, filename))
    issues.extend(_check_s1192_duplicated_literals(tree, filename, doc_lines))
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
    if not filepath or "\0" in filepath:
        return []

    try:
        import tempfile
        base_dir = os.path.realpath(os.getcwd())
        tmp_dir = os.path.realpath(tempfile.gettempdir())
        canonical = os.path.realpath(os.path.abspath(filepath))

        is_under_base = canonical.startswith(base_dir + os.sep) or canonical == base_dir
        is_under_tmp = canonical.startswith(tmp_dir + os.sep) or canonical == tmp_dir
        if not (is_under_base or is_under_tmp):
            return []
        if not os.path.isfile(canonical) or is_excluded_file(canonical) or not canonical.endswith(".py"):
            return []

        with open(canonical, "r", encoding="utf-8") as f:
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


def _run_git_cmd(args: List[str]) -> Tuple[bool, List[str], str]:
    """Execute git command and return (success, stdout_lines, stderr)."""
    try:
        res = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        return (res.returncode == 0, res.stdout.splitlines() if res.returncode == 0 else [], res.stderr.strip())
    except Exception as e:
        return (False, [], str(e))


def _get_py_files_from_cmd(args: List[str]) -> Set[str]:
    """Execute git command and return matching python files."""
    success, lines, _ = _run_git_cmd(args)
    if not success:
        return set()
    return {line.strip() for line in lines if line.strip().endswith(".py")}


def _get_branch_diff_files() -> Set[str]:
    """Get modified python files against origin/master or master."""
    files = _get_py_files_from_cmd(["git", "diff", "--name-only", "--ignore-space-at-eol", "origin/master...HEAD"])
    if not files:
        files = _get_py_files_from_cmd(["git", "diff", "--name-only", "--ignore-space-at-eol", "master...HEAD"])
    return files


def get_git_diff_files() -> List[str]:
    """Get modified/added Python files by combining branch diff, staged, and working tree changes."""
    files = _get_branch_diff_files()
    files.update(_get_py_files_from_cmd(["git", "diff", "--name-only", "--cached", "--ignore-space-at-eol"]))

    # Fallback: Only include working tree changes if neither branch diff nor staged diff found anything
    if not files:
        files.update(_get_py_files_from_cmd(["git", "diff", "--name-only", "--ignore-space-at-eol"]))

    return sorted(files)


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


def _print_sonar_report(all_issues: List[Dict[str, Any]], scanned_count: int) -> int:
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
    """Entry point for SonarCloud Local Guardrail CLI scanner."""
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

    return _print_sonar_report(all_issues, scanned_count)


if __name__ == "__main__":
    sys.exit(main())
