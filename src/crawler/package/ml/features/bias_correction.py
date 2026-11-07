"""
特定物件種別のバイアス是正および非線形補正特徴量モジュール (Issue #1304, #1305, #1306)
"""
import math
from typing import Any
from .parsers import _get_attr, safe_float, parse_kouzou
from .constants import LIFESPAN


def calculate_bias_correction_features(
    property_obj: Any,
    property_type: str,
    chikunen: float,
    tatemono_area: float,
    tochi_area: float,
    average_land_price: float,
    kouzou_str: str,
    combined_text: str,
    is_shigaika_chousei: float,
) -> dict[str, float]:
    """
    本番実データ分析に基づく3大構造的バイアスを是正する特徴量を算出:
    1. 戸建て: 耐用年数超減価率 & 解体費用控除 (Issue #1304)
    2. マンション: 築古ヴィンテージ床 & 規模交差項 (Issue #1305)
    3. 土地: 低路線価・低需要エリア減価率 (Issue #1306)
    """
    res = {
        "building_depreciation_ratio": 1.0,
        "demolition_cost_discount": 0.0,
        "mansion_vintage_floor": 0.0,
        "scale_vintage_interaction": 0.0,
        "low_demand_land_discount": 1.0,
    }

    # 1. 戸建て・アパート: 建物耐用年数超減価と解体控除 (Issue #1304)
    if property_type in ("kodate", "apartment"):
        kouzou_cat = parse_kouzou(kouzou_str)
        legal_lifespan = float(LIFESPAN.get(kouzou_cat, 22))
        age = max(0.0, float(chikunen))

        # 法定耐用年数超減価カーブ: 耐用年数内は線形償却、超過後は指数関数的減衰し残存10%で底打ち
        if age <= legal_lifespan:
            dep_ratio = max(0.10, (legal_lifespan - age * 0.90) / legal_lifespan)
        else:
            over_years = age - legal_lifespan
            dep_ratio = max(0.05, 0.10 * math.exp(-0.03 * over_years))
        res["building_depreciation_ratio"] = round(dep_ratio, 4)

        # 築30年超または古家表記のある木造戸建ての更地化解体コスト控除（万円単位）
        is_furuya_text = any(k in combined_text for k in ["古家", "上物あり", "上物有", "解体"])
        if (age >= 30.0 or is_furuya_text) and "更地渡し" not in combined_text:
            b_area = max(50.0, float(tatemono_area or 80.0))
            # 木造約1.5万円/㎡
            res["demolition_cost_discount"] = round(b_area * 1.5, 2)

    # 2. マンション: 築古ヴィンテージ床と規模交差項 (Issue #1305)
    if property_type == "mansion":
        age = max(0.0, float(chikunen))
        # 築30年超過後の下げ止まり効果（リノベ・立地価値床）
        res["mansion_vintage_floor"] = round(1.0 / (1.0 + math.exp(-0.15 * (age - 30.0))), 4) if age >= 25.0 else 0.0

        # 総戸数（スケールメリット）× 築年数
        raw_units = _get_attr(property_obj, "soukosu", 0) or _get_attr(property_obj, "totalUnits", 0) or 0
        units = safe_float(raw_units, 0.0)
        log_units = math.log1p(max(0.0, units))
        res["scale_vintage_interaction"] = round(log_units * math.sqrt(max(1.0, age)), 4)

    # 3. 土地: 低路線価・低需要エリア非線形減価 (Issue #1306)
    if property_type in ("tochi", "kodate"):
        land_price_val = float(average_land_price or 0.0)
        # ㎡単価5万円以下（50,000円/㎡）または市街化調整区域における需要減退
        if land_price_val < 50000.0 or is_shigaika_chousei >= 0.5:
            base_discount = max(0.20, (land_price_val / 50000.0) ** 0.5) if land_price_val > 0 else 0.20
            if is_shigaika_chousei >= 0.5:
                base_discount *= 0.50
            res["low_demand_land_discount"] = round(base_discount, 4)
        else:
            res["low_demand_land_discount"] = 1.0

    return res
