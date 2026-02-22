import os
import django
from django.conf import settings
from dotenv import load_dotenv

# Load .env file
load_dotenv()
def configure():
    if not settings.configured:
        if os.getenv('IS_CLOUD', ''):
            settings.configure(
                DATABASES={
                    'default': {
                        'ENGINE': 'django.db.backends.mysql',
                        'NAME': os.getenv('DB_NAME', 'real_estate'),
                        'USER': os.getenv('DB_USER', 'sumifu'),
                        'PASSWORD': os.getenv('DB_PASSWORD'),
                        'HOST': os.getenv('DB_HOST', '10.128.0.17'),
                        'PORT': os.getenv('DB_PORT', '13306'),
                        'OPTIONS': {'charset': 'utf8mb4'},
                    }
                }
                , INSTALLED_APPS=[
                     'package.apps.SumifuappConfig'
                ]
            )
        else:
            settings.configure(
                DATABASES={
                    'default': {
                        'ENGINE': 'django.db.backends.mysql',
                        'NAME': os.getenv('DB_NAME', 'real_estate'),
                        'USER': os.getenv('DB_USER', 'sumifu'),
                        'PASSWORD': os.getenv('DB_PASSWORD'),
                        'HOST': os.getenv('DB_HOST', '34.122.252.162'),
                        'PORT': os.getenv('DB_PORT', '13306'),
                        'OPTIONS': {'charset': 'utf8mb4'},
                    }
                }
                , INSTALLED_APPS=[
                     'package.apps.SumifuappConfig'
                ]
            )
        django.setup()