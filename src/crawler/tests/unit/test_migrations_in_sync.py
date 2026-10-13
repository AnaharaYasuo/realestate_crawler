"""Issue #905: モデルとマイグレーションの乖離検知 (makemigrations --check)"""
import io

from django.core.management import call_command
from django.test import override_settings


# テスト設定は MIGRATION_MODULES で package のマイグレーションを無効化しているため、解除して検査する
@override_settings(MIGRATION_MODULES={})
def test_migrations_in_sync_with_models():
    """未作成のマイグレーションが無いこと (差分があれば SystemExit(1))"""
    out = io.StringIO()
    try:
        call_command("makemigrations", "package", "--check", "--dry-run", stdout=out)
    except SystemExit:
        raise AssertionError(f"未作成マイグレーションあり:\n{out.getvalue()}")
