import asyncio
import aiohttp
import os
import json
import ssl
import traceback
from abc import ABCMeta, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path
import re
import uuid
import requests
from package.utils.storage import get_storage_manager
from package.ml.investment_evaluator import evaluate_investment_property

from package.parser.baseParser import LoadPropertyPageException, ParserBase, \
    ReadPropertyNameException, SkipPropertyException, ListingEndedException

import datetime
from django.core.exceptions import ValidationError
from django.db import close_old_connections, OperationalError
from builtins import Exception
import logging
from decimal import Decimal
from package.api.middleware import CrawlerMiddleware, LoggingMiddleware
from package.utils.report import CrawlerReporter
from asgiref.sync import sync_to_async
from package.api.differential import filter_differential_items, ListItem
from package.models.evaluation import PropertyPriceHistory
from package.utils.url_matcher import UrlMatcher
from package.utils.property_type_detector import PropertyTypeDetector
from package.utils.converter import parse_chidai
header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
GLOBAL_SAVE_COUNT = 0

ERROR_PAGES_DIR = Path("src/crawler/tests/error_pages")
CAMEL_TO_SNAKE_PATTERN = re.compile(r'(?<!^)(?=[A-Z])')
DETAIL_ID_PATTERN = re.compile(r'detail_([^/]+)')
BKDETAIL_ID_PATTERN = re.compile(r'bkdetail/([^/]+)')


def _sync_save_error_html_by_url(url: str, model_name: str, reason: str = "Unknown Error") -> None:
    """Save HTML of failed property/page synchronously in worker thread."""
    ERROR_PAGES_DIR.mkdir(parents=True, exist_ok=True)
    company_type = CAMEL_TO_SNAKE_PATTERN.sub('_', model_name).lower()
    company_dir = ERROR_PAGES_DIR / company_type
    company_dir.mkdir(parents=True, exist_ok=True)

    match = DETAIL_ID_PATTERN.search(url) or BKDETAIL_ID_PATTERN.search(url)
    p_id = match.group(1) if match else str(int(datetime.datetime.now().timestamp()))

    html_file = company_dir / f"{p_id}.html"
    response = requests.get(url, headers=header, timeout=30)
    if response.status_code == 200:
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        meta_file = company_dir / f"{p_id}_meta.txt"
        with open(meta_file, 'w', encoding='utf-8') as f:
            f.write(f"URL: {url}\nModel/Class: {model_name}\nTimestamp: {datetime.datetime.now()}\nReason: {reason}\n")
        logging.info("Saved error HTML to %s", html_file)


TCP_CONNECTOR_LIMIT = 100
SUMIFU_MANSION_START_ENDPOINT = '/sumifu_mansion_start'
API_KEY_MANSION_ALL_START = '/api/all/mansion/start'
API_KEY_TOCHI_ALL_START = '/api/all/tochi/start'

API_KEY_MITSUI_MANSION_START = '/api/mitsui/mansion/start'
API_KEY_MITSUI_MANSION_START_GCP = SUMIFU_MANSION_START_ENDPOINT
API_KEY_MITSUI_MANSION_AREA = '/api/mitsui/mansion/area'
API_KEY_MITSUI_MANSION_AREA_GCP = '/mitsui_mansion_area'
API_KEY_MITSUI_MANSION_LIST = '/api/mitsui/mansion/list'
API_KEY_MITSUI_MANSION_LIST_GCP = '/mitsui_mansion_list'
API_KEY_MITSUI_MANSION_DETAIL = '/api/mitsui/mansion/detail'
API_KEY_MITSUI_MANSION_DETAIL_GCP = '/mitsui_mansion_detail'
API_KEY_MITSUI_MANSION_DETAIL_TEST = '/api/mitsui/mansion/detail/test'

API_KEY_MITSUI_TOCHI_START = '/api/mitsui/tochi/start'
API_KEY_MITSUI_TOCHI_START_GCP = '/sumifu_tochi_start'
API_KEY_MITSUI_TOCHI_AREA = '/api/mitsui/tochi/area'
API_KEY_MITSUI_TOCHI_AREA_GCP = '/mitsui_tochi_area'
API_KEY_MITSUI_TOCHI_LIST = '/api/mitsui/tochi/list'
API_KEY_MITSUI_TOCHI_LIST_GCP = '/mitsui_tochi_list'
API_KEY_MITSUI_TOCHI_DETAIL = '/api/mitsui/tochi/detail'
API_KEY_MITSUI_TOCHI_DETAIL_GCP = '/mitsui_tochi_detail'
API_KEY_MITSUI_TOCHI_DETAIL_TEST = '/api/mitsui/tochi/detail/test'

API_KEY_MITSUI_KODATE_START = '/api/mitsui/kodate/start'
API_KEY_MITSUI_KODATE_START_GCP = '/sumifu_kodate_start'
API_KEY_MITSUI_KODATE_AREA = '/api/mitsui/kodate/area'
API_KEY_MITSUI_KODATE_AREA_GCP = '/mitsui_kodate_area'
API_KEY_MITSUI_KODATE_LIST = '/api/mitsui/kodate/list'
API_KEY_MITSUI_KODATE_LIST_GCP = '/mitsui_kodate_list'
API_KEY_MITSUI_KODATE_DETAIL = '/api/mitsui/kodate/detail'
API_KEY_MITSUI_KODATE_DETAIL_GCP = '/mitsui_kodate_detail'
API_KEY_MITSUI_KODATE_DETAIL_TEST = '/api/mitsui/kodate/detail/test'

API_KEY_SUMIFU_MANSION_START = '/api/sumifu/mansion/start'
API_KEY_SUMIFU_MANSION_START_GCP = SUMIFU_MANSION_START_ENDPOINT
API_KEY_SUMIFU_MANSION_REGION = '/api/sumifu/mansion/region'
API_KEY_SUMIFU_MANSION_REGION_GCP = '/sumifu_mansion_region'
API_KEY_SUMIFU_MANSION_AREA = '/api/sumifu/mansion/area'
API_KEY_SUMIFU_MANSION_AREA_GCP = '/sumifu_mansion_area'
API_KEY_SUMIFU_MANSION_LIST = '/api/sumifu/mansion/list'
API_KEY_SUMIFU_MANSION_LIST_GCP = '/sumifu_mansion_list'
API_KEY_SUMIFU_MANSION_DETAIL = '/api/sumifu/mansion/detail'
API_KEY_SUMIFU_MANSION_DETAIL_GCP = '/sumifu_mansion_detail'
API_KEY_SUMIFU_MANSION_LIST_DETAIL = '/api/sumifu/mansion/listdetail'
API_KEY_SUMIFU_MANSION_LIST_DETAIL_GCP = '/sumifu_mansion_listdetail'
API_KEY_SUMIFU_MANSION_DETAIL_TEST = '/api/sumifu/mansion/detail/test'

API_KEY_SUMIFU_TOCHI_START = '/api/sumifu/tochi/start'
API_KEY_SUMIFU_TOCHI_START_GCP = '/sumifu_tochi_start'
API_KEY_SUMIFU_TOCHI_REGION = '/api/sumifu/tochi/region'
API_KEY_SUMIFU_TOCHI_REGION_GCP = '/sumifu_tochi_region'
API_KEY_SUMIFU_TOCHI_AREA = '/api/sumifu/tochi/area'
API_KEY_SUMIFU_TOCHI_AREA_GCP = '/sumifu_tochi_area'
API_KEY_SUMIFU_TOCHI_LIST = '/api/sumifu/tochi/list'
API_KEY_SUMIFU_TOCHI_LIST_GCP = '/sumifu_tochi_list'
API_KEY_SUMIFU_TOCHI_DETAIL = '/api/sumifu/tochi/detail'
API_KEY_SUMIFU_TOCHI_DETAIL_GCP = '/sumifu_tochi_detail'
API_KEY_SUMIFU_TOCHI_LIST_DETAIL = '/api/sumifu/tochi/listdetail'
API_KEY_SUMIFU_TOCHI_LIST_DETAIL_GCP = '/sumifu_tochi_listdetail'
API_KEY_SUMIFU_TOCHI_DETAIL_TEST = '/api/sumifu/tochi/detail/test'

API_KEY_SUMIFU_KODATE_START = '/api/sumifu/kodate/start'
API_KEY_SUMIFU_KODATE_START_GCP = '/sumifu_kodate_start'
API_KEY_SUMIFU_KODATE_REGION = '/api/sumifu/kodate/region'
API_KEY_SUMIFU_KODATE_REGION_GCP = '/sumifu_kodate_region'
API_KEY_SUMIFU_KODATE_AREA = '/api/sumifu/kodate/area'
API_KEY_SUMIFU_KODATE_AREA_GCP = '/sumifu_kodate_area'
API_KEY_SUMIFU_KODATE_LIST = '/api/sumifu/kodate/list'
API_KEY_SUMIFU_KODATE_LIST_GCP = '/sumifu_kodate_list'
API_KEY_SUMIFU_KODATE_DETAIL = '/api/sumifu/kodate/detail'
API_KEY_SUMIFU_KODATE_DETAIL_GCP = '/sumifu_kodate_detail'
API_KEY_SUMIFU_KODATE_LIST_DETAIL = '/api/sumifu/kodate/listdetail'
API_KEY_SUMIFU_KODATE_LIST_DETAIL_GCP = '/sumifu_kodate_listdetail'
API_KEY_SUMIFU_KODATE_DETAIL_TEST = '/api/sumifu/kodate/detail/test'

API_KEY_SUMIFU_INVEST_START = '/api/sumifu/investment/start'
API_KEY_SUMIFU_INVEST_START_GCP = '/sumifu_investment_start'
API_KEY_SUMIFU_INVEST_REGION = '/api/sumifu/investment/region'
API_KEY_SUMIFU_INVEST_REGION_GCP = '/sumifu_investment_region'
API_KEY_SUMIFU_INVEST_AREA = '/api/sumifu/investment/area'
API_KEY_SUMIFU_INVEST_AREA_GCP = '/sumifu_investment_area'
API_KEY_SUMIFU_INVEST_LIST = '/api/sumifu/investment/list'
API_KEY_SUMIFU_INVEST_LIST_GCP = '/sumifu_investment_list'
API_KEY_SUMIFU_INVEST_DETAIL = '/api/sumifu/investment/detail'
API_KEY_SUMIFU_INVEST_DETAIL_GCP = '/sumifu_investment_detail'

