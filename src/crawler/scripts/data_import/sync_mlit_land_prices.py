import json
import logging
import os
import re
import sys
from collections import defaultdict

# Django環境のロード
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import realestateSettings

realestateSettings.configure()

from package.models.evaluation import LandPricePotential
from package.utils.mlit_transaction_data import (
    PREF_CODE_TO_NAME,
    REINFOLIB_XIT001_URL,
    fetch_reinfolib_xit001_trades,
)

# 国土交通省 不動産情報ライブラリ 不動産価格情報取得APIエンドポイント (旧 webland 廃止に伴う移行)
MLIT_API_URL = REINFOLIB_XIT001_URL
logger = logging.getLogger(__name__)

def safe_path(path: str) -> str:
    """Return the canonical path when it is within the working or repository tree.

    Raises:
        ValueError: If the resolved path is outside both allowed trees.
    """
    resolved = os.path.realpath(path)
    base_dir = os.path.realpath(os.getcwd())
    if resolved != base_dir and not resolved.startswith(base_dir + os.sep):
        project_root = os.path.realpath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
        if resolved != project_root and not resolved.startswith(project_root + os.sep):
            raise ValueError(f"path {path!r} is outside the allowed directory")
    return resolved


def _classify_use_for_potential(raw_use: str) -> str | None:
    if "住宅" in raw_use:
        return "residential"
    if any(k in raw_use for k in ("商業", "店舗", "事務所")):
        return "commercial"
    return None


def _extract_city_use_unit_price(trade: dict) -> tuple[str, str, float] | None:
    city = str(trade.get("Municipality") or trade.get("City") or "").strip()
    land_use = _classify_use_for_potential(str(trade.get("Use", "")))
    if not city or not land_use:
        return None
    try:
        price = float(trade.get("TradePrice", "0"))
        area_match = re.search(r"([\d.]+)", str(trade.get("Area", "0")))
        if not area_match:
            return None
        area = float(area_match.group(1))
        if area <= 0:
            return None
        unit_price = price / area
        if not (10000 <= unit_price <= 10000000):
            return None
        return city, land_use, unit_price
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _load_mlit_trade_list(pref_code: str, year_quarter: str, json_path: str | None) -> list[dict]:
    if json_path:
        clean_path = safe_path(json_path)
        logger.info("Loading real estate trade data from local JSON file: %s...", clean_path)
        with open(clean_path, encoding="utf-8") as f:
            return json.load(f).get("data", [])
    api_key = os.environ.get("REINFOLIB_API_KEY", "").strip()
    yq = str(year_quarter)
    yr = int(yq[:4]) if len(yq) >= 4 else 2024
    qtr = int(yq[4:5]) if len(yq) >= 5 else None
    logger.info(
        "Fetching real estate trade data from MLIT Reinfolib XIT001 for prefecture=%s, year=%s, quarter=%s...",
        pref_code, yr, qtr,
    )
    return fetch_reinfolib_xit001_trades(api_key, str(pref_code), yr, quarter=qtr, timeout=45.0)


def sync_land_prices_from_mlit(pref_code="13", year_quarter="20241", json_path=None):
    """Aggregate MLIT trade data and upsert average land prices by municipality."""
    try:
        trade_list = _load_mlit_trade_list(str(pref_code), str(year_quarter), json_path)
        if not trade_list:
            logger.warning("No trade data returned.")
            return False

        logger.info("Successfully loaded %d trade records. Commencing aggregation...", len(trade_list))
        stats = defaultdict(lambda: [0.0, 0])
        pref_name = PREF_CODE_TO_NAME.get(str(pref_code).zfill(2), "東京都")

        for trade in trade_list:
            parsed = _extract_city_use_unit_price(trade)
            if parsed is None:
                continue
            city, land_use, unit_price = parsed
            key = (pref_name, city, land_use)
            stats[key][0] += unit_price
            stats[key][1] += 1
                
        # データベースにマスタとして保存・洗い替え
        saved_count = 0
        for (pref, city_name, use), (total_unit_price, count) in stats.items():
            if count == 0:
                continue
            
            # 平均平米単価の算出
            avg_unit_price = int(total_unit_price / count)
            
            # 8割を路線価、7割を固定資産税評価額として推定
            rosenka = int(avg_unit_price * 0.8)
            fixed_asset = int(avg_unit_price * 0.7)
            
            # update_or_create でマスタに同期
            LandPricePotential.objects.update_or_create(
                prefecture=pref,
                city=city_name,
                land_use=use,
                defaults={
                    "average_land_price": avg_unit_price,
                    "estimated_rosenka_price": rosenka,
                    "estimated_fixed_asset_price": fixed_asset
                }
            )
            saved_count += 1
            
        print(f"MLIT API Sync: Successfully updated {saved_count} municipality land price records in database.")
        return True
        
    except Exception:
        logger.exception("Failed to sync land prices from MLIT API")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # デフォルトで東京都 (13) の直近データを取得
    # 国交省のAPIは前四半期のデータを取得可能。ここでは "20241" (2024年第1四半期) などを基準にする
    import argparse
    parser = argparse.ArgumentParser(description="Sync land prices from MLIT API.")
    parser.add_argument("--area", default="13", help="Prefecture code (e.g., 13 for Tokyo, 14 for Kanagawa)")
    parser.add_argument("--quarter", default="20241", help="Year and Quarter (e.g., 20241)")
    parser.add_argument("--json", default=None, help="Path to local MLIT JSON file")
    args = parser.parse_args()
    
    sync_land_prices_from_mlit(pref_code=args.area, year_quarter=args.quarter, json_path=args.json)
