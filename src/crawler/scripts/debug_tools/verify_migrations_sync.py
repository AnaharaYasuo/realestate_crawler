import os
import sys

# Worktree 内の src/crawler を参照
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import realestateSettings

realestateSettings.configure()

from io import StringIO

from django.core.management import call_command

out = StringIO()
err = StringIO()

try:
    call_command("makemigrations", "--check", "--dry-run", stdout=out, stderr=err)
    print("SUCCESS: No changes detected! Migrations are completely in sync with models.")
    print("Stdout:", out.getvalue())
except SystemExit as e:
    print(f"FAILED (exit code {e.code}): Pending changes detected!")
    print("Stdout:", out.getvalue())
    print("Stderr:", err.getvalue())
    sys.exit(e.code)
