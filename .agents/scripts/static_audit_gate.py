#!/usr/bin/env python3
"""Local static audit gate for Sonar/Semgrep shift-left (Chapter 7.2-7.5)."""
import ast
import sys
from pathlib import Path


def audit_python_source(source: str, filename: str = "<unknown>") -> list[str]:
    """Detect swallowed exceptions (bare pass in except) before PR."""
    findings: list[str] = []
    tree = ast.parse(source, filename=filename)
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                findings.append(f"{filename}:{node.lineno}: swallowed_exception")
    return findings


def main() -> None:
    targets = [Path(p) for p in sys.argv[1:]]
    all_findings: list[str] = []
    for path in targets:
        if path.suffix == ".py" and path.exists():
            all_findings.extend(audit_python_source(path.read_text(encoding="utf-8"), str(path)))
    for item in all_findings:
        print(item)
    sys.exit(1 if all_findings else 0)


if __name__ == "__main__":
    main()
