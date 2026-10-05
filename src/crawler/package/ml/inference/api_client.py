# -*- coding: utf-8 -*-
"""API 経由での価格推定クライアントおよびプロパティシリアライザ (Issue #714)"""

import logging
import os
from typing import Any
from package.ml.constants import COMPANIES


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
    except Exception:
        return None


def _serialize_chikunengetsu_field(item: Any) -> str:
    chikunengetsu = _prop_val(item, "chikunengetsu", None)
    if not chikunengetsu:
        return str(_prop_val(item, "chikunengetsuStr", "") or "")
    if hasattr(chikunengetsu, "strftime"):
        return chikunengetsu.strftime("%Y-%m-%d")
    return str(chikunengetsu)


def _serialize_type_specific_fields(data: dict[str, Any], item: Any, ptype: str) -> None:
    if ptype == "mansion":
        data["senyuMenseki"] = _prop_to_float(_prop_val(item, "senyuMenseki"))
        data["kanrihi"] = _prop_val(item, "kanrihi", None)
        data["syuzenTsumitate"] = _prop_val(item, "syuzenTsumitate", None)
        return

    if ptype in ("kodate", "apartment", "tochi"):
        data["tochiMenseki"] = _prop_to_float(_prop_val(item, "tochiMenseki"))
        data["maguchi"] = _prop_to_float(_prop_val(item, "maguchi"))
        data["roadWidth"] = _prop_to_float(_prop_val(item, "roadWidth"))
        data["setsudou"] = _prop_val(item, "setsudou", "")

    if ptype in ("kodate", "apartment"):
        data["tatemonoMenseki"] = _prop_to_float(_prop_val(item, "tatemonoMenseki"))

    if ptype == "apartment":
        data["grossYield"] = _prop_to_float(_prop_val(item, "grossYield"))
        data["annualRent"] = _prop_val(item, "annualRent", None)


def serialize_property(item: Any, ptype: str) -> dict[str, Any]:
    """Djangoモデルオブジェクトまたは辞書からAPI送信用のシリアライズ辞書を作成"""
    address = _prop_val(item, "address", "")
    if not address:
        addr1 = _prop_val(item, "address1", "") or ""
        addr2 = _prop_val(item, "address2", "") or ""
        address = f"{addr1}{addr2}".strip()

    data: dict[str, Any] = {
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
    payload = {
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
        logging.error("API estimation failed: status=%s, response=%s", response.status_code, response.text)
    except Exception as e:
        logging.debug("API server not reachable, falling back to local prediction: %s", e)

    return 0, 0
