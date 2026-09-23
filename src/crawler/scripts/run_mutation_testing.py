# -*- coding: utf-8 -*-
"""
Mutation Testing Runner (run_mutation_testing.py)
Level 1: データ故意破損注入テスト (Data Mutation)
Level 2: コードAST変異テスト (Code Mutation)
統合実行およびキル率 (Mutation Score) レポート出力スクリプト
"""
import argparse
import json
import logging
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

_crawler_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)

import setup_env  # noqa: E402
setup_env.init_environment()

from package.testing.mutation_engine import (  # noqa: E402
    ASTMutationEngine,
    MutationResult,
)

logger = logging.getLogger("mutation_testing")

DEFAULT_DETECTOR_FILE = "property_type_detector.py"
DEFAULT_DETECTOR_TEST_FILE = f"test_{DEFAULT_DETECTOR_FILE}"


def run_level1_data_mutation(crawler_root: str) -> Dict[str, Any]:
    """Level 1: 全モデル・フィールド分類網羅とデータ破損注入テストの実行"""
    logger.info("=== [Level 1: Data Mutation Testing] Starting ===")
    test_file = os.path.join(crawler_root, "tests", "unit", "test_parser_field_validation.py")

    cmd = [sys.executable, "-m", "pytest", test_file, "-q"]
    res = subprocess.run(cmd, cwd=crawler_root, capture_output=True, text=True)

    passed = (res.returncode == 0)
    logger.info("Level 1 Test Exit Code: %d, Passed: %s", res.returncode, passed)
    if not passed:
        logger.error("Level 1 Test stdout:\n%s", res.stdout)
        logger.error("Level 1 Test stderr:\n%s", res.stderr)

    return {
        "level": 1,
        "name": "Data Mutation & Field Classification",
        "test_target": test_file,
        "status": "PASS" if passed else "FAIL",
        "detection_rate": 100.0 if passed else 0.0,
        "is_passed": passed,
    }


def _resolve_paths(crawler_root: str, target_file: Optional[str], test_file: Optional[str]) -> tuple[str, str]:
    if not target_file:
        target_file = os.path.join(crawler_root, "package", "utils", DEFAULT_DETECTOR_FILE)
    if not test_file:
        test_file = os.path.join(crawler_root, "tests", "unit", DEFAULT_DETECTOR_TEST_FILE)

    def _to_abs(path: str) -> str:
        if os.path.isabs(path):
            return path
        candidate = os.path.join(crawler_root, path)
        return candidate if os.path.exists(candidate) else os.path.abspath(path)

    return _to_abs(target_file), _to_abs(test_file)


def _evaluate_single_mutant(
    engine: ASTMutationEngine,
    mutant: Any,
    test_cmd: str,
    crawler_root: str,
    idx: int,
    total: int,
) -> tuple[bool, Optional[Dict[str, Any]]]:
    try:
        is_killed = engine.run_mutation_test(
            mutant=mutant,
            test_command=test_cmd,
            cwd=crawler_root,
            timeout=25,
        )
        if is_killed:
            logger.info("[%d/%d] KILLED: Line %d (%s)", idx, total, mutant.line_number, mutant.ast_node_str)
            return True, None
        logger.warning("[%d/%d] SURVIVED: Line %d (%s) -> %s", idx, total, mutant.line_number, mutant.original_source, mutant.mutated_source)
        return False, {
            "line": mutant.line_number,
            "type": mutant.mutation_type.value,
            "original": mutant.original_source,
            "mutated": mutant.mutated_source,
            "ast_change": mutant.ast_node_str,
        }
    except Exception:
        logger.exception("[%d/%d] ERROR running mutant at line %d", idx, total, mutant.line_number)
        return False, None


def run_level2_code_mutation(
    crawler_root: str,
    target_file: Optional[str] = None,
    test_file: Optional[str] = None,
    max_mutants: int = 15,
) -> MutationResult:
    """Level 2: コアユニットのASTコード変異テストの実行"""
    logger.info("=== [Level 2: Code Mutation Testing] Starting ===")
    target_abs, test_abs = _resolve_paths(crawler_root, target_file, test_file)

    engine = ASTMutationEngine()
    limit = max_mutants if max_mutants > 0 else None
    mutants = engine.generate_mutants_from_file(target_abs, max_mutants=limit)
    total_mutants = len(mutants)
    logger.info("Generated %d mutants for target: %s", total_mutants, target_abs)

    killed = 0
    survived = 0
    errored = 0
    survived_details: List[Dict[str, Any]] = []
    test_cmd = f'"{sys.executable}" -m pytest "{test_abs}" -q'

    for idx, mutant in enumerate(mutants, 1):
        is_killed, detail = _evaluate_single_mutant(engine, mutant, test_cmd, crawler_root, idx, total_mutants)
        if is_killed:
            killed += 1
        elif detail:
            survived += 1
            survived_details.append(detail)
        else:
            errored += 1

    return MutationResult(
        target=os.path.basename(target_abs),
        total_mutants=total_mutants,
        killed_mutants=killed,
        survived_mutants=survived,
        errored_mutants=errored,
        survived_details=survived_details,
    )