# Sumifu Investment Kodate (戸建て賃貸)
API_KEY_SUMIFU_INVEST_KODATE_START = '/api/sumifu/investment/kodate/start'
API_KEY_SUMIFU_INVEST_KODATE_START_GCP = '/sumifu_investment_kodate_start'
API_KEY_SUMIFU_INVEST_KODATE_LIST = '/api/sumifu/investment/kodate/list'
API_KEY_SUMIFU_INVEST_KODATE_LIST_GCP = '/sumifu_investment_kodate_list'
API_KEY_SUMIFU_INVEST_KODATE_DETAIL = '/api/sumifu/investment/kodate/detail'
API_KEY_SUMIFU_INVEST_KODATE_DETAIL_GCP = '/sumifu_investment_kodate_detail'

# Sumifu Investment Apartment (アパート)
API_KEY_SUMIFU_INVEST_APARTMENT_START = '/api/sumifu/investment/apartment/start'
API_KEY_SUMIFU_INVEST_APARTMENT_START_GCP = '/sumifu_investment_apartment_start'
API_KEY_SUMIFU_INVEST_APARTMENT_LIST = '/api/sumifu/investment/apartment/list'
API_KEY_SUMIFU_INVEST_APARTMENT_LIST_GCP = '/sumifu_investment_apartment_list'
API_KEY_SUMIFU_INVEST_APARTMENT_DETAIL = '/api/sumifu/investment/apartment/detail'
API_KEY_SUMIFU_INVEST_APARTMENT_DETAIL_GCP = '/sumifu_investment_apartment_detail'

# Mitsui Investment Kodate (戸建て賃貸)
API_KEY_MITSUI_INVEST_KODATE_START = '/api/mitsui/investment/kodate/start'
API_KEY_MITSUI_INVEST_KODATE_START_GCP = '/mitsui_investment_kodate_start'
API_KEY_MITSUI_INVEST_KODATE_AREA = '/api/mitsui/investment/kodate/area'
API_KEY_MITSUI_INVEST_KODATE_AREA_GCP = '/mitsui_investment_kodate_area'
API_KEY_MITSUI_INVEST_KODATE_LIST = '/api/mitsui/investment/kodate/list'
API_KEY_MITSUI_INVEST_KODATE_LIST_GCP = '/mitsui_investment_kodate_list'
API_KEY_MITSUI_INVEST_KODATE_DETAIL = '/api/mitsui/investment/kodate/detail'
API_KEY_MITSUI_INVEST_KODATE_DETAIL_GCP = '/mitsui_investment_kodate_detail'

# Mitsui Investment Apartment (アパート)
API_KEY_MITSUI_INVEST_APARTMENT_START = '/api/mitsui/investment/apartment/start'
API_KEY_MITSUI_INVEST_APARTMENT_START_GCP = '/mitsui_investment_apartment_start'
API_KEY_MITSUI_INVEST_APARTMENT_AREA = '/api/mitsui/investment/apartment/area'
API_KEY_MITSUI_INVEST_APARTMENT_AREA_GCP = '/mitsui_investment_apartment_area'
API_KEY_MITSUI_INVEST_APARTMENT_LIST = '/api/mitsui/investment/apartment/list'
API_KEY_MITSUI_INVEST_APARTMENT_LIST_GCP = '/mitsui_investment_apartment_list'
API_KEY_MITSUI_INVEST_APARTMENT_DETAIL = '/api/mitsui/investment/apartment/detail'
API_KEY_MITSUI_INVEST_APARTMENT_DETAIL_GCP = '/mitsui_investment_apartment_detail'

# Tokyu Investment Kodate (戸建て賃貸)
API_KEY_TOKYU_INVEST_KODATE_START = '/api/tokyu/investment/kodate/start'
API_KEY_TOKYU_INVEST_KODATE_START_GCP = '/tokyu_investment_kodate_start'
API_KEY_TOKYU_INVEST_KODATE_LIST = '/api/tokyu/investment/kodate/list'
API_KEY_TOKYU_INVEST_KODATE_LIST_GCP = '/tokyu_investment_kodate_list'
API_KEY_TOKYU_INVEST_KODATE_DETAIL = '/api/tokyu/investment/kodate/detail'
API_KEY_TOKYU_INVEST_KODATE_DETAIL_GCP = '/tokyu_investment_kodate_detail'

# Tokyu Investment Apartment (アパート)
API_KEY_TOKYU_INVEST_APARTMENT_START = '/api/tokyu/investment/apartment/start'
API_KEY_TOKYU_INVEST_APARTMENT_START_GCP = '/tokyu_investment_apartment_start'
API_KEY_TOKYU_INVEST_APARTMENT_LIST = '/api/tokyu/investment/apartment/list'
API_KEY_TOKYU_INVEST_APARTMENT_LIST_GCP = '/tokyu_investment_apartment_list'
API_KEY_TOKYU_INVEST_APARTMENT_DETAIL = '/api/tokyu/investment/apartment/detail'
API_KEY_TOKYU_INVEST_APARTMENT_DETAIL_GCP = '/tokyu_investment_apartment_detail'

# Nomura Investment Kodate (戸建て賃貸)
API_KEY_NOMURA_INVEST_KODATE_START = '/api/nomura/investment/kodate/start'
API_KEY_NOMURA_INVEST_KODATE_START_GCP = '/nomura_investment_kodate_start'
API_KEY_NOMURA_INVEST_KODATE_LIST = '/api/nomura/investment/kodate/list'
API_KEY_NOMURA_INVEST_KODATE_LIST_GCP = '/nomura_investment_kodate_list'
API_KEY_NOMURA_INVEST_KODATE_DETAIL = '/api/nomura/investment/kodate/detail'
API_KEY_NOMURA_INVEST_KODATE_DETAIL_GCP = '/nomura_investment_kodate_detail'

# Nomura Investment Apartment (アパート)
API_KEY_NOMURA_INVEST_APARTMENT_START = '/api/nomura/investment/apartment/start'
API_KEY_NOMURA_INVEST_APARTMENT_START_GCP = '/nomura_investment_apartment_start'
API_KEY_NOMURA_INVEST_APARTMENT_LIST = '/api/nomura/investment/apartment/list'
API_KEY_NOMURA_INVEST_APARTMENT_LIST_GCP = '/nomura_investment_apartment_list'
API_KEY_NOMURA_INVEST_APARTMENT_DETAIL = '/api/nomura/investment/apartment/detail'
API_KEY_NOMURA_INVEST_APARTMENT_DETAIL_GCP = '/nomura_investment_apartment_detail'

# Misawa Investment Kodate (戸建て賃貸)
API_KEY_MISAWA_INVEST_KODATE_START = '/api/misawa/investment/kodate/start'
API_KEY_MISAWA_INVEST_KODATE_START_GCP = '/misawa_investment_kodate_start'
API_KEY_MISAWA_INVEST_KODATE_LIST = '/api/misawa/investment/kodate/list'
API_KEY_MISAWA_INVEST_KODATE_LIST_GCP = '/misawa_investment_kodate_list'
API_KEY_MISAWA_INVEST_KODATE_DETAIL = '/api/misawa/investment/kodate/detail'
API_KEY_MISAWA_INVEST_KODATE_DETAIL_GCP = '/misawa_investment_kodate_detail'

# Misawa Investment Apartment (アパート)
API_KEY_MISAWA_INVEST_APARTMENT_START = '/api/misawa/investment/apartment/start'
API_KEY_MISAWA_INVEST_APARTMENT_START_GCP = '/misawa_investment_apartment_start'
API_KEY_MISAWA_INVEST_APARTMENT_LIST = '/api/misawa/investment/apartment/list'
API_KEY_MISAWA_INVEST_APARTMENT_LIST_GCP = '/misawa_investment_apartment_list'
API_KEY_MISAWA_INVEST_APARTMENT_DETAIL = '/api/misawa/investment/apartment/detail'
API_KEY_MISAWA_INVEST_APARTMENT_DETAIL_GCP = '/misawa_investment_apartment_detail'

API_KEY_TOKYU_MANSION_START = '/api/tokyu/mansion/start'
API_KEY_TOKYU_MANSION_START_GCP = SUMIFU_MANSION_START_ENDPOINT
API_KEY_TOKYU_MANSION_AREA = '/api/tokyu/mansion/area'
API_KEY_TOKYU_MANSION_AREA_GCP = '/tokyu_mansion_area'
API_KEY_TOKYU_MANSION_LIST = '/api/tokyu/mansion/list'
API_KEY_TOKYU_MANSION_LIST_GCP = '/tokyu_mansion_list'
API_KEY_TOKYU_MANSION_DETAIL = '/api/tokyu/mansion/detail'
API_KEY_TOKYU_MANSION_DETAIL_GCP = '/tokyu_mansion_detail'
API_KEY_TOKYU_MANSION_DETAIL_TEST = '/api/tokyu/mansion/detail/test'


API_KEY_TOKYU_TOCHI_START = '/api/tokyu/tochi/start'
API_KEY_TOKYU_TOCHI_START_GCP = '/tokyu_tochi_start'
API_KEY_TOKYU_TOCHI_AREA = '/api/tokyu/tochi/area'
API_KEY_TOKYU_TOCHI_AREA_GCP = '/tokyu_tochi_area'
API_KEY_TOKYU_TOCHI_LIST = '/api/tokyu/tochi/list'
API_KEY_TOKYU_TOCHI_LIST_GCP = '/tokyu_tochi_list'
API_KEY_TOKYU_TOCHI_DETAIL = '/api/tokyu/tochi/detail'
API_KEY_TOKYU_TOCHI_DETAIL_GCP = '/tokyu_tochi_detail'
API_KEY_TOKYU_TOCHI_DETAIL_TEST = '/api/tokyu/tochi/detail/test'

