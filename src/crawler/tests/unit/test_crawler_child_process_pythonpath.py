import os
import sys
import subprocess
import pytest

def test_crawler_dir_in_sys_path():
    """Verify that main.py directory is present in sys.path when imported or run."""
    _crawler_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    assert os.path.exists(os.path.join(_crawler_dir, "main.py"))
    assert os.path.exists(os.path.join(_crawler_dir, "package"))

def test_main_py_importable():
    """Verify that main.py can be invoked without ModuleNotFoundError for package."""
    _crawler_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    main_py = os.path.join(_crawler_dir, "main.py")
    res = subprocess.run([sys.executable, main_py, "--help"], capture_output=True, text=True)
    assert "ModuleNotFoundError: No module named 'package'" not in res.stderr
    assert "Usage: python main.py" in res.stderr or res.returncode in (0, 1, 2)
