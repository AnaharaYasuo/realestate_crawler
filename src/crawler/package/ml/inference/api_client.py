"""API 経由での価格推定クライアントおよびプロパティシリアライザ (Issue #714)"""

import logging
import os
from typing import Any

from package.ml.constants import COMPANIES

logger = logging.getLogger(__name__)


def get_api_base_url() -> str:
    """価格推定APIのベースURLを解決する"""
    url = os.getenv("EVALUATION_API_URL", "")
    if url:
        if not url.endswith("/"):
            url += "/"
        return url
    base = (os.getenv("API_BASE_URL") or "http://localhost:8000").rstrip("/")
    return f"{base}/api/evaluation/predict/"


def _prop_val(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _prop_to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None



def _serialize_chikunengetsu_field(item: Any) -> str:
    chikunengetsu = _prop_val(item, "chikunengetsu", None)
    if not chikunengetsu:
        return str(_prop_val(item, "chikunengetsuStr", "") or "")
    if hasattr(chikunengetsu, "strftime"):
        return chikunengetsu.strftime("%Y-%m-%d")
    return str(chikunengetsu)


def _serialize_land_and_road_fields(data: dict[str, Any], item: Any) -> None:
    for float_col in ("tochiMenseki", "maguchi", "setsumen", "roadWidth", "douroHaba", "okuyuki", "shidoMenseki"):
        val = _prop_to_float(_prop_val(item, float_col))
        if val is not None or float_col in ("tochiMenseki", "maguchi", "roadWidth"):
            data[float_col] = val
    for str_col in (
        "setsudou", "douro", "maguchiStr", "setsumenStr", "roadWidthStr", "douroHabaStr",
        "okuyukiStr", "roadDirection", "douroMuki", "roadType", "douroKubun", "roadStructure",
    ):
        val = _prop_val(item, str_col, "")
        if val or str_col == "setsudou":
            data[str_col] = str(val or "")


def _serialize_type_specific_fields(data: dict[str, Any], item: Any, ptype: str) -> None:
    if ptype == "mansion":
        data["senyuMenseki"] = _prop_to_float(_prop_val(item, "senyuMenseki"))
        data["kanrihi"] = _prop_val(item, "kanrihi", None)
        data["syuzenTsumitate"] = _prop_val(item, "syuzenTsumitate", None)
        return

    if ptype in ("kodate", "apartment", "tochi"):
        _serialize_land_and_road_fields(data, item)

    if ptype in ("kodate", "apartment"):
        data["tatemonoMenseki"] = _prop_to_float(_prop_val(item, "tatemonoMenseki"))

    if ptype == "apartment":
        data["grossYield"] = _prop_to_float(_prop_val(item, "grossYield"))
        data["annualRent"] = _prop_val(item, "annualRent", None)
        data["monthlyRent"] = _prop_val(item, "monthlyRent", None)


_OPTIONAL_COMMON_TEXT_ATTRS = (
    "propertyName", "address1", "address2", "traffic", "kaisu", "kaisuStr", "kai", "chijo",
    "madori", "chimoku", "chimokuChisei", "chisei", "setsubi", "genkyo", "currentStatus",
    "hikiwatashi", "kenchikuJoken", "boukaChiiki", "toshikeikaku", "kuiki", "youtoChiiki",
    "privateRoadBurden", "sonotaHiyouStr", "rights", "chidaiStr",
)
_OPTIONAL_COMMON_NUM_ATTRS = (
    "busUse1", "busRideMinute1", "busWalkMinute1", "soukosu", "chidai", "latitude", "longitude",
)


def serialize_property(item: Any, ptype: str) -> dict[str, Any]:
    """Djangoモデルオブジェクトまたは辞書からAPI送信・インライン評価用の完全シリアライズ辞書を作成"""
    address = _prop_val(item, "address", "")
    if not address:
        addr1 = _prop_val(item, "address1", "") or ""
        addr2 = _prop_val(item, "address2", "") or ""
        address = f"{addr1}{addr2}".strip()

    data: dict[str, Any] = {
        "propertyType": ptype,
        "price": _prop_val(item, "price", None),
        "address": address,
        "station1": _prop_val(item, "station1", ""),
        "railwayWalkMinute1": _prop_val(item, "railwayWalkMinute1", None),
        "kouzou": _prop_val(item, "kouzou", ""),
        "youseki": _prop_to_float(_prop_val(item, "youseki")),
        "kenpei": _prop_to_float(_prop_val(item, "kenpei")),
        "yousekiStr": str(_prop_val(item, "yousekiStr", "") or _prop_val(item, "youseki", "") or ""),
        "kenpeiStr": str(_prop_val(item, "kenpeiStr", "") or _prop_val(item, "kenpei", "") or ""),
        "tochikenri": _prop_val(item, "tochikenri", ""),
        "biko": _prop_val(item, "biko", ""),
        "chikunengetsuStr": _serialize_chikunengetsu_field(item),
    }
    for attr in _OPTIONAL_COMMON_TEXT_ATTRS:
        val = _prop_val(item, attr, None)
        if val not in (None, ""):
            data[attr] = str(val)
    for attr in _OPTIONAL_COMMON_NUM_ATTRS:
        val = _prop_val(item, attr, None)
        if val is not None:
            data[attr] = _prop_to_float(val) if attr in ("latitude", "longitude") else val

    _serialize_type_specific_fields(data, item, ptype)
    return data


def call_predict_api(
    property_obj: Any,
    interior_score: float = 3.0,
    layout_score: float = 3.0,
) -> tuple[int, int]:
    """APIを呼び出して推定結果 (first_stage, second_stage) を返す"""
    ptype = _prop_val(property_obj, "propertyType") or _prop_val(property_obj, "property_type")
    if not ptype:
        model_name = property_obj.__class__.__name__
        company = "unknown"
        for c in COMPANIES:
            if model_name.lower().startswith(c):
                company = c
                break
        ptype = model_name.lower().replace(company, "")

    if "kodate" in ptype:
        ptype = "kodate"
    elif "apartment" in ptype:
        ptype = "apartment"

    if ptype not in ("mansion", "kodate", "apartment", "tochi"):
        ptype = "mansion"

    serialized = serialize_property(property_obj, ptype)
    payload: dict[str, Any] = {
        "property_data": serialized,
        "interior_score": float(interior_score),
        "layout_score": float(layout_score),
    }

    api_base_url = get_api_base_url()
    api_url = f"{api_base_url}{ptype}"

    try:
        import requests
        response = requests.post(api_url, json=payload, timeout=5)
        if response.status_code == 200:
            res_data = response.json()
            return (
                int(res_data.get("first_stage_predicted_price", 0)),
                int(res_data.get("second_stage_predicted_price", 0)),
            )
        logger.error("API estimation failed: status=%s, response=%s", response.status_code, response.text)
    except (requests.RequestException, ValueError, KeyError) as e:
        logger.debug("API server not reachable, falling back to local prediction: %s", e)

    return 0, 0