API_KEY_TOKYU_KODATE_START = '/api/tokyu/kodate/start'
API_KEY_TOKYU_KODATE_START_GCP = '/tokyu_kodate_start'
API_KEY_TOKYU_KODATE_AREA = '/api/tokyu/kodate/area'
API_KEY_TOKYU_KODATE_AREA_GCP = '/tokyu_kodate_area'
API_KEY_TOKYU_KODATE_LIST = '/api/tokyu/kodate/list'
API_KEY_TOKYU_KODATE_LIST_GCP = '/tokyu_kodate_list'
API_KEY_TOKYU_KODATE_DETAIL = '/api/tokyu/kodate/detail'
API_KEY_TOKYU_KODATE_DETAIL_GCP = '/tokyu_kodate_detail'
API_KEY_TOKYU_KODATE_DETAIL_TEST = '/api/tokyu/kodate/detail/test'


# Nomura Mansion
API_KEY_NOMURA_MANSION_START = '/api/nomura/mansion/start'
API_KEY_NOMURA_MANSION_START_GCP = '/nomura_mansion_start'
API_KEY_NOMURA_MANSION_REGION = '/api/nomura/mansion/region'
API_KEY_NOMURA_MANSION_REGION_GCP = '/nomura_mansion_region'
API_KEY_NOMURA_MANSION_AREA = '/api/nomura/mansion/area'
API_KEY_NOMURA_MANSION_AREA_GCP = '/nomura_mansion_area'
API_KEY_NOMURA_MANSION_LIST = '/api/nomura/mansion/list'
API_KEY_NOMURA_MANSION_LIST_GCP = '/nomura_mansion_list'
API_KEY_NOMURA_MANSION_DETAIL = '/api/nomura/mansion/detail'
API_KEY_NOMURA_MANSION_DETAIL_GCP = '/nomura_mansion_detail'

# Nomura Kodate
API_KEY_NOMURA_KODATE_START = '/api/nomura/kodate/start'
API_KEY_NOMURA_KODATE_START_GCP = '/nomura_kodate_start'
API_KEY_NOMURA_KODATE_REGION = '/api/nomura/kodate/region'
API_KEY_NOMURA_KODATE_REGION_GCP = '/nomura_kodate_region'
API_KEY_NOMURA_KODATE_AREA = '/api/nomura/kodate/area'
API_KEY_NOMURA_KODATE_AREA_GCP = '/nomura_kodate_area'
API_KEY_NOMURA_KODATE_LIST = '/api/nomura/kodate/list'
API_KEY_NOMURA_KODATE_LIST_GCP = '/nomura_kodate_list'
API_KEY_NOMURA_KODATE_DETAIL = '/api/nomura/kodate/detail'
API_KEY_NOMURA_KODATE_DETAIL_GCP = '/nomura_kodate_detail'

# Nomura Tochi
API_KEY_NOMURA_TOCHI_START = '/api/nomura/tochi/start'
API_KEY_NOMURA_TOCHI_START_GCP = '/nomura_tochi_start'
API_KEY_NOMURA_TOCHI_REGION = '/api/nomura/tochi/region'
API_KEY_NOMURA_TOCHI_REGION_GCP = '/nomura_tochi_region'
API_KEY_NOMURA_TOCHI_AREA = '/api/nomura/tochi/area'
API_KEY_NOMURA_TOCHI_AREA_GCP = '/nomura_tochi_area'
API_KEY_NOMURA_TOCHI_LIST = '/api/nomura/tochi/list'
API_KEY_NOMURA_TOCHI_LIST_GCP = '/nomura_tochi_list'
API_KEY_NOMURA_TOCHI_DETAIL = '/api/nomura/tochi/detail'
API_KEY_NOMURA_TOCHI_DETAIL_GCP = '/nomura_tochi_detail'

API_KEY_TOKYU_INVEST_START = '/api/tokyu/investment/start'
API_KEY_TOKYU_INVEST_START_GCP = '/tokyu_investment_start'
API_KEY_TOKYU_INVEST_LIST = '/api/tokyu/investment/list'
API_KEY_TOKYU_INVEST_LIST_GCP = '/tokyu_investment_list'
API_KEY_TOKYU_INVEST_DETAIL = '/api/tokyu/investment/detail'
API_KEY_TOKYU_INVEST_DETAIL_GCP = '/tokyu_investment_detail'

API_KEY_SUMIFU_INVEST_START = '/api/sumifu/investment/start'
API_KEY_SUMIFU_INVEST_START_GCP = '/sumifu_investment_start'
API_KEY_SUMIFU_INVEST_LIST = '/api/sumifu/investment/list'
API_KEY_SUMIFU_INVEST_LIST_GCP = '/sumifu_investment_list'
API_KEY_SUMIFU_INVEST_DETAIL = '/api/sumifu/investment/detail'
API_KEY_SUMIFU_INVEST_DETAIL_GCP = '/sumifu_investment_detail'

API_KEY_MISAWA_MANSION_START = '/api/misawa/mansion/start'
API_KEY_MISAWA_MANSION_LIST = '/api/misawa/mansion/list'
API_KEY_MISAWA_MANSION_DETAIL = '/api/misawa/mansion/detail'

API_KEY_MISAWA_KODATE_START = '/api/misawa/kodate/start'
API_KEY_MISAWA_KODATE_LIST = '/api/misawa/kodate/list'
API_KEY_MISAWA_KODATE_DETAIL = '/api/misawa/kodate/detail'

API_KEY_MISAWA_TOCHI_START = '/api/misawa/tochi/start'
API_KEY_MISAWA_TOCHI_LIST = '/api/misawa/tochi/list'
API_KEY_MISAWA_TOCHI_DETAIL = '/api/misawa/tochi/detail'
API_KEY_MISAWA_INVEST_START = '/api/misawa/investment/start'

API_KEY_KILL = '/api/kill'

# Athome
API_KEY_ATHOME_INVEST_APARTMENT_START = '/api/athome/investment/apartment/start'
API_KEY_ATHOME_INVEST_APARTMENT_DETAIL = '/api/athome/investment/apartment/detail'
API_KEY_ATHOME_MANSION_START = '/api/athome/mansion/start'
API_KEY_ATHOME_MANSION_DETAIL = '/api/athome/mansion/detail'
API_KEY_ATHOME_KODATE_START = '/api/athome/kodate/start'
API_KEY_ATHOME_KODATE_DETAIL = '/api/athome/kodate/detail'
API_KEY_ATHOME_TOCHI_START = '/api/athome/tochi/start'
API_KEY_ATHOME_TOCHI_DETAIL = '/api/athome/tochi/detail'

# Homes
API_KEY_HOMES_INVEST_APARTMENT_START = '/api/homes/investment/apartment/start'
API_KEY_HOMES_INVEST_APARTMENT_DETAIL = '/api/homes/investment/apartment/detail'
API_KEY_HOMES_MANSION_START = '/api/homes/mansion/start'
API_KEY_HOMES_MANSION_DETAIL = '/api/homes/mansion/detail'
API_KEY_HOMES_KODATE_START = '/api/homes/kodate/start'
API_KEY_HOMES_KODATE_DETAIL = '/api/homes/kodate/detail'
API_KEY_HOMES_TOCHI_START = '/api/homes/tochi/start'
API_KEY_HOMES_TOCHI_DETAIL = '/api/homes/tochi/detail'

# Smtrc
API_KEY_SMTRC_MANSION_START = '/api/smtrc/mansion/start'
API_KEY_SMTRC_MANSION_DETAIL = '/api/smtrc/mansion/detail'
API_KEY_SMTRC_KODATE_START = '/api/smtrc/kodate/start'
API_KEY_SMTRC_KODATE_DETAIL = '/api/smtrc/kodate/detail'
API_KEY_SMTRC_TOCHI_START = '/api/smtrc/tochi/start'
API_KEY_SMTRC_TOCHI_DETAIL = '/api/smtrc/tochi/detail'

# Sumai1
API_KEY_SUMAI1_MANSION_START = '/api/sumai1/mansion/start'
API_KEY_SUMAI1_MANSION_DETAIL = '/api/sumai1/mansion/detail'
API_KEY_SUMAI1_KODATE_START = '/api/sumai1/kodate/start'
API_KEY_SUMAI1_KODATE_DETAIL = '/api/sumai1/kodate/detail'
API_KEY_SUMAI1_TOCHI_START = '/api/sumai1/tochi/start'
API_KEY_SUMAI1_TOCHI_DETAIL = '/api/sumai1/tochi/detail'

# Sekisui
API_KEY_SEKISUI_MANSION_START = '/api/sekisui/mansion/start'
API_KEY_SEKISUI_MANSION_DETAIL = '/api/sekisui/mansion/detail'
API_KEY_SEKISUI_KODATE_START = '/api/sekisui/kodate/start'
API_KEY_SEKISUI_KODATE_DETAIL = '/api/sekisui/kodate/detail'
API_KEY_SEKISUI_TOCHI_START = '/api/sekisui/tochi/start'
API_KEY_SEKISUI_TOCHI_DETAIL = '/api/sekisui/tochi/detail'

# Asahi Kasei (afr)
API_KEY_AFR_MANSION_START = '/api/afr/mansion/start'
API_KEY_AFR_MANSION_DETAIL = '/api/afr/mansion/detail'
API_KEY_AFR_KODATE_START = '/api/afr/kodate/start'
API_KEY_AFR_KODATE_DETAIL = '/api/afr/kodate/detail'
API_KEY_AFR_TOCHI_START = '/api/afr/tochi/start'
API_KEY_AFR_TOCHI_DETAIL = '/api/afr/tochi/detail'

# Mizuho (mizuho)
API_KEY_MIZUHO_MANSION_START = '/api/mizuho/mansion/start'
API_KEY_MIZUHO_MANSION_DETAIL = '/api/mizuho/mansion/detail'
API_KEY_MIZUHO_KODATE_START = '/api/mizuho/kodate/start'
API_KEY_MIZUHO_KODATE_DETAIL = '/api/mizuho/kodate/detail'
API_KEY_MIZUHO_TOCHI_START = '/api/mizuho/tochi/start'
API_KEY_MIZUHO_TOCHI_DETAIL = '/api/mizuho/tochi/detail'

