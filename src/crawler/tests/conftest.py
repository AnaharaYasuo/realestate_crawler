import os
import sys
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
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realestateSettings')
    if not settings.configured:
        settings.configure(
            SECRET_KEY='test_secret_key',
            INSTALLED_APPS=[
                'package',
            ],
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': ':memory:',
                }
            },
            MIGRATION_MODULES={
                'package': None,
            }
        )
    django.setup()
    # メモリDBにテーブルを自動作成
    call_command('migrate', interactive=False, verbosity=0, run_syncdb=True)
