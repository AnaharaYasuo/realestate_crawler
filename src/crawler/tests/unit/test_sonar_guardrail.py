import ast
import tempfile
import os
import pytest
try:
    from scripts.debug_tools.check_local_sonar import (
        calculate_cognitive_complexity,
        detect_regex_redos_risks,
        scan_source_code,
        scan_file,
    )
except ImportError:
    from src.crawler.scripts.debug_tools.check_local_sonar import (
        calculate_cognitive_complexity,
        detect_regex_redos_risks,
        scan_source_code,
        scan_file,
    )


def test_cognitive_complexity_simple():
    code = """
def simple_func():
    return 42
"""
    tree = ast.parse(code)
    func = tree.body[0]
    score, details = calculate_cognitive_complexity(func)
    assert score == 0
    assert len(details) == 0


def test_cognitive_complexity_nested_ifs():
    code = """
def nested_func(a, b, c):
    if a:
        if b:
            if c:
                return 1
    return 0
"""
    tree = ast.parse(code)
    func = tree.body[0]
    score, details = calculate_cognitive_complexity(func)
    # if a (+1), if b (+2), if c (+3) => total 6
    assert score == 6
    assert len(details) == 3


def test_cognitive_complexity_bool_ops():
    code = """
def bool_func(a, b, c):
    if a and b or c:
        return 1
    return 0
"""
    tree = ast.parse(code)
    func = tree.body[0]
    score, details = calculate_cognitive_complexity(func)
    # if (+1), and (+1), or (+1) => total 3
    assert score == 3


def test_cognitive_complexity_threshold_exceeded():
    # Construct a function with complexity > 15
    code = """
def complex_func(a, b, c, d, e):
    if a:
        for x in b:
            if x > 0:
                while c:
                    if d:
                        try:
                            if e:
                                pass
                        except Exception:
                            if not a:
                                pass
"""
    tree = ast.parse(code)
    func = tree.body[0]
    score, _ = calculate_cognitive_complexity(func)
    assert score > 15


def test_cognitive_complexity_while_orelse():
    code = """
def while_else_func(a):
    while a:
        pass
    else:
        if a:
            pass
"""
    tree = ast.parse(code)
    func = tree.body[0]
    score, details = calculate_cognitive_complexity(func)
    # while (+1), if in else (+2 because in else block)
    assert score >= 3


def test_cognitive_complexity_nested_function_isolation():
    code = """
def outer_func(a):
    if a:
        def inner_func(b):
            if b:
                pass
        return inner_func
"""
    tree = ast.parse(code)
    func = tree.body[0]
    score, _ = calculate_cognitive_complexity(func)
    # outer_func should only count 'if a' (+1), inner_func should be isolated
    assert score == 1


def test_detect_regex_redos_risks():
    code = r'''
import re

# Risky regex: nested quantifier
pattern1 = re.compile(r"(a+)+")

# Risky regex: greedy ambiguous dot with group
match = re.search(r"価格.*?(\d+)万円", text)

# Safe regex
safe_pattern = re.compile(r"価格[^\d]*(\d+)万円")
safe_match = re.search(r"\d{4}-\d{2}-\d{2}", text)
'''
    issues = detect_regex_redos_risks(code, filename="dummy.py")
    assert len(issues) >= 2
    messages = [i["message"] for i in issues]
    assert any("backtracking" in m.lower() or "redos" in m.lower() for m in messages)


def test_detect_regex_length_limit():
    long_pat = "a" * 501
    code = f'import re\nre.match(pattern="{long_pat}", string="test")'
    issues = detect_regex_redos_risks(code, filename="dummy.py")
    assert len(issues) == 1
    assert "exceeds maximum safe length" in issues[0]["message"]


def test_detect_regex_api_variants():
    code = '''
import re
re.fullmatch(r"(x+)+", s)
re.split(r"(y+)+", s)
'''
    issues = detect_regex_redos_risks(code, filename="dummy.py")
    assert len(issues) == 2


def test_scan_source_code_clean():
    clean_code = """
def clean_function(data):
    if not data:
        return None
    return [x * 2 for x in data]
"""
    issues = scan_source_code(clean_code, filename="clean.py", max_complexity=15)
    assert len(issues) == 0


def test_scan_file():
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("""
import re

def high_complexity(a, b, c, d, e):
    if a:
        for x in b:
            if x > 0:
                while c:
                    if d:
                        if e:
                            pass
    re.search(r"(x+)+", a)
""")
        temp_path = f.name

    try:
        issues = scan_file(temp_path, max_complexity=5)
        # Should detect complexity > 5 and redos regex
        rules = [i["rule"] for i in issues]
        assert "python:S3776" in rules
        assert "python:S8786" in rules
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