# Odakyu (odakyu)
API_KEY_ODAKYU_MANSION_START = '/api/odakyu/mansion/start'
API_KEY_ODAKYU_MANSION_DETAIL = '/api/odakyu/mansion/detail'
API_KEY_ODAKYU_KODATE_START = '/api/odakyu/kodate/start'
API_KEY_ODAKYU_KODATE_DETAIL = '/api/odakyu/kodate/detail'
API_KEY_ODAKYU_TOCHI_START = '/api/odakyu/tochi/start'
API_KEY_ODAKYU_TOCHI_DETAIL = '/api/odakyu/tochi/detail'

# Tokyo Tatemono (totate)
API_KEY_TOTATE_MANSION_START = '/api/totate/mansion/start'
API_KEY_TOTATE_MANSION_DETAIL = '/api/totate/mansion/detail'
API_KEY_TOTATE_KODATE_START = '/api/totate/kodate/start'
API_KEY_TOTATE_KODATE_DETAIL = '/api/totate/kodate/detail'
API_KEY_TOTATE_TOCHI_START = '/api/totate/tochi/start'
API_KEY_TOTATE_TOCHI_DETAIL = '/api/totate/tochi/detail'

# Daiwa House (daiwa)
API_KEY_DAIWA_MANSION_START = '/api/daiwa/mansion/start'
API_KEY_DAIWA_MANSION_DETAIL = '/api/daiwa/mansion/detail'
API_KEY_DAIWA_KODATE_START = '/api/daiwa/kodate/start'
API_KEY_DAIWA_KODATE_DETAIL = '/api/daiwa/kodate/detail'
API_KEY_DAIWA_TOCHI_START = '/api/daiwa/tochi/start'
API_KEY_DAIWA_TOCHI_DETAIL = '/api/daiwa/tochi/detail'

# Sumitomo Forestry Home Service (sumirin)
API_KEY_SUMIRIN_MANSION_START = '/api/sumirin/mansion/start'
API_KEY_SUMIRIN_MANSION_DETAIL = '/api/sumirin/mansion/detail'
API_KEY_SUMIRIN_KODATE_START = '/api/sumirin/kodate/start'
API_KEY_SUMIRIN_KODATE_DETAIL = '/api/sumirin/kodate/detail'
API_KEY_SUMIRIN_TOCHI_START = '/api/sumirin/tochi/start'
API_KEY_SUMIRIN_TOCHI_DETAIL = '/api/sumirin/tochi/detail'
API_KEY_SUMIRIN_INVESTMENT_START = '/api/sumirin/investment/start'
API_KEY_SUMIRIN_INVESTMENT_DETAIL = '/api/sumirin/investment/detail'

# Sekisui Heim (heim)
API_KEY_HEIM_MANSION_START = '/api/heim/mansion/start'
API_KEY_HEIM_MANSION_DETAIL = '/api/heim/mansion/detail'
API_KEY_HEIM_KODATE_START = '/api/heim/kodate/start'
API_KEY_HEIM_KODATE_DETAIL = '/api/heim/kodate/detail'
API_KEY_HEIM_TOCHI_START = '/api/heim/tochi/start'
API_KEY_HEIM_TOCHI_DETAIL = '/api/heim/tochi/detail'

# Panasonic Homes (rearie)
API_KEY_REARIE_MANSION_START = '/api/rearie/mansion/start'
API_KEY_REARIE_MANSION_DETAIL = '/api/rearie/mansion/detail'
API_KEY_REARIE_KODATE_START = '/api/rearie/kodate/start'
API_KEY_REARIE_KODATE_DETAIL = '/api/rearie/kodate/detail'
API_KEY_REARIE_TOCHI_START = '/api/rearie/tochi/start'
API_KEY_REARIE_TOCHI_DETAIL = '/api/rearie/tochi/detail'

# Keio Real Estate (keio)
API_KEY_KEIO_MANSION_START = '/api/keio/mansion/start'
API_KEY_KEIO_MANSION_DETAIL = '/api/keio/mansion/detail'
API_KEY_KEIO_KODATE_START = '/api/keio/kodate/start'
API_KEY_KEIO_KODATE_DETAIL = '/api/keio/kodate/detail'
API_KEY_KEIO_TOCHI_START = '/api/keio/tochi/start'
API_KEY_KEIO_TOCHI_DETAIL = '/api/keio/tochi/detail'

# Seibu (seibu)
API_KEY_SEIBU_MANSION_START = '/api/seibu/mansion/start'
API_KEY_SEIBU_MANSION_DETAIL = '/api/seibu/mansion/detail'
API_KEY_SEIBU_KODATE_START = '/api/seibu/kodate/start'
API_KEY_SEIBU_KODATE_DETAIL = '/api/seibu/kodate/detail'
API_KEY_SEIBU_TOCHI_START = '/api/seibu/tochi/start'
API_KEY_SEIBU_TOCHI_DETAIL = '/api/seibu/tochi/detail'

# Keikyu (keikyu)
API_KEY_KEIKYU_MANSION_START = '/api/keikyu/mansion/start'
API_KEY_KEIKYU_MANSION_DETAIL = '/api/keikyu/mansion/detail'
API_KEY_KEIKYU_KODATE_START = '/api/keikyu/kodate/start'
API_KEY_KEIKYU_KODATE_DETAIL = '/api/keikyu/kodate/detail'
API_KEY_KEIKYU_TOCHI_START = '/api/keikyu/tochi/start'
API_KEY_KEIKYU_TOCHI_DETAIL = '/api/keikyu/tochi/detail'

# Sotetsu (sotetsu)
API_KEY_SOTETSU_MANSION_START = '/api/sotetsu/mansion/start'
API_KEY_SOTETSU_MANSION_DETAIL = '/api/sotetsu/mansion/detail'
API_KEY_SOTETSU_KODATE_START = '/api/sotetsu/kodate/start'
API_KEY_SOTETSU_KODATE_DETAIL = '/api/sotetsu/kodate/detail'
API_KEY_SOTETSU_TOCHI_START = '/api/sotetsu/tochi/start'
API_KEY_SOTETSU_TOCHI_DETAIL = '/api/sotetsu/tochi/detail'

# Keisei (keisei)
API_KEY_KEISEI_MANSION_START = '/api/keisei/mansion/start'
API_KEY_KEISEI_MANSION_DETAIL = '/api/keisei/mansion/detail'
API_KEY_KEISEI_KODATE_START = '/api/keisei/kodate/start'
API_KEY_KEISEI_KODATE_DETAIL = '/api/keisei/kodate/detail'
API_KEY_KEISEI_TOCHI_START = '/api/keisei/tochi/start'
API_KEY_KEISEI_TOCHI_DETAIL = '/api/keisei/tochi/detail'

# Daikyo (daikyo)
API_KEY_DAIKYO_MANSION_START = '/api/daikyo/mansion/start'
API_KEY_DAIKYO_MANSION_DETAIL = '/api/daikyo/mansion/detail'
API_KEY_DAIKYO_KODATE_START = '/api/daikyo/kodate/start'
API_KEY_DAIKYO_KODATE_DETAIL = '/api/daikyo/kodate/detail'
API_KEY_DAIKYO_TOCHI_START = '/api/daikyo/tochi/start'
API_KEY_DAIKYO_TOCHI_DETAIL = '/api/daikyo/tochi/detail'

# Smtrc, Sumai1, Mizuho, Odakyu Investment
API_KEY_SMTRC_INVESTMENT_START = '/api/smtrc/investment/start'
API_KEY_SMTRC_INVESTMENT_DETAIL = '/api/smtrc/investment/detail'
API_KEY_SUMAI1_INVESTMENT_START = '/api/sumai1/investment/start'
API_KEY_SUMAI1_INVESTMENT_DETAIL = '/api/sumai1/investment/detail'
API_KEY_MIZUHO_INVESTMENT_START = '/api/mizuho/investment/start'
API_KEY_MIZUHO_INVESTMENT_DETAIL = '/api/mizuho/investment/detail'
API_KEY_ODAKYU_INVESTMENT_START = '/api/odakyu/investment/start'
API_KEY_ODAKYU_INVESTMENT_DETAIL = '/api/odakyu/investment/detail'


# ------------------------------------------------------------------
# 偏差値（T-score）ベースの上位1%お宝物件判定ヘルパー
# ------------------------------------------------------------------
# 上位1%に相当する偏差値閾値（正規分布: μ+2.326σ → T≒73.3）
T_SCORE_THRESHOLD = 73.3


def get_score_statistics(is_investment: bool) -> tuple[float, float, int]:
    """
    PropertyEvaluationから投資用 / 実需用それぞれのスコア分布の
    平均値(mean)と標準偏差(stddev)、および母集団サイズを返す。

    Returns:
        (mean, stddev, count)
    """
    from django.db.models import Avg, StdDev, Count
    from package.models.evaluation import PropertyEvaluation

    if is_investment:
        qs = PropertyEvaluation.objects.filter(
            total_investment_score__isnull=False,
            duplicate_of__isnull=True,   # 名寄せ重複は除外
            analysis_status="completed"
        )
        agg = qs.aggregate(
            mean=Avg("total_investment_score"),
            stddev=StdDev("total_investment_score"),
            cnt=Count("id")
        )
    else:
        qs = PropertyEvaluation.objects.filter(
            investment_score__isnull=False,
            duplicate_of__isnull=True,
            analysis_status="completed"
        )
        agg = qs.aggregate(
            mean=Avg("investment_score"),
            stddev=StdDev("investment_score"),
            cnt=Count("id")
        )

    mean = agg["mean"] if agg["mean"] is not None else 55.0
    stddev = agg["stddev"] if agg["stddev"] is not None and agg["stddev"] > 0 else 12.0
    count = agg["cnt"] or 0

    # データが極端に少ない場合は安全なデフォルト値を使用
    if count < 10:
        mean = 55.0
        stddev = 12.0

    return float(mean), float(stddev), count


