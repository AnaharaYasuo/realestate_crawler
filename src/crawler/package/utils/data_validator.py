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

        # 1. 価格の検証
        price = getattr(item, "price", 0) or 0
        try:
            price_val = float(price)
        except (ValueError, TypeError):
            price_val = 0.0

        price_man = price_val / 10000.0

        # 価格下限（100万円未満）および上限（20億円超）
        if price_man <= 0 or price_man < 100.0:
            reasons.append(f"価格異常 ({price_man:.1f}万円: 100万円未満または0円)")
        elif price_man > 200000.0:  # 20億円超
            reasons.append(f"価格異常 ({price_man:.1f}万円: 20億円超の異常値疑い)")

        # 2. 面積の動的抽出と検証
        area = 0.0
        senyu = getattr(item, "senyuMenseki", None)
        tatemono = getattr(item, "tatemonoMenseki", None)
        tochi = getattr(item, "tochiMenseki", None)

        if senyu is not None:
            try:
                area = float(senyu)
            except (ValueError, TypeError):
                area = 0.0
        elif tatemono is not None:
            try:
                area = float(tatemono)
            except (ValueError, TypeError):
                area = 0.0
        elif tochi is not None:
            try:
                area = float(tochi)
            except (ValueError, TypeError):
                area = 0.0

        if area <= 5.0:
            reasons.append(f"面積異常 ({area:.1f}㎡: 5㎡以下)")
        elif area > 10000.0 and ptype in ["mansion", "kodate", "invest_kodate"]:
            reasons.append(f"面積異常 ({area:.1f}㎡: 住宅用として過大)")

        # 3. 平米単価の検証（価格と面積の両方が正常値の場合）
        if price_val > 0 and area > 5.0:
            unit_price = price_val / area
            if unit_price < 1000.0:  # 1㎡あたり1000円未満（極端な桁ズレ）
                reasons.append(f"単価異常 (平米単価 {unit_price:.0f}円: 1000円/㎡未満)")
            elif unit_price > 15000000.0:  # 1㎡あたり1500万円超（坪約5000万円超）
                reasons.append(f"単価異常 (平米単価 {unit_price:.0f}円: 1500万円/㎡超)")

        # 4. 築年数・築年月の検証
        current_year = datetime.now(timezone.utc).year
        chikunengetsu = getattr(item, "chikunengetsu", None)
        if chikunengetsu and isinstance(chikunengetsu, (datetime,)):
            if chikunengetsu.year < 1900:
                reasons.append(f"築年数異常 ({chikunengetsu.year}年: 1900年以前)")
            elif chikunengetsu.year > current_year + 3:
                reasons.append(f"築年数異常 ({chikunengetsu.year}年: 未来年)")
        else:
            chikunen_str = getattr(item, "chikunengetsuStr", None)
            if chikunen_str and isinstance(chikunen_str, str):
                match = re.search(r"(\d{4})年", chikunen_str)
                if match:
                    y = int(match.group(1))
                    if y < 1900:
                        reasons.append(f"築年数異常 ({y}年: 1900年以前)")
                    elif y > current_year + 3:
                        reasons.append(f"築年数異常 ({y}年: 未来年)")

        # 5. 物件種別ごとの必須スペック欠損チェック
        if ptype == "mansion":
            # マンション: 専有面積、所在階
            if not senyu or float(senyu or 0) <= 0:
                reasons.append("必須項目欠損 (専有面積が未抽出)")
            floor = getattr(item, "shozaikai", None) or getattr(item, "kaisu", None)
            if not floor or str(floor).strip() in ["", "-", "None"]:
                reasons.append("必須項目欠損 (所在階が未抽出)")

        elif ptype in ["kodate", "invest_kodate"]:
            # 戸建て: 建物面積、土地面積
            if not tatemono or float(tatemono or 0) <= 0:
                reasons.append("必須項目欠損 (建物面積が未抽出)")
            if not tochi or float(tochi or 0) <= 0:
                reasons.append("必須項目欠損 (土地面積が未抽出)")

        elif ptype == "tochi":
            # 土地: 土地面積
            if not tochi or float(tochi or 0) <= 0:
                reasons.append("必須項目欠損 (土地面積が未抽出)")

        elif "apartment" in ptype or "invest" in ptype:
            # 投資用一棟/アパート: 利回り（yieldRate）が存在する場合のチェック
            yield_rate = getattr(item, "yieldRate", None) or getattr(item, "grossYield", None)
            if yield_rate is not None:
                try:
                    y_val = float(yield_rate)
                    if y_val <= 0 or y_val > 100.0:
                        reasons.append(f"利回り異常 ({y_val:.1f}%: 0%以下または100%超)")
                except (ValueError, TypeError):
                    pass

        return len(reasons) == 0, reasons
