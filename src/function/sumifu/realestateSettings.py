import os
import django
from django.conf import settings
def configure():
    if not settings.configured:
        if os.getenv('IS_CLOUD', ''):
            settings.configure(
                DATABASES={
                    'default': {
                        'ENGINE': 'django.db.backends.mysql',
                        'NAME': 'real_estate',
                        'USER': 'sumifu',
                        'PASSWORD': 'mayumimayumi0413',
                        'HOST': '10.128.0.17',
                        'PORT': '13306',
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
                        'NAME': 'real_estate',
                        'USER': 'sumifu',
                        'PASSWORD': 'mayumimayumi0413',
                        'HOST': '34.122.252.162',
                        'PORT': '13306',
                    }
                }
                , INSTALLED_APPS=[
                     'package.apps.SumifuappConfig'
                ]
            )
        django.setup()