def calculate_t_score(raw_score: float, mean: float, stddev: float) -> float:
    """
    偏差値 T = 50 + 10 × (Score - μ) / σ を算出する。
    """
    if stddev <= 0:
        stddev = 12.0
    return 50.0 + 10.0 * (raw_score - mean) / stddev


def require_eval_record(eval_record, page_url: str):
    """ML評価レコード必須チェック。except Exception 内で assert を使わない (S5779)。"""
    if eval_record is None:
        raise RuntimeError(
            f"ML: eval_record is missing after stage-1 handling for {page_url}"
        )
    return eval_record


class ApiAsyncProcBase(metaclass=ABCMeta):
    USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:61.0) Gecko/20100101 Firefox/61.1'
    headersJson = {
        'Content-Type': 'application/json',
        'User-Agent': USER_AGENT,
    }
    _loop: Optional[asyncio.AbstractEventLoop] = None
    middlewares: list[CrawlerMiddleware] = [LoggingMiddleware()]

    def __init__(self):
        self.parser:ParserBase = self._generateParser()
        self._semaphore = None

    @property
    def semaphore(self):
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(value=self._getPararellLimit())
        return self._semaphore

    @semaphore.setter
    def semaphore(self, value):
        self._semaphore = value

    def _getActiveEventLoop(self):
        try:
            loop = asyncio.get_running_loop()
            self._loop = loop
            return loop
        except RuntimeError:
            if (self._loop is None or self._loop.is_closed()):
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
            return self._loop

    def _generateConnector(self, _loop):
        """Create a bounded aiohttp connector using the default TLS checks."""
        # SSL Context with secure defaults
        ctx = ssl.create_default_context()
        return aiohttp.TCPConnector(loop=_loop, limit=TCP_CONNECTOR_LIMIT, ssl=ctx)

    def _generateTimeout(self):
        _total = self._getTimeOutSecond()
        return aiohttp.ClientTimeout(total=_total)

    def _getUrl(self):
        if os.getenv('IS_CLOUD', ''):
            return "https://us-central1-sumifu.cloudfunctions.net"
        return "http://127.0.0.1:8000"

    def get_seed_urls(self) -> list:
        """Return crawl seed URLs for smoke/guarantee tests (urlList or SEED_URL)."""
        url_list = getattr(self, "urlList", None)
        if url_list:
            return list(url_list)
        seed = getattr(type(self), "SEED_URL", None)
        if isinstance(seed, str) and seed:
            return [seed]
        if isinstance(seed, (list, tuple)):
            return list(seed)
        return []

    def _getApiUrl(self):
        api_url = self._getUrl() + (self._getApiKey() or '')
        return api_url

    async def _fetchWithEachSession(self, detail_url, api_url, loop):
        await self.semaphore.acquire()
        try:
            async with aiohttp.ClientSession(headers=header, connector=self._generateConnector(self._getActiveEventLoop()), timeout=self._generateTimeout()) as _session:
                try:
                    return await self._fetch(_session, detail_url, api_url, loop, retry_times=0)
                finally:
                    if _session is not None:
                        await _session.close()
        finally:
            self.semaphore.release()

    async def _apply_middlewares_request(self, request_context: Dict[str, Any]) -> Optional[Any]:
        for mw in self.middlewares:
            result = await mw.process_request(request_context)
            if result is not None:
                return result
        return None

    async def _apply_middlewares_response(self, response_context: Dict[str, Any]) -> Dict[str, Any]:
        for mw in reversed(self.middlewares):
            response_context = await mw.process_response(response_context)
        return response_context

    def _handle_local_execution(self, api_url, detail_url):
        if os.getenv('IS_CLOUD', ''):
            return None

        from package.api.registry import ApiRegistry
        from urllib.parse import urlparse
        import threading

        parsed = urlparse(api_url)
        path = parsed.path
        target_class = ApiRegistry.get(path)
        
        if not target_class:
            logging.warning("No registry found for %s, falling back to HTTP", path)
            return None

        logging.debug("Local routing: %s -> %s", path, target_class.__name__)
        
        def run_in_new_loop():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                target_class().main(detail_url)
            finally:
                try:
                    from django.db import close_old_connections, connections
                    close_old_connections()
                    connections.close_all()
                except Exception:
                    pass
                new_loop.close()

        t = threading.Thread(target=run_in_new_loop)
        t.start()
        while t.is_alive():
            t.join(1.0)
            if os.path.exists("stop.flag"):
                print("stop.flag found, forcing exit...", flush=True)
                from django.db import close_old_connections
                close_old_connections()
                os._exit(0)
        
        return detail_url, 200, "LocalSync"

    async def _fetch(self, session: aiohttp.ClientSession, detail_url, api_url, loop, retry_times: int):
        if os.path.exists("stop.flag"):
            logging.info("stop.flag found at start of _fetch, aborting: " + detail_url)
            return detail_url, 200, "Aborted"

        # Middleware request hook
        request_context = {
            'method': 'POST',
            'url': api_url,
            'detailUrl': detail_url,
            'retryTimes': retry_times
        }
        mw_result = await self._apply_middlewares_request(request_context)
        if mw_result is not None:
            return mw_result

        _timeout = aiohttp.ClientTimeout(total=3.0) 

        local_result = self._handle_local_execution(api_url, detail_url)
        if local_result is not None:
            return local_result

        post_json_data = json.dumps(
            '{"url":"' + detail_url + '"}').encode("utf-8")
        try:
            response: aiohttp.ClientResponse = await session.post(api_url, headers=self.headersJson, data=post_json_data, timeout=_timeout)
        except aiohttp.client_exceptions.ClientConnectorError:
            if retry_times > 0:
                await asyncio.sleep(10)
                return await self._fetch(session, detail_url, api_url, loop, retry_times + 1)
            logging.exception("ClientConnectorError: %s", detail_url)
            raise
        except aiohttp.client_exceptions.ServerDisconnectedError:
            if retry_times > 0:
                await asyncio.sleep(10)
                return await self._fetch(session, detail_url, api_url, loop, retry_times + 1)
            logging.exception("ServerDisconnectedError: %s", detail_url)
            raise
        except (asyncio.TimeoutError, TimeoutError):
            # Fire-and-Forget Success Path
            logging.info("Fire and forget - Timeout (assumed success): " + detail_url)
            return detail_url, 200, "FireAndForget"
        except Exception:
            logging.exception("fetch error: %s", detail_url)
            raise
        return await self._proc_response(detail_url, response)

    async def _proc_response(self, url, response:aiohttp.ClientResponse):
        response_context = {
            'url': url,
            'status': response.status,
            'text': await response.text(),
            'response': response
        }
        # Middleware response hook
        response_context = await self._apply_middlewares_response(response_context)
        
        if response_context.get('should_retry'):
            # Note: This simple implementation might need session management refinement
            # but follows the proposed structure.
            pass

        return url, response_context['status'], response_context['text']

    async def _run(self, _url):
        _loop = self._getActiveEventLoop()
        
        _timeout: aiohttp.ClientTimeout = self._generateTimeout()
        _connector: aiohttp.TCPConnector = self._generateConnector(_loop)
        url_list = []
        try:
            async with aiohttp.ClientSession(headers=header, connector=_connector, timeout=_timeout) as session:
                try:
                    url_list = await self._treatPage(session, self._getTreatPageArg())
                except Exception as e:
                    logging.error(f"Error in _run/_treatPage for {_url}: {e}")
                    raise e
                finally:
                    if session is not None:
                        await session.close()
        finally:
            if _connector is not None:
                await _connector.close()

        return await self._callApi(url_list)

    def _afterRunProc(self, run_result):
        # Optional lifecycle hook invoked after execution in subclasses
        pass

    def main(self, url):
        self.url = url
        loop: Optional[asyncio.AbstractEventLoop] = None
        run_result = None
        try:
            try:
                loop = self._getActiveEventLoop()
                task = loop.create_task(self._run(url))
                res = loop.run_until_complete(task)
                run_result = res if isinstance(res, list) else [res]
            except asyncio.exceptions.TimeoutError:
                if loop and loop.is_running():
                    loop.stop()
                if loop:
                    task = loop.create_task(self._run(url))
                    res = loop.run_until_complete(task)
                    run_result = res if isinstance(res, list) else [res]
        finally:
            if loop and loop.is_running():
                loop.stop()
            if loop and not loop.is_closed():
                loop.close()
        self._afterRunProc(run_result)
        return "finish", 200

    async def _save_error_html_by_url(self, url, model_name, reason="Unknown Error"):
        """Save HTML of failed property/page for debugging"""
        try:
            await asyncio.to_thread(_sync_save_error_html_by_url, url, model_name, reason)
        except Exception:
            logging.exception("Failed to save error HTML for %s", url)

    def _getPararellLimit(self):
        pararell_limit = self._getLocalPararellLimit()
        if os.getenv('IS_CLOUD', ''):
            custom_cloud_limit = os.getenv('CLOUD_DETAIL_CONCURRENCY')
            if custom_cloud_limit and custom_cloud_limit.isdigit():
                return int(custom_cloud_limit)
            pararell_limit = self._getCloudPararellLimit()
        return pararell_limit

    @abstractmethod
    def _generateParser(self)->ParserBase:
        pass

    @abstractmethod
    def _getLocalPararellLimit(self)->int:
        pass

    @abstractmethod
    def _getCloudPararellLimit(self)->int:
        pass

    @abstractmethod
    def _getTimeOutSecond(self)->int:
        pass

    @abstractmethod
    def _getApiKey(self):
        pass

    @abstractmethod
    async def _treatPage(self, _session, *arg):
        pass

    @abstractmethod
    def _getTreatPageArg(self):
        pass

    @abstractmethod
    async def _callApi(self, url_list):
        pass


