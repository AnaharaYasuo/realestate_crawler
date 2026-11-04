# -*- coding: utf-8 -*-
"""
Road parsing helper function for parsers to unpack setsudou text into:
- douroMuki / roadDirection
- douroHaba / roadWidth / roadWidthStr
- douroKubun / roadType
- setsumen
"""
import re
from decimal import Decimal

def parse_road_details(text: str) -> dict:
    result = {
        'douroMuki': '',
        'douroHaba': None,
        'douroKubun': '',
        'setsumen': None,
        'roadWidthStr': '',
        'roadWidth': None,
        'roadDirection': '',
        'roadType': '',
        'roadStructure': ''
    }
    if not text:
        return result

    # 方位 (e.g., 南西, 北東, 南, 北, etc.)
    muki_m = re.search(r'([東西南北]{1,2})', text)
    if muki_m:
        result['douroMuki'] = muki_m.group(1)
        result['roadDirection'] = muki_m.group(1)

    # 道路幅員 (e.g., 幅員約4.0m, 幅4m, 4.0m, 4m)
    # 幅員・幅が前につくか、もしくは「南西 6.0m」のように方位の後に続く数字+m
    haba_m = re.search(r'(?:幅員|幅|約)?\s*([0-9０-９]+(?:\.[0-9０-９]+)?)\s*[mｍ]', text)
    if haba_m and not re.search(r'[mｍ]\s*接面', text):
        try:
            import unicodedata
            val_str = unicodedata.normalize('NFKC', haba_m.group(1))
            val_dec = Decimal(val_str)
            result['douroHaba'] = val_dec
            result['roadWidth'] = val_dec
            result['roadWidthStr'] = f"{val_str}m"
        except Exception:
            pass

    # 道路区分 (公道/私道)
    if "公道" in text:
        result['douroKubun'] = "公道"
        result['roadType'] = "公道"
    elif "私道" in text:
        result['douroKubun'] = "私道"
        result['roadType'] = "私道"

    # 接面長 (e.g., 接面約8.0m, 接面8m, 間口8m)
    setsumen_m = re.search(r'(?:接面|間口)(?:約)?\s*([0-9０-９]+(?:\.[0-9０-９]+)?)\s*[mｍ]', text)
    if setsumen_m:
        try:
            import unicodedata
            val_str = unicodedata.normalize('NFKC', setsumen_m.group(1))
            result['setsumen'] = Decimal(val_str)
        except Exception:
            pass

    return result

def apply_road_details_to_item(item, text: str):
    if not text:
        return
    details = parse_road_details(text)
    for k, v in details.items():
        if hasattr(item, k) and v is not None and v != "":
            # Only set if item's attribute is currently empty or None
            cur = getattr(item, k)
            if cur is None or cur == "" or cur == Decimal(0):
                setattr(item, k, v)
