import os
import secrets

import django
from django.conf import settings
from dotenv import load_dotenv

# Load .env file
load_dotenv()
def configure():
    """Configure Django once for the active test, cloud, or local environment."""
    if not settings.configured:
        import sys
        is_testing = 'pytest' in sys.argv[0] or os.getenv('FORCE_SQLITE') == 'true'
        if is_testing:
            settings.configure(
                SECRET_KEY=os.getenv('SECRET_KEY', secrets.token_hex(32)),
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
            return

        is_cloud = bool(os.getenv('IS_CLOUD') or os.getenv('K_SERVICE') or os.getenv('CLOUD_RUN_JOB') or os.getenv('GOOGLE_CLOUD_PROJECT'))
        default_host = 'localhost' if is_cloud else 'db'

        settings.configure(
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.mysql',
                    'NAME': os.getenv('DB_NAME', 'real_estate'),
                    'USER': os.getenv('DB_USER', 'sumifu'),
                    'PASSWORD': os.getenv('DB_PASSWORD'),
                    'HOST': os.getenv('DB_HOST', default_host),
                    'PORT': os.getenv('DB_PORT', '3306'),
                    'CONN_MAX_AGE': 0,  # ProxySQL一元管理: アプリ側プールを禁止し即時切断
                    'OPTIONS': {'charset': 'utf8mb4'},
                }
            },
            INSTALLED_APPS=[
                'package.apps.SumifuappConfig'
            ]
        )
        django.setup()
