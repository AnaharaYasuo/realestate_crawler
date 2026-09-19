import os
import secrets
import django
from django.conf import settings
from dotenv import load_dotenv

# Load .env file
load_dotenv()
def configure():
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
        if is_cloud:
            settings.configure(
                DATABASES={
                    'default': {
                        'ENGINE': 'dj_db_conn_pool.backends.mysql',
                        'NAME': os.getenv('DB_NAME', 'real_estate'),
                        'USER': os.getenv('DB_USER', 'sumifu'),
                        'PASSWORD': os.getenv('DB_PASSWORD'),
                        'HOST': os.getenv('DB_HOST', '10.128.0.17'),
                        'PORT': os.getenv('DB_PORT', '3306'),
                        'OPTIONS': {'charset': 'utf8mb4'},
                        'POOL_OPTIONS': {
                            'POOL_SIZE': int(os.getenv('DB_POOL_SIZE', 10)),
                            'MAX_OVERFLOW': int(os.getenv('DB_MAX_OVERFLOW', -1)),
                            'RECYCLE': int(os.getenv('DB_POOL_RECYCLE', 1800)),
                        }
                    }
                }
                , INSTALLED_APPS=[
                     'package.apps.SumifuappConfig'
                ]
            )
        else:
            db_engine = 'django.db.backends.mysql'
            try:
                import dj_db_conn_pool
                db_engine = 'dj_db_conn_pool.backends.mysql'
            except ImportError:
                pass

            settings.configure(
                DATABASES={
                    'default': {
                        'ENGINE': db_engine,
                        'NAME': os.getenv('DB_NAME', 'real_estate'),
                        'USER': os.getenv('DB_USER', 'sumifu'),
                        'PASSWORD': os.getenv('DB_PASSWORD'),
                        'HOST': os.getenv('DB_HOST', 'db'),
                        'PORT': os.getenv('DB_PORT', '3306'),
                        'OPTIONS': {'charset': 'utf8mb4'},
                        'POOL_OPTIONS': {
                            'POOL_SIZE': int(os.getenv('DB_POOL_SIZE', 10)),
                            'MAX_OVERFLOW': int(os.getenv('DB_MAX_OVERFLOW', -1)),
                            'RECYCLE': int(os.getenv('DB_POOL_RECYCLE', 1800)),
                        }
                    }
                }
                , INSTALLED_APPS=[
                     'package.apps.SumifuappConfig'
                ]
            )
        django.setup()