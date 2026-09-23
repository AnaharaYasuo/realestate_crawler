import os
import sys
import secrets
import django
from django.conf import settings

# Ensure current directory is in path for fetch_snapshot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure src/crawler is in path for package module
crawler_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if crawler_path not in sys.path:
    sys.path.insert(0, crawler_path)

# 普遍原則 (AGENTS.md): 固定モックファイルは使用せず、動的ライブ検証を実施


def pytest_configure():
    from django.core.management import call_command
    import tempfile

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realestateSettings')
    if not settings.configured:
        # Per-process file so parallel Start-Job / xdist workers do not lock one another.
        # Avoid :memory: — asyncio.to_thread ORM saves need a shared schema per process.
        db_path = os.path.join(
            tempfile.gettempdir(), f"crawl_guarantee_pytest_{os.getpid()}.sqlite3"
        )
        settings.configure(
            SECRET_KEY=os.getenv('SECRET_KEY', secrets.token_hex(32)),
            INSTALLED_APPS=[
                'package',
            ],
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': db_path,
                    'OPTIONS': {
                        'timeout': 30,
                    },
                }
            },
            MIGRATION_MODULES={
                'package': None,
            }
        )
    django.setup()
    # メモリ/ファイルDBにテーブルを自動作成
    call_command('migrate', interactive=False, verbosity=0, run_syncdb=True)