def _get_git_changed_files(crawler_root: str) -> List[str]:
    diff_cmds = [
        ["git", "diff", "--ignore-space-at-eol", "origin/master...HEAD", "--name-only"],
        ["git", "diff", "--ignore-space-at-eol", "master...HEAD", "--name-only"],
        ["git", "diff", "--ignore-space-at-eol", "--cached", "--name-only"],
        ["git", "diff", "--ignore-space-at-eol", "--name-only"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    all_files = set()
    for cmd in diff_cmds:
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=crawler_root)
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.strip().splitlines():
                    f = line.strip().split()[-1]
                    if f.endswith(".py"):
                        all_files.add(f)
        except Exception:
            continue
    return sorted(all_files)


def _resolve_unit_abs_path(crawler_root: str, path: str) -> str:
    if os.path.isabs(path):
        return path
    cand1 = os.path.join(crawler_root, path)
    if os.path.exists(cand1):
        return os.path.abspath(cand1)
    if path.startswith("src/crawler/"):
        cand2 = os.path.join(crawler_root, path.replace("src/crawler/", "", 1))
        if os.path.exists(cand2):
            return os.path.abspath(cand2)
    return os.path.abspath(cand1)


def _find_matched_source(crawler_root: str, test_base: str, source_files: List[str]) -> Optional[str]:
    for sf in source_files:
        if os.path.basename(sf) == test_base:
            return _resolve_unit_abs_path(crawler_root, sf)

    if "detector" in test_base:
        return os.path.join(crawler_root, "package", "utils", DEFAULT_DETECTOR_FILE)
    if "router" in test_base:
        return os.path.join(crawler_root, "package", "utils", "url_router.py")

    for root, _, files in os.walk(os.path.join(crawler_root, "package")):
        if test_base in files:
            return os.path.join(root, test_base)
    return None


def find_pr_changed_units(crawler_root: str) -> List[Dict[str, str]]:
    """PRで追加・変更されたファイルから、変異対象ファイルと対応するテストファイルのペアを自動検出"""
    changed_files = _get_git_changed_files(crawler_root)
    exclude_tests = {"test_parser_field_validation.py", "test_mutation_engine.py"}
    exclude_targets = {"mutation_engine.py"}

    pairs: List[Dict[str, str]] = []
    test_files = [f for f in changed_files if "tests/unit/test_" in f and os.path.basename(f) not in exclude_tests]
    source_files = [f for f in changed_files if "package/" in f and "tests/" not in f and os.path.basename(f) not in exclude_targets]

    for tf in test_files:
        test_abs = _resolve_unit_abs_path(crawler_root, tf)
        test_base = os.path.basename(tf).replace("test_", "")
        matched_src = _find_matched_source(crawler_root, test_base, source_files)
        if matched_src and os.path.exists(matched_src):
            pairs.append({"target": os.path.abspath(matched_src), "test": test_abs})

    for sf in source_files:
        src_abs = _resolve_unit_abs_path(crawler_root, sf)
        src_base = os.path.basename(sf)
        expected_test = f"test_{src_base}"
        test_path = os.path.join(crawler_root, "tests", "unit", expected_test)
        if os.path.exists(test_path) and not any(p.get("target") == src_abs for p in pairs):
            pairs.append({"target": src_abs, "test": os.path.abspath(test_path)})

    return pairs


def _run_pr_code_mutations(
    crawler_root: str,
    args: argparse.Namespace,
    report_data: Dict[str, Any],
) -> bool:
    pr_pairs = find_pr_changed_units(crawler_root)
    logger.info("PR Mode detected %d unit test / target pairs: %s", len(pr_pairs), pr_pairs)
    report_data["results"]["level2_code_mutation_pr"] = []
    # docs/config のみの PR 等、変異対象のソースが無い場合はデフォルト detector へ
    # フォールバックしない（無関係ファイル破壊・ノイズを防止）。スキップ=合格。
    if not pr_pairs:
        logger.info(
            "PR Mode: no mutable source/test pairs in changed files; "
            "skipping Level 2 code mutation"
        )
        report_data["results"]["level2_code_mutation_pr"].append({
            "target": "(none)",
            "test": "(skipped-no-pairs)",
            "total_mutants": 0,
            "killed_mutants": 0,
            "survived_mutants": 0,
            "errored_mutants": 0,
            "mutation_score": 100.0,
            "threshold": args.threshold,
            "is_passed": True,
            "survived_details": [],
        })
        return True

    pr_passed = True
    for pair in pr_pairs:
        code_res = run_level2_code_mutation(
            crawler_root=crawler_root,
            target_file=pair["target"],
            test_file=pair["test"],
            max_mutants=args.max_mutants,
        )
        passed = code_res.is_passed(args.threshold)
        report_data["results"]["level2_code_mutation_pr"].append({
            "target": code_res.target,
            "test": os.path.basename(pair["test"]),
            "total_mutants": code_res.total_mutants,
            "killed_mutants": code_res.killed_mutants,
            "survived_mutants": code_res.survived_mutants,
            "errored_mutants": code_res.errored_mutants,
            "mutation_score": code_res.mutation_score,
            "threshold": args.threshold,
            "is_passed": passed,
            "survived_details": code_res.survived_details,
        })
        if not passed:
            pr_passed = False
    return pr_passed


def _print_mutation_summary(report_data: Dict[str, Any], all_passed: bool):
    print("\n=======================================================")
    print("           MUTATION TESTING SUMMARY REPORT             ")
    print("=======================================================")
    if "level1_data_mutation" in report_data["results"]:
        d_res = report_data["results"]["level1_data_mutation"]
        print(f"Level 1 (Data Mutation): {d_res['status']} | Detection Rate: {d_res['detection_rate']}%")

    if "level2_code_mutation" in report_data["results"]:
        c_res = report_data["results"]["level2_code_mutation"]
        c_status = "PASS" if c_res["is_passed"] else "FAIL"
        print(f"Level 2 (Code Mutation): {c_status} | Target: {c_res['target']}")
        print(f"  - Total Evaluated: {c_res['total_mutants']}")
        print(f"  - Killed: {c_res['killed_mutants']} | Survived: {c_res['survived_mutants']}")
        print(f"  - Mutation Score: {c_res['mutation_score']}% (Threshold: {c_res['threshold']}%)")

    if "level2_code_mutation_pr" in report_data["results"]:
        for c_res in report_data["results"]["level2_code_mutation_pr"]:
            c_status = "PASS" if c_res["is_passed"] else "FAIL"
            print(f"Level 2 (Code Mutation - PR): {c_status} | Target: {c_res['target']} (Test: {c_res['test']})")
            print(f"  - Total Evaluated: {c_res['total_mutants']}")
            print(f"  - Killed: {c_res['killed_mutants']} | Survived: {c_res['survived_mutants']}")
            print(f"  - Mutation Score: {c_res['mutation_score']}% (Threshold: {c_res['threshold']}%)")

    print("-------------------------------------------------------")
    print(f"OVERALL STATUS: {'PASS' if all_passed else 'FAIL'}")
    print("=======================================================\n")


def _save_mutation_report(crawler_root: str, report_arg: Optional[str], report_data: Dict[str, Any]):
    report_filename = os.path.basename(report_arg) if report_arg else "mutation_report.json"
    if not report_filename.endswith(".json"):
        report_filename = f"{report_filename}.json"

    logs_dir = os.path.join(crawler_root, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    report_path = os.path.join(logs_dir, report_filename)

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    print(f"Report saved to: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Run Mutation Testing Framework")
    parser.add_argument("--mode", choices=["all", "data", "code"], default="all", help="Test mode (all, data, code)")
    parser.add_argument("--pr-mode", action="store_true", help="PR mode: automatically detect and test modified unit tests and source files")
    parser.add_argument("--threshold", type=float, default=85.0, help="Code mutation kill rate threshold percentage (default: 85.0)")
    parser.add_argument("--target", type=str, default=None, help="Target file path for code mutation")
    parser.add_argument("--test", type=str, default=None, help="Unit test file path for code mutation")
    parser.add_argument("--max-mutants", type=int, default=15, help="Maximum number of code mutants to evaluate (default: 15)")
    parser.add_argument("--report", type=str, default=None, help="Output path for JSON report")

    args = parser.parse_args()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    crawler_root = os.path.dirname(script_dir)

    report_data: Dict[str, Any] = {
        "mode": "pr-mode" if args.pr_mode else args.mode,
        "results": {},
        "summary": {},
    }
    all_passed = True

    if args.pr_mode or args.mode in ["all", "data"]:
        data_result = run_level1_data_mutation(crawler_root)
        report_data["results"]["level1_data_mutation"] = data_result
        if not data_result["is_passed"]:
            all_passed = False

    if args.pr_mode:
        if not _run_pr_code_mutations(crawler_root, args, report_data):
            all_passed = False
    elif args.mode in ["all", "code"]:
        code_result = run_level2_code_mutation(
            crawler_root=crawler_root,
            target_file=args.target,
            test_file=args.test,
            max_mutants=args.max_mutants,
        )
        passed = code_result.is_passed(args.threshold)
        report_data["results"]["level2_code_mutation"] = {
            "target": code_result.target,
            "total_mutants": code_result.total_mutants,
            "killed_mutants": code_result.killed_mutants,
            "survived_mutants": code_result.survived_mutants,
            "errored_mutants": code_result.errored_mutants,
            "mutation_score": code_result.mutation_score,
            "threshold": args.threshold,
            "is_passed": passed,
            "survived_details": code_result.survived_details,
        }
        if not passed:
            all_passed = False

    report_data["summary"]["overall_passed"] = all_passed
    _print_mutation_summary(report_data, all_passed)
    _save_mutation_report(crawler_root, args.report, report_data)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
