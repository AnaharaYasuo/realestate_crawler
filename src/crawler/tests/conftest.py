import os
import sys
import pytest
import django
from django.conf import settings

# Ensure current directory is in path for fetch_snapshot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure src/crawler is in path for package module
crawler_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if crawler_path not in sys.path:
    sys.path.insert(0, crawler_path)

import fetch_snapshot

@pytest.fixture(scope="session", autouse=True)
def fetch_snapshots_fixture():
    """
    Automatically fetch snapshots for all targets at the start of the test session.
    Changes CWD to the directory of fetch_snapshot.py to ensure relative paths work correctly.
    """
    print("\n[Fixture] Starting automatic snapshot fetch...")
    original_cwd = os.getcwd()
    # Assuming fetch_snapshot is in the intended working directory (src/crawler)
    target_cwd = os.path.dirname(os.path.abspath(fetch_snapshot.__file__))
    
    try:
        if target_cwd:
            os.chdir(target_cwd)
            print(f"[Fixture] Changed CWD to: {os.getcwd()}")
            
        for site, types_dict in fetch_snapshot.TARGETS.items():
            for target_type in types_dict:
                print(f"[Fixture] Fetching {site} - {target_type}")
                fetch_snapshot.fetch_snapshot(site, target_type)
                
    except Exception as e:
        print(f"[Fixture] Error during snapshot fetch: {e}")
    finally:
        os.chdir(original_cwd)
        print(f"[Fixture] Restored CWD to: {original_cwd}")

def pytest_configure():
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
            }
        )
    django.setup()
