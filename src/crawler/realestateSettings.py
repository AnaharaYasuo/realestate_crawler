import os
import secrets
import socket
import sys

import django
from django.conf import settings
from dotenv import load_dotenv
from package.utils.db_timeouts import bound_mysql_timeouts

# Load .env file
load_dotenv()


def _resolve_db_target(default_host: str) -> tuple[str, str]:
    """Resolve active DB host and port.

    When DB_HOST is omitted, defaults to 'localhost' for cloud or 'db' for local Docker.
    If explicitly enabled via ALLOW_CONTAINER_DB_FALLBACK=true and running in container,
    falls back from unreachable host.docker.internal to internal service 'db:3306'.
    """
    configured_host = os.getenv("DB_HOST", default_host)
    configured_port = os.getenv("DB_PORT", "3306")
    allow_fallback = os.getenv("ALLOW_CONTAINER_DB_FALLBACK", "true").lower() in ("true", "1", "yes")
    if (
        allow_fallback
        and configured_host == "host.docker.internal"
        and (os.path.exists("/.dockerenv") or os.path.exists("/proc/1/cgroup"))
    ):
        s = socket.socket()
        s.settimeout(0.5)
        try:
            s.connect((configured_host, int(configured_port)))
            s.close()
        except OSError:
            return ("db", "3306")
    return (configured_host, configured_port)


def get_database_config():
    """Build production MySQL database settings dict based on active environment variables."""
    is_cloud = bool(os.getenv('IS_CLOUD') or os.getenv('K_SERVICE') or os.getenv('CLOUD_RUN_JOB') or os.getenv('GOOGLE_CLOUD_PROJECT'))
    default_host = 'localhost' if is_cloud else 'db'
    db_host, db_port = _resolve_db_target(default_host)
    cfg = {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME', 'real_estate'),
        'USER': os.getenv('DB_USER', 'sumifu'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': db_host,
        'PORT': db_port,
        'CONN_MAX_AGE': 0,  # ProxySQL一元管理: アプリ側プールを禁止し即時切断
        'OPTIONS': {'charset': 'utf8mb4'},
    }
    bound_mysql_timeouts(cfg)
    return cfg


def configure():
    """Configure Django once for the active test, cloud, or local environment."""
    if not settings.configured:
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
        db_host, db_port = _resolve_db_target(default_host)

        db_cfg = {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.getenv('DB_NAME', 'real_estate'),
            'USER': os.getenv('DB_USER', 'sumifu'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': db_host,
            'PORT': db_port,
            'CONN_MAX_AGE': 0,  # ProxySQL一元管理: アプリ側プールを禁止し即時切断
            'OPTIONS': {'charset': 'utf8mb4'},
        }
        bound_mysql_timeouts(db_cfg)

        settings.configure(
            DATABASES={
                'default': db_cfg
            },
            INSTALLED_APPS=[
                'package.apps.SumifuappConfig'
            ]
        )
        django.setup()
