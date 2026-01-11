import logging
import traceback
import asyncio
from flask import Blueprint, request
from package.api.api import (
    API_KEY_MISAWA_MANSION_START,
    API_KEY_MISAWA_KODATE_START,
    API_KEY_MISAWA_TOCHI_START,
    API_KEY_MISAWA_INVEST_START
)
from package.api.misawa import Misawa

misawa_bp = Blueprint('misawa', __name__)

async def run_misawa_crawl(target_types):
    crawler = Misawa(target_types=target_types)
    await crawler.crawl()
    return "Success"

@misawa_bp.route(API_KEY_MISAWA_MANSION_START, methods=['OPTIONS', 'POST', 'GET'])
def misawaMansionStart():
    logging.info("Start misawaMansionStart")
    try:
        # Type 1: Mansion
        asyncio.run(run_misawa_crawl(['1']))
    except:
        logging.error("Failed misawaMansionStart")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success misawaMansionStart")
    return "finish", 200

@misawa_bp.route(API_KEY_MISAWA_KODATE_START, methods=['OPTIONS', 'POST', 'GET'])
def misawaKodateStart():
    logging.info("Start misawaKodateStart")
    try:
        # Type 2: Kodate
        asyncio.run(run_misawa_crawl(['2']))
    except:
        logging.error("Failed misawaKodateStart")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success misawaKodateStart")
    return "finish", 200

@misawa_bp.route(API_KEY_MISAWA_TOCHI_START, methods=['OPTIONS', 'POST', 'GET'])
def misawaTochiStart():
    logging.info("Start misawaTochiStart")
    try:
        # Type 3: Tochi
        asyncio.run(run_misawa_crawl(['3']))
    except:
        logging.error("Failed misawaTochiStart")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success misawaTochiStart")
    return "finish", 200

@misawa_bp.route(API_KEY_MISAWA_INVEST_START, methods=['OPTIONS', 'POST', 'GET'])
def misawaInvestStart():
    logging.info("Start misawaInvestStart")
    try:
        # Type 4: Investment
        asyncio.run(run_misawa_crawl(['4']))
    except:
        logging.error("Failed misawaInvestStart")
        logging.error(traceback.format_exc())
        return "error end", 500
    logging.info("Success misawaInvestStart")
    return "finish", 200