# urlを受け取って、そのページから更にドリルダウン先を呼び出す場合の基底クラス
class ParseMiddlePageAsyncBase(ApiAsyncProcBase):

    async def _treatPage(self, _session, *arg):
        try:
            if self._isBsMiddlePage():
                 response = await self.parser.getResponseBs(_session, self.url, self.parser.getCharset())
            else:
                 response = await self.parser.getResponse(_session, self.url, self.parser.getCharset())
        except Exception as e:
            logging.error(f"Failed to fetch middle page: {self.url}")
            await self._save_error_html_by_url(self.url, self.__class__.__name__, f"Middle Page Fetch Failure: {str(e)}")
            raise e

        detail_url_list = []
        try:
            parser_func = self._getParserFunc()
            async for detail_url in parser_func(response):
                detail_url_list.append(detail_url)
        except Exception as e:
            logging.error(f"Failed to parse middle page: {self.url}")
            await self._save_error_html_by_url(self.url, self.__class__.__name__, f"Middle Page Parse Failure: {str(e)}")
            raise e
        finally:
            # 次のページを開く
            parser_next_func = self._getNextPageParserFunc()
            if parser_next_func is not None:
                next_page_url = await parser_next_func(response)
                if len(next_page_url) > 0:
                    async with aiohttp.ClientSession(headers=header, connector=self._generateConnector(self._getActiveEventLoop()), timeout=self._generateTimeout()) as another_session:
                        try:
                            await self._fetch(session=another_session, detail_url=next_page_url, api_url=self._getUrl(
                            ) + (self._getNextPageApiKey() or ''), loop=self._getActiveEventLoop(), retry_times=0)
                        except Exception as npe:
                            logging.warning(f"Failed to fetch next page {next_page_url}: {npe}")

        return detail_url_list

    def _getTreatPageArg(self):
        return

    async def _callApi(self, url_list):
        if not url_list:
            return []

        model_class = None
        if hasattr(self, "parser") and self.parser:
            try:
                entity = self.parser.createEntity()
                if entity is not None:
                    model_class = entity.__class__
            except Exception:
                model_class = None

        to_fetch = url_list
        if model_class is not None:
            ttl_days = int(os.getenv("DIFFERENTIAL_TTL_DAYS", "7"))
            force_full = os.getenv("FORCE_FULL_CRAWL", "false").lower() in ("true", "1")
            enabled = os.getenv("ENABLE_DIFFERENTIAL_CRAWL", "true").lower() in ("true", "1")
            to_fetch, _ = await filter_differential_items(
                items=url_list,
                model_class=model_class,
                ttl_days=ttl_days,
                force_full=force_full,
                enabled=enabled,
            )

        tasks = []
        loop = self._getActiveEventLoop()
        for detail_item in to_fetch:
            if isinstance(detail_item, ListItem):
                detail_url = detail_item.url
            elif isinstance(detail_item, (tuple, list)):
                detail_url = detail_item[0]
            else:
                detail_url = str(detail_item)

            colo = self._fetchWithEachSession(
                detail_url, self._getApiUrl(), loop)
            task = asyncio.create_task(colo)
            tasks.append(task)

        responses = await asyncio.gather(*tasks)
        return responses

    @abstractmethod
    def _getParserFunc(self) -> Any:
        pass

    def _getNextPageParserFunc(self):
        return None

    def _getNextPageApiKey(self):
        return None

    def _isBsMiddlePage(self):
        return False


