import re
from datetime import datetime, timezone
from typing import Any


class PropertyDataValidator:
    """
    物件データの完全性・妥当性を厳格に検査する統一バリデータ (Issue #665)
    
    価格、面積、平米単価、築年数、種別ごとの必須スペックを多角的に検査し、
    クローラーのパーサー不具合や欠損を検知して Auto-Heal (自律修復) へ引き継ぐ。
    """

    @classmethod
    def validate_property(cls, item: Any, property_type: str) -> tuple[bool, list[str]]:
        """
        物件インスタンスを検証し、(is_valid: bool, reasons: list[str]) を返却する。
        is_valid が False の場合は再クローリング対象 (needs_recrawl=True) となる。
        """
        reasons: list[str] = []
        ptype = (property_type or "").lower().replace("-", "_")

        price_val = cls._validate_price(item, reasons)
        area = cls._extract_and_validate_area(item, ptype, reasons)
        cls._validate_unit_price(price_val, area, reasons)
        cls._validate_age(item, reasons)
        cls._validate_type_specific_specs(item, ptype, reasons)

        return len(reasons) == 0, reasons

    @staticmethod
    def _validate_price(item: Any, reasons: list[str]) -> float:
        price = getattr(item, "price", 0) or 0
        try:
            price_val = float(price)
        except (ValueError, TypeError):
            price_val = 0.0

        price_man = price_val / 10000.0
        if price_man <= 0 or price_man < 100.0:
            reasons.append(f"価格異常 ({price_man:.1f}万円: 100万円未満または0円)")
        elif price_man > 200000.0:
            reasons.append(f"価格異常 ({price_man:.1f}万円: 20億円超の異常値疑い)")
        return price_val

    @staticmethod
    def _extract_and_validate_area(item: Any, ptype: str, reasons: list[str]) -> float:
        area = 0.0
        senyu = getattr(item, "senyuMenseki", None)
        tatemono = getattr(item, "tatemonoMenseki", None)
        tochi = getattr(item, "tochiMenseki", None)

        for candidate in (senyu, tatemono, tochi):
            if candidate is not None:
                try:
                    area = float(candidate)
                    break
                except (ValueError, TypeError):
                    continue

        if area <= 5.0:
            reasons.append(f"面積異常 ({area:.1f}㎡: 5㎡以下)")
        elif area > 10000.0 and ptype in ["mansion", "kodate", "invest_kodate"]:
            reasons.append(f"面積異常 ({area:.1f}㎡: 住宅用として過大)")
        return area

    @staticmethod
    def _validate_unit_price(price_val: float, area: float, reasons: list[str]) -> None:
        if price_val > 0 and area > 5.0:
            unit_price = price_val / area
            if unit_price < 1000.0:
                reasons.append(f"単価異常 (平米単価 {unit_price:.0f}円: 1000円/㎡未満)")
            elif unit_price > 15000000.0:
                reasons.append(f"単価異常 (平米単価 {unit_price:.0f}円: 1500万円/㎡超)")

    @staticmethod
    def _validate_age(item: Any, reasons: list[str]) -> None:
        current_year = datetime.now(timezone.utc).year
        chikunengetsu = getattr(item, "chikunengetsu", None)
        if chikunengetsu and isinstance(chikunengetsu, datetime):
            if chikunengetsu.year < 1900:
                reasons.append(f"築年数異常 ({chikunengetsu.year}年: 1900年以前)")
            elif chikunengetsu.year > current_year + 3:
                reasons.append(f"築年数異常 ({chikunengetsu.year}年: 未来年)")
            return

        chikunen_str = getattr(item, "chikunengetsuStr", None)
        if chikunen_str and isinstance(chikunen_str, str):
            match = re.search(r"(\d{4})年", chikunen_str)
            if match:
                y = int(match.group(1))
                if y < 1900:
                    reasons.append(f"築年数異常 ({y}年: 1900年以前)")
                elif y > current_year + 3:
                    reasons.append(f"築年数異常 ({y}年: 未来年)")

    @classmethod
    def _validate_type_specific_specs(cls, item: Any, ptype: str, reasons: list[str]) -> None:
        if ptype == "mansion":
            cls._check_mansion_specs(item, reasons)
        elif ptype in ["kodate", "invest_kodate"]:
            cls._check_kodate_specs(item, reasons)
        elif ptype == "tochi":
            cls._check_tochi_specs(item, reasons)
        elif "apartment" in ptype or "invest" in ptype:
            cls._check_investment_specs(item, reasons)

    @staticmethod
    def _check_mansion_specs(item: Any, reasons: list[str]) -> None:
        senyu = getattr(item, "senyuMenseki", None)
        if not senyu or float(senyu or 0) <= 0:
            reasons.append("必須項目欠損 (専有面積が未抽出)")
        floor = getattr(item, "shozaikai", None) or getattr(item, "kaisu", None)
        if not floor or str(floor).strip() in ["", "-", "None"]:
            reasons.append("必須項目欠損 (所在階が未抽出)")

    @staticmethod
    def _check_kodate_specs(item: Any, reasons: list[str]) -> None:
        tatemono = getattr(item, "tatemonoMenseki", None)
        tochi = getattr(item, "tochiMenseki", None)
        if not tatemono or float(tatemono or 0) <= 0:
            reasons.append("必須項目欠損 (建物面積が未抽出)")
        if not tochi or float(tochi or 0) <= 0:
            reasons.append("必須項目欠損 (土地面積が未抽出)")

    @staticmethod
    def _check_tochi_specs(item: Any, reasons: list[str]) -> None:
        tochi = getattr(item, "tochiMenseki", None)
        if not tochi or float(tochi or 0) <= 0:
            reasons.append("必須項目欠損 (土地面積が未抽出)")

    @staticmethod
    def _check_investment_specs(item: Any, reasons: list[str]) -> None:
        yield_rate = getattr(item, "yieldRate", None) or getattr(item, "grossYield", None)
        if yield_rate is not None:
            try:
                y_val = float(yield_rate)
                if y_val <= 0 or y_val > 100.0:
                    reasons.append(f"利回り異常 ({y_val:.1f}%: 0%以下または100%超)")
            except (ValueError, TypeError):
                pass