# 物件詳細ページのurlを受け取って、そのページ内の物件情報を取得、保存する場合の基底クラス
class ParseDetailPageAsyncBase(ApiAsyncProcBase):

    async def _run(self, _url):
        """詳細ページURLを受け取り、適切なパーサーでパース・保存を実行"""
        # Update parser dynamically based on current URL
        try:
            from package.utils.url_router import UrlRouter
            self.parser = UrlRouter.create_parser(_url) or self._generateParser()
        except Exception:
            self.parser = self._generateParser()
        _loop = self._getActiveEventLoop()
        _timeout:int = self._generateTimeout()
        _connector = self._generateConnector(_loop)
        async with aiohttp.ClientSession(headers=header, connector=_connector, timeout=_timeout) as session:
            try:
                item = await self._treatPage(session, self._getTreatPageArg())
            except Exception as e:
                logging.exception("Error during _treatPage: %s", e)
                item = None
            finally:
                if session is not None:
                    await session.close()
                if _connector is not None:
                    await _connector.close()
        return item

    async def _getContent(self, session, url):
        max_retries = 3
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                async with session.get(url) as response:
                    status_code = response.status
                    logging.info(f"Response status: {status_code} for URL: {url}")
                    if status_code != 200:
                        raise RuntimeError(f"HTTP Error: {status_code} for URL: {url}")
                    return await response.read()
            except (aiohttp.client_exceptions.ClientConnectorError, 
                    aiohttp.client_exceptions.ServerDisconnectedError) as e:
                retry_count += 1
                if retry_count > max_retries:
                    logging.exception("Max retries (%s) exceeded for %s", max_retries, url)
                    raise
                
                # Exponential backoff: 2s, 4s, 8s
                wait_time = 2 ** retry_count
                logging.warning(f"Connection error for {url}, retry {retry_count}/{max_retries} after {wait_time}s")
                logging.warning(f"Exception type: {type(e).__name__}, Details: {str(e)}")
                await asyncio.sleep(wait_time)
            except Exception as e:
                logging.exception("Unexpected error getting content from %s: %s", url, e)
                raise

    async def _treatPage(self, _session, *arg):

        async def get_item():
            item = None
            _connector = self._generateConnector(self._getActiveEventLoop())
            await self.semaphore.acquire()
            try:
                # with await self.semaphore:
                async with aiohttp.ClientSession(headers=header, connector=self._generateConnector(self._getActiveEventLoop()), timeout=self._generateTimeout()) as dtl_session:
                    try:
                        item = await self.parser.parsePropertyDetailPage(session=dtl_session, url=self.url)

                    except Exception as e:
                        logging.exception("exception get item for URL: %s Details: %s", self.url, e)
                        raise
                    finally:
                        if dtl_session is not None:
                            await dtl_session.close()
                        if _connector is not None:
                            await _connector.close()
            finally:
                self.semaphore.release()
            return item

        retry = False
        item = None
        is_skipped_property = False
        try:
            item = await get_item()
        except (LoadPropertyPageException, TimeoutError, ReadPropertyNameException):
            retry = True
        except (SkipPropertyException, ListingEndedException) as e:
            logging.info(f"Skipping property (Expected / Listing Ended): {type(e).__name__} for URL: {self.url}")
            item = None
            is_skipped_property = True


        except Exception as e:
            logging.error(f"get item exception for URL: {self.url}", exc_info=e)
        if retry:
            logging.debug("get item retry")
            try:
                item = await get_item()
            except (LoadPropertyPageException, TimeoutError, ReadPropertyNameException) as e:
                logging.error(f"get item exception (retry failed) for URL: {self.url}: {e}", exc_info=e)
                await self._save_error_html_by_url(self.url, self.parser.createEntity().__class__.__name__, "Detail Page Retry Failure")
                CrawlerReporter.failure(self.url, self.parser.createEntity().__class__.__name__, f"Retry Failed: {str(e)}")

        if item is not None:
            current_time = datetime.datetime.now()
            current_day = datetime.date.today()

            # Enforce 1 property = 1 record and record price revision history
            item.pageUrl = UrlMatcher.normalize(item.pageUrl)
            model_class = item.__class__
            existing_record = None
            try:
                def get_existing():
                    return UrlMatcher.find_match_in_queryset(
                        model_class.objects, "pageUrl", item.pageUrl
                    )
                existing_record = await sync_to_async(get_existing)()
            except Exception as e:
                logging.warning(f"Failed to check existing record for {item.pageUrl}: {e}")

            if existing_record:
                item.id = existing_record.id
                item._state.adding = False
                item.inputDate = existing_record.inputDate or current_day
                item.inputDateTime = existing_record.inputDateTime or current_time
                item.updateDateTime = current_time

                old_p = existing_record.price
                new_p = item.price
                if old_p is not None and new_p is not None and old_p != new_p:
                    model_name = model_class.__name__
                    company = "unknown"
                    for c in ["mitsui", "sumifu", "tokyu", "nomura", "misawa", "smtrc", "sumai1", "mizuho", "odakyu", "afr", "sekisui", "daiwa", "totate", "athome", "homes", "seibu", "keikyu", "sotetsu", "keisei", "daikyo", "rearie", "heim", "sumirin", "keio"]:
                        if model_name.lower().startswith(c):
                            company = c
                            break
                    property_type = PropertyTypeDetector.detect_from_object(item)
                    try:
                        def create_price_history():
                            PropertyPriceHistory.objects.create(
                                property_url=item.pageUrl,
                                company=company,
                                property_type=property_type,
                                old_price=old_p,
                                new_price=new_p,
                                price_diff=new_p - old_p,
                            )
                        await sync_to_async(create_price_history)()
                        logging.info(f"[Price Revision] {item.pageUrl}: {old_p} -> {new_p} (diff: {new_p - old_p:+d})")
                    except Exception as he:
                        logging.warning(f"Failed to record price history for {item.pageUrl}: {he}")
            else:
                item.inputDateTime = current_time
                item.inputDate = current_day
                item.updateDateTime = current_time

            try:
                logging.debug(f"Attempting to save item (Single): {item.propertyName} ({item.pageUrl})")
                await sync_to_async(item.save)()
                logging.debug(f"Successfully saved item (Single): {item.propertyName} ({item.pageUrl})")
                
                # ----------------------------------------------------
                # 2段階スクリーニング統合処理 (B案: クロール中の同期評価はデフォルト非有効化)
                # ----------------------------------------------------
                enable_inline_ml = os.getenv("ENABLE_INLINE_ML_EVALUATION", "false").lower() in ("true", "1")
                if not enable_inline_ml:
                    logging.debug(f"ML: Inline ML evaluation disabled. Property {item.pageUrl} saved for bulk evaluation.")
                    return item

                try:
                    # 機械学習・画像解析モジュールのインポート
                    from package.ml.predict import predict_first_stage, predict_second_stage

                    from package.models.evaluation import PropertyEvaluation, PropertyImage
                    from package.utils.image_handler import extract_images_from_soup, clean_images, analyze_property_images_with_gemini, check_api_budget_cap
                    from django.utils import timezone
                    
                    # 1. 不動産会社名と物件種別の特定
                    model_name = item.__class__.__name__
                    company = "unknown"
                    for c in ["mitsui", "sumifu", "tokyu", "nomura", "misawa", "smtrc", "sumai1", "mizuho", "odakyu", "afr", "sekisui", "daiwa", "totate", "athome", "homes", "seibu", "keikyu", "sotetsu", "keisei", "daikyo", "rearie", "heim", "sumirin", "keio"]:
                        if model_name.lower().startswith(c):
                            company = c
                            break
                    property_type = PropertyTypeDetector.detect_from_object(item)
                    
                    # すでに価格推定（一次・二次予測、または一次不合格）が完了している場合は全体をスキップ
                    def get_existing_eval():
                        return UrlMatcher.find_match_in_queryset(
                            PropertyEvaluation.objects.order_by("-id"),
                            "property_url",
                            item.pageUrl,
                        )
                    existing_eval = await sync_to_async(get_existing_eval)()
                    
                    price_stage1 = None
                    is_passed = False
                    eval_record = None
                    asking_price = (float(item.price) / 10000.0) if item.price else 0.0
                    
                    if existing_eval and existing_eval.first_stage_predicted_price is not None:
                        # 二次予測まで終わっているか、または一次不合格で終了している場合
                        if existing_eval.second_stage_predicted_price is not None or not existing_eval.is_first_stage_passed:
                            logging.info(f"ML: Skipping already fully evaluated property: {item.pageUrl}")
                            return item
                        else:
                            # 一次合格しているが二次未完了の場合、一次予測結果を再利用して後半の画像解析へ進む
                            price_stage1 = float(existing_eval.first_stage_predicted_price)
                            is_passed = existing_eval.is_first_stage_passed
                            eval_record = existing_eval
                            logging.info(f"ML: Reusing Stage 1 result for incomplete Stage 2: {item.pageUrl} ({price_stage1}万円)")
                    
                    # 新規または一次予測未実行の場合のみ一次予測を実行
                    if price_stage1 is None:
                        # 2. 一次理論価格予測の実行
                        price_stage1 = await sync_to_async(predict_first_stage)(item)
                        
                        # 3. 一次合格判定（理論価格が販売価格以上） - 販売価格（円）を万円単位にスケール変換して比較
                        if price_stage1 > 0 and asking_price > 0 and price_stage1 >= asking_price:
                            is_passed = True
                            
                        chidai_val = getattr(item, "chidai", None)
                        if chidai_val is None and getattr(item, "chidaiStr", None):
                            chidai_val = parse_chidai(item.chidaiStr)
                        monthly_rent = int(chidai_val) if chidai_val and int(chidai_val) > 0 else None
                        liability = Decimal(int((monthly_rent * 12.0) / 10000.0 / 0.05)) if monthly_rent else None

                        # 4. PropertyEvaluation レコードの作成/更新
                        eval_record, created = await sync_to_async(PropertyEvaluation.objects.update_or_create)(
                            property_url=item.pageUrl,
                            defaults={
                                "company": company,
                                "property_type": property_type,
                                "property_id": item.id,
                                "first_stage_predicted_price": price_stage1,
                                "is_first_stage_passed": is_passed,
                                "analysis_status": "pending",
                                "monthly_land_rent": monthly_rent,
                                "land_rent_liability": liability
                            }
                        )
                    
                    eval_record = require_eval_record(eval_record, item.pageUrl)
                    
                    # 名寄せロジックによる重複検出
                    from package.utils.deduplication import find_duplicate_property
                    duplicate_parent = await sync_to_async(find_duplicate_property)(eval_record)
                    if duplicate_parent:
                        eval_record.duplicate_of = duplicate_parent
                        # 重複物件のため、親物件が既に通知済み、または名寄せにより通知済み扱いとする
                        eval_record.is_slack_notified = True
                        await sync_to_async(eval_record.save)()
                        logging.info(f"Deduplication: Property {item.pageUrl} is linked as a duplicate of {duplicate_parent.property_url}. Skipping Slack notification.")
                    
                    # 投資用物件の場合は、一次合格の有無にかかわらず、
                    # まずテキスト情報のみから詳細な収支・融資・総合投資スコアの評価を実行
                    if PropertyTypeDetector.is_investment(property_type):
                        from package.ml.investment_evaluator import evaluate_investment_property
                        eval_record = await sync_to_async(evaluate_investment_property)(item, eval_record)
                        await sync_to_async(eval_record.save)()
                    
                    logging.info(f"ML: Stage 1 predicted for {item.propertyName} ({item.pageUrl}) = {price_stage1}万円 (Asking: {asking_price}万円, Passed: {is_passed})")
                    
                    # 一次合格の場合のみ、詳細画像の取得と画像解析の実行
                    if is_passed:
                        soup = getattr(item, "_soup", None)
                        raw_images = []
                        if soup:
                            # BeautifulSoup から画像をスクレイピング
                            raw_images = extract_images_from_soup(soup, item.pageUrl)
                            
                        cleaned_images = clean_images(raw_images)
                        
                        if cleaned_images:
                            # 予算上限 (1日200件) チェック
                            if await sync_to_async(check_api_budget_cap)():
                                logging.info(f"ML: Executing Gemini image analysis for {item.propertyName}...")
                                # 解析ステータスを処理中に変更
                                eval_record.analysis_status = "processing"
                                await sync_to_async(eval_record.save)()
                                
                                # Gemini API で画像スコア・物件評価メタデータを算出
                                analysis_res = await sync_to_async(analyze_property_images_with_gemini)(cleaned_images)
                                interior_score = analysis_res['interior_score']
                                layout_score = analysis_res['layout_score']
                                
                                # 二次理論価格予測の実行
                                price_stage2 = await sync_to_async(predict_second_stage)(item, interior_score, layout_score)
                                
                                # 投資価値スコアの算出 (割安度×50。最大100)
                                if asking_price > 0:
                                    ratio = price_stage2 / asking_price
                                    investment_score = min(100.0, max(0.0, ratio * 50.0))
                                else:
                                    investment_score = 0.0
                                    
                                # 結果を更新
                                eval_record.second_stage_predicted_price = price_stage2
                                eval_record.interior_score = interior_score
                                eval_record.layout_score = layout_score
                                eval_record.investment_score = investment_score
                                eval_record.plot_shape_type = analysis_res['plot_shape_type']
                                eval_record.plot_shape_description = analysis_res['plot_shape_description']
                                eval_record.maintenance_score = analysis_res['maintenance_score']
                                eval_record.maintenance_comment = analysis_res['maintenance_comment']
                                eval_record.analysis_status = "completed"
                                eval_record.analyzed_at = timezone.now()
                                
                                # 投資用物件の場合は、詳細な収支・融資・総合投資スコアの評価を実行
                                if PropertyTypeDetector.is_investment(property_type):
                                    eval_record = await sync_to_async(evaluate_investment_property)(item, eval_record)
                                
                                await sync_to_async(eval_record.save)()
                                
                                # 総合投資スコア（投資用以外は従来のinvestment_scoreを使用）
                                final_score = eval_record.total_investment_score if PropertyTypeDetector.is_investment(property_type) else eval_record.investment_score
                                
                                logging.info(f"ML: Stage 2 prediction for {item.propertyName}: {price_stage2}万円 (Interior: {interior_score}, Layout: {layout_score}, Score: {final_score or 0.0:.1f})")
                                
                                # クレンジング画像情報を保存
                                for idx, img in enumerate(cleaned_images):
                                    try:
                                        resp = await sync_to_async(requests.get)(img["url"], timeout=10)
                                        if resp.status_code == 200:
                                            img_bytes = resp.content
                                            ext = ".jpg"
                                            clean_url = img["url"].split('?')[0].lower()
                                            if clean_url.endswith(".png"):
                                                ext = ".png"
                                            elif clean_url.endswith(".webp"):
                                                ext = ".webp"
                                                
                                            object_key = f"{property_type}/{eval_record.id}_{idx}_{uuid.uuid4().hex}{ext}"
                                            content_type = f"image/{ext[1:]}"
                                            if ext == ".jpg":
                                                content_type = "image/jpeg"
                                                
                                            storage_mgr = get_storage_manager()
                                            storage_url = storage_mgr.upload_image_bytes(img_bytes, object_key, content_type)
                                            
                                            await sync_to_async(PropertyImage.objects.create)(
                                                evaluation=eval_record,
                                                image_url=storage_url,
                                                local_path=object_key,
                                                category=img["category"],
                                                is_cleaned=True
                                            )
                                        else:
                                            await sync_to_async(PropertyImage.objects.create)(
                                                evaluation=eval_record,
                                                image_url=img["url"],
                                                local_path=None,
                                                category=img["category"],
                                                is_cleaned=True
                                            )
                                    except Exception as img_err:
                                        logging.error(f"Failed to upload image to MinIO for {img['url']}: {img_err}")
                                        try:
                                            await sync_to_async(PropertyImage.objects.create)(
                                                evaluation=eval_record,
                                                image_url=img["url"],
                                                local_path=None,
                                                category=img["category"],
                                                is_cleaned=True
                                            )
                                        except Exception:
                                            pass
                                    
                                # 偏差値（T-score）ベースの上位1%判定
                                is_investment = "investment" in property_type
                                mean, stddev, pop_count = await sync_to_async(get_score_statistics)(is_investment)
                                t_score = calculate_t_score(final_score, mean, stddev) if final_score else 0.0
                                
                                logging.info(
                                    f"T-score: {t_score:.1f} (raw={final_score or 0.0:.1f}, "
                                    f"μ={mean:.1f}, σ={stddev:.1f}, N={pop_count}, threshold={T_SCORE_THRESHOLD})"
                                )
                                
                                if t_score >= T_SCORE_THRESHOLD and not eval_record.is_slack_notified:
                                    # 通知前のURL生存性（稼働状況）チェック
                                    from package.utils.slack import send_slack_message, verify_url_active
                                    url_active = await verify_url_active(item.pageUrl)
                                    
                                    if url_active:
                                        # 会社名・物件種別の日本語変換
                                        company_name = {
                                            "mitsui": "三井のリハウス",
                                            "sumifu": "住友不動産販売",
                                            "tokyu": "東急リバブル",
                                            "nomura": "野村の仲介+",
                                            "misawa": "ミサワホーム不動産",
                                            "athome": "アットホーム",
                                            "homes": "LIFULL HOME'S",
                                            "smtrc": "三井住友トラスト不動産",
                                            "sumai1": "三菱UFJ不動産販売",
                                            "mizuho": "みずほ不動産販売",
                                            "odakyu": "小田急不動産",
                                            "afr": "旭化成不動産レジデンス",
                                            "sekisui": "積水ハウス",
                                            "daiwa": "大和ハウス",
                                            "totate": "東京建物",
                                            "seibu": "西武不動産",
                                            "keikyu": "京急不動産",
                                            "sotetsu": "相鉄不動産販売",
                                            "keisei": "京成不動産",
                                            "daikyo": "大京穴吹不動産",
                                            "rearie": "パナソニック ホームズ不動産",
                                            "heim": "セキスイハイム不動産",
                                            "sumirin": "住友林業ホームサービス",
                                            "keio": "京王不動産"
                                        }.get(company, company)
                                        
                                        type_name = {
                                            "mansion": "中古マンション",
                                            "kodate": "戸建て",
                                            "tochi": "土地",
                                            "investment": "投資用物件"
                                        }.get(property_type, property_type)
                                        
                                        asking_price_man = int(asking_price) if asking_price > 0 else 0
                                        
                                        plot_shape_label = {
                                            "regular": "整形地 (良好)",
                                            "irregular": "不整形地/変形地 (建物の再建築効率低下の懸念あり)",
                                            "flagpole": "旗竿地/敷延 (再建築・アクセス制限の懸念あり)",
                                            "unknown": "判定不能"
                                        }.get(eval_record.plot_shape_type, "判定不能")

                                        if is_investment:
                                            msg = (
                                                f"🏆 [TOP 1% ALERT] 上位1%のお宝物件を検出しました！\n"
                                                f"物件種別: {type_name} ({company_name})\n"
                                                f"物件名: {item.propertyName}\n"
                                                f"価格: {asking_price_man}万円 (理論価格: {price_stage2}万円, 積算価格: {eval_record.estimated_sekisan_price}万円)\n"
                                                f"キャッシュフロー: {eval_record.cash_flow}万円/年, DSCR: {float(eval_record.dscr):.2f}\n"
                                                f"偏差値: {t_score:.1f} (スコア: {final_score:.1f}, 母集団: {pop_count}件)\n"
                                                f"土地の形状: {plot_shape_label}\n"
                                                f"  詳細: {eval_record.plot_shape_description or '画像なし/記述なし'}\n"
                                                f"建物メンテナンス状態: {eval_record.maintenance_score or 'N/A'} / 5.0\n"
                                                f"  評価: {eval_record.maintenance_comment or '画像なし/記述なし'}\n"
                                                f"URL: {item.pageUrl}"
                                            )
                                        else:
                                            msg = (
                                                f"🏆 [TOP 1% ALERT] 上位1%のお宝物件を検出しました！\n"
                                                f"物件種別: {type_name} ({company_name})\n"
                                                f"物件名: {item.propertyName}\n"
                                                f"価格: {asking_price_man}万円 (理論価格: {price_stage2}万円, 投資スコア: {final_score:.1f})\n"
                                                f"偏差値: {t_score:.1f} (母集団: {pop_count}件)\n"
                                                f"土地の形状: {plot_shape_label}\n"
                                                f"  詳細: {eval_record.plot_shape_description or '画像なし/記述なし'}\n"
                                                f"建物メンテナンス状態: {eval_record.maintenance_score or 'N/A'} / 5.0\n"
                                                f"  評価: {eval_record.maintenance_comment or '画像なし/記述なし'}\n"
                                                f"URL: {item.pageUrl}"
                                            )
                                        
                                        logging.info(msg)
                                        
                                        # 物件種別ごとのアラートチャンネル定義 (お宝物件用: SLACK_RECOMMEND_*)
                                        alert_channel = os.getenv("SLACK_CHANNEL_ID")
                                        if property_type == "mansion":
                                            alert_channel = os.getenv("SLACK_RECOMMEND_MANSION", "C0BJ87V7BM0")
                                        elif property_type == "kodate":
                                            alert_channel = os.getenv("SLACK_RECOMMEND_KODATE", "C0BJ87VEV0S")
                                        elif property_type == "tochi":
                                            alert_channel = os.getenv("SLACK_RECOMMEND_TOCHI", "C0BJA5D1GMP")
                                        elif property_type in ["invest_apartment", "apartment"]:
                                            alert_channel = os.getenv("SLACK_RECOMMEND_INVEST_APARTMENT", "C0BJBUMSYGL")
                                        elif property_type == "invest_kodate":
                                            alert_channel = os.getenv("SLACK_RECOMMEND_INVEST_KODATE", "C0BJ20EMQ67")

                                        # Slack送信を実行し、成否を明示的に判定・ログ記録する
                                        if alert_channel:
                                            success = await send_slack_message(msg, channel=alert_channel)
                                        else:
                                            success = False
                                            logging.error("Slack alert_channel is not defined.")
                                        if success:
                                            eval_record.is_slack_notified = True
                                            await sync_to_async(eval_record.save)()
                                        else:
                                            logging.error(f"❌ [SLACK ERROR] Failed to send Slack alert for {item.propertyName} ({item.pageUrl})")
                                    else:
                                        logging.warning(f"⚠️ [SLACK SKIPPED] Slack notification skipped for {item.propertyName} due to inactive URL: {item.pageUrl}")
                            else:
                                eval_record.analysis_status = "skipped_by_budget"
                                await sync_to_async(eval_record.save)()
                                logging.warning(f"ML: Skipped Gemini analysis for {item.propertyName} due to daily budget cap.")
                        else:
                            logging.info(f"ML: No valid property images found for {item.propertyName}.")
                            
                except Exception as ex:
                    logging.exception("ML/Image screening error for %s: %s", item.pageUrl, ex)
                # ----------------------------------------------------
                
                # Global Limit Check for Verification
                global GLOBAL_SAVE_COUNT
                try:
                    GLOBAL_SAVE_COUNT += 1
                except NameError:
                    GLOBAL_SAVE_COUNT = 1
                
                limit = int(os.getenv("CRAWLER_LIMIT", 0))
                if limit > 0:
                    logging.info(f"Global Save Count: {GLOBAL_SAVE_COUNT}/{limit}")
                    if GLOBAL_SAVE_COUNT >= limit:
                        logging.info(f"Hit limit {limit}. Exiting...")
                        os._exit(0)
                        
            except Exception as e:
                logging.exception("Failed to save item (Single): %s for URL: %s", e, item.pageUrl)
            await sync_to_async(CrawlerReporter.success)(self.url, item.__class__.__name__)
        elif is_skipped_property:
            logging.info(f"Skipped property processing (Lifecycle / Filtered) for URL: {self.url}")
        else:
            await sync_to_async(CrawlerReporter.failure)(self.url, self.parser.createEntity().__class__.__name__, "Item is None")

        return item


    def _getTreatPageArg(self):
        return

    async def _callApi(self, url_list):
        return

    async def _save_error_html_by_url(self, url, model_name, reason="Live Fetch Failure/Parsing Error"):
        """Save HTML of failed property for debugging when we only have the URL"""
        try:
            await asyncio.to_thread(_sync_save_error_html_by_url, url, model_name, reason)
        except Exception:
            logging.exception("Failed to save error HTML by URL")

    def _save_error_html_record(self, item):
        """Save HTML of failed property for debugging"""
        try:
            url = getattr(item, 'pageUrl', '')
            if url:
                model_name = item.__class__.__name__
                prop_name = getattr(item, 'propertyName', 'UNKNOWN')
                _sync_save_error_html_by_url(url, model_name, f"Property Name: {prop_name}")
        except Exception:
            logging.exception("Failed to save error HTML")

    def _save_item_record(self, item):
        try:
            item.full_clean()
            logging.info("Attempting to save item (Batch): %s (%s)", item.propertyName, item.pageUrl)
            item.save(False, False, None, None)
            logging.info("Successfully saved item (Batch): %s:%s", item.propertyName, item.pageUrl)
        except ValidationError as ve:
            msg = f"Validation failed for property: {getattr(item, 'pageUrl', 'UNKNOWN_URL')}\n"
            msg += f"Property name: {getattr(item, 'propertyName', 'UNKNOWN')}\n"
            missing_fields = [
                f"{field} (value: {getattr(item, field, 'N/A')}): {', '.join(errors)}"
                for field, errors in ve.message_dict.items()
            ]
            msg += f"Missing/invalid fields: {'; '.join(missing_fields)}"
            logging.warning(msg)
            logging.warning("Skipping save for this property due to validation errors.")
            self._save_error_html_record(item)

    def _save_item_with_retry(self, item, max_retries: int = 3):
        for attempt in range(max_retries):
            try:
                self._save_item_record(item)
                close_old_connections()
                return
            except OperationalError as e:
                if attempt < max_retries - 1:
                    logging.warning("Database error (attempt %d/%d): %s. Retrying in 5 seconds...", attempt + 1, max_retries, e)
                    close_old_connections()
                    from time import sleep
                    sleep(5)
                else:
                    logging.exception("Max retries reached. Failed to save %s", getattr(item, 'pageUrl', 'UNKNOWN'))
                    raise
            except Exception:
                logging.exception("save error %s:%s", getattr(item, 'propertyName', 'UNKNOWN'), getattr(item, 'pageUrl', 'UNKNOWN_URL'))
                raise

    def _afterRunProc(self, run_result):
        logging.debug("start afterRunProc")
        try:
            for item in run_result:
                if item is not None:
                    self._save_item_with_retry(item)
        finally:
            close_old_connections()
            logging.debug("finished afterRunProc")
