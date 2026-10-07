import re
from datetime import datetime, timezone
from typing import Any

from package.models.evaluation import PropertyEvaluation

# Error messages (Sonar S1192 constant reuse)
ERR_MISSING_SENYU = "必須項目欠損 (専有面積が未抽出)"
ERR_MISSING_FLOOR = "必須項目欠損 (所在階が未抽出)"
ERR_MISSING_TATEMONO = "必須項目欠損 (建物面積が未抽出)"
ERR_MISSING_TOCHI = "必須項目欠損 (土地面積が未抽出)"
ERR_MISSING_NAME = "必須項目欠損 (物件名が未抽出)"
ERR_MISSING_ADDRESS = "必須項目欠損 (住所が未抽出)"
ERR_MISSING_TRAFFIC = "必須項目欠損 (交通が未抽出)"
ERR_MISSING_MADORI = "必須項目欠損 (間取りが未抽出)"
ERR_MISSING_AGE = "必須項目欠損 (築年月が未抽出)"
_BLANKS = ("", "-", "None", "nan")


def _blank(val: Any) -> bool:
    return val is None or str(val).strip() in _BLANKS



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

        cls._check_common_required(item, reasons)
        price_val = cls._validate_price(item, ptype, reasons)
        area = cls._extract_and_validate_area(item, ptype, reasons)
        cls._validate_unit_price(item, ptype, price_val, area, reasons)
        cls._validate_age(item, reasons)
        cls._validate_type_specific_specs(item, ptype, reasons)

        return len(reasons) == 0, reasons

    @staticmethod
    def _check_common_required(item: Any, reasons: list[str]) -> None:
        """全ページに必ず存在する項目 (物件名・住所・交通) の欠損検査"""
        if _blank(getattr(item, "propertyName", None)):
            reasons.append(ERR_MISSING_NAME)
        if _blank(getattr(item, "address", None)):
            reasons.append(ERR_MISSING_ADDRESS)
        if _blank(getattr(item, "traffic", None)) and _blank(getattr(item, "station1", None)):
            reasons.append(ERR_MISSING_TRAFFIC)

    @staticmethod
    def _check_madori_and_age(item: Any, reasons: list[str]) -> None:
        """居住用 (mansion/kodate) で必ず存在する間取り・築年月の欠損検査"""
        if _blank(getattr(item, "madori", None)):
            reasons.append(ERR_MISSING_MADORI)
        if _blank(getattr(item, "chikunengetsu", None)) and _blank(getattr(item, "chikunengetsuStr", None)):
            reasons.append(ERR_MISSING_AGE)

    @classmethod
    def _is_low_price_allowed(cls, item: Any, ptype: str) -> bool:
        """山林・原野・雑種地・農地・持分売買・投資区分など低価格（10万〜100万円未満）が正常なケース"""
        chimoku = str(getattr(item, "chimoku", "") or "")
        valid_chimoku = {"山林", "原野", "雑種地", "農地", "畑", "田", "保安林", "ため池", "公衆用道路", "墓地"}
        if any(target in chimoku for target in valid_chimoku):
            return True

        name = str(getattr(item, "propertyName", "") or "")
        biko = str(getattr(item, "biko", "") or "")
        full_text = f"{name} {biko}"
        specific_keywords = ["山林", "原野", "雑種地", "農地", "資材置場", "持分", "オーナーチェンジ"]
        if any(kw in full_text for kw in specific_keywords):
            return True

        invest_keywords = ["利回り", "賃料", "家賃", "満室", "稼働", "一棟", "区分"]
        is_invest_type = ptype in ["investment", "invest", "investmentapartment", "investment_apartment"]
        has_valid_yield = False
        raw_yield = getattr(item, "yieldRate", None) or getattr(item, "grossYield", None)
        if raw_yield is not None:
            try:
                y_val = float(raw_yield)
                has_valid_yield = y_val > 0
            except (ValueError, TypeError):
                has_valid_yield = False
        return is_invest_type and (any(kw in full_text for kw in invest_keywords) or has_valid_yield)

    @classmethod
    def _validate_price(cls, item: Any, ptype: str, reasons: list[str]) -> float:
        price = getattr(item, "price", 0) or 0
        try:
            price_val = float(price)
        except (ValueError, TypeError):
            price_val = 0.0

        price_man = price_val / 10000.0
        # 100万円未満の価格チェック: 山林や投資用区分・持分等は1万円以上を許容
        min_price_man = 1.0 if cls._is_low_price_allowed(item, ptype) else 100.0
        if price_man <= 0 or price_man < min_price_man:
            reasons.append(f"価格異常 ({price_man:.1f}万円: {min_price_man:.0f}万円未満または0円)")
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

    @classmethod
    def _validate_unit_price(cls, item: Any, ptype: str, price_val: float, area: float, reasons: list[str]) -> None:
        if price_val > 0 and area > 5.0:
            unit_price = price_val / area
            # 山林・原野・安価な土地/投資物件は単価10円/㎡まで許容
            min_unit = 10.0 if cls._is_low_price_allowed(item, ptype) else 1000.0
            if unit_price < min_unit:
                reasons.append(f"単価異常 (平米単価 {unit_price:.0f}円: {min_unit:.0f}円/㎡未満)")
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
        if ptype in ["mansion", "kodate"]:
            cls._check_madori_and_age(item, reasons)
        if ptype == "mansion":
            cls._check_mansion_specs(item, reasons)
        elif ptype in ["kodate", "invest_kodate"]:
            cls._check_kodate_specs(item, reasons)
        elif ptype == "tochi":
            cls._check_tochi_specs(item, reasons)
        elif "apartment" in ptype or "invest" in ptype:
            cls._check_investment_specs(item, reasons)

    @staticmethod
    def _has_located_floor(kaisu_str: Any) -> bool:
        if not kaisu_str or str(kaisu_str).strip() in ["", "-", "None"]:
            return False
        tokens = [t.strip() for t in str(kaisu_str).replace('/', ' ').replace('／', ' ').split() if t.strip()]
        return any(
            '階' in token
            and not ('地上' in token or '地下' in token or '建' in token)
            and any(ch.isdigit() for ch in token)
            for token in tokens
        )

    @classmethod
    def _check_mansion_specs(cls, item: Any, reasons: list[str]) -> None:
        senyu = getattr(item, "senyuMenseki", None)
        try:
            if not senyu or float(senyu) <= 0:
                reasons.append(ERR_MISSING_SENYU)
        except (ValueError, TypeError):
            reasons.append(ERR_MISSING_SENYU)

        floor = (
            getattr(item, "shozaikai", None)
            or getattr(item, "kaisu", None)
            or getattr(item, "floorType_kai", None)
        )
        has_floor = bool(floor and str(floor).strip() not in ["", "-", "None"])
        if not has_floor and cls._has_located_floor(getattr(item, "kaisuStr", None)):
            has_floor = True

        if not has_floor:
            reasons.append(ERR_MISSING_FLOOR)

    @staticmethod
    def _check_kodate_specs(item: Any, reasons: list[str]) -> None:
        tatemono = getattr(item, "tatemonoMenseki", None)
        try:
            if not tatemono or float(tatemono) <= 0:
                reasons.append(ERR_MISSING_TATEMONO)
        except (ValueError, TypeError):
            reasons.append(ERR_MISSING_TATEMONO)

        tochi = getattr(item, "tochiMenseki", None)
        try:
            if not tochi or float(tochi) <= 0:
                reasons.append(ERR_MISSING_TOCHI)
        except (ValueError, TypeError):
            reasons.append(ERR_MISSING_TOCHI)

    @staticmethod
    def _check_tochi_specs(item: Any, reasons: list[str]) -> None:
        tochi = getattr(item, "tochiMenseki", None)
        try:
            if not tochi or float(tochi) <= 0:
                reasons.append(ERR_MISSING_TOCHI)
        except (ValueError, TypeError):
            reasons.append(ERR_MISSING_TOCHI)

    @staticmethod
    def _check_investment_specs(item: Any, reasons: list[str]) -> None:
        yield_rate = getattr(item, "yieldRate", None) or getattr(item, "grossYield", None)
        if yield_rate is not None:
            try:
                y_val = float(yield_rate)
                if y_val <= 0 or y_val > 100.0:
                    reasons.append(f"利回り異常 ({y_val:.1f}%: 0%以下または100%超)")
            except (ValueError, TypeError):
                reasons.append(f"利回り異常 ({yield_rate}: 数値変換不能)")


def tag_property_integrity(item: Any, property_type: str, company: str) -> tuple[bool, list[str]]:
    """
    保存後の共通整合性タグ付け。検証NGなら needs_parser_fix=True (オートヒール対象)、
    OKなら解消する。単件保存・バッチ保存・validate_data.py から共通利用。
    """
    is_valid, reasons = PropertyDataValidator.validate_property(item, property_type)
    issue = "; ".join(reasons)
    eval_rec, _ = PropertyEvaluation.objects.get_or_create(
        property_url=item.pageUrl,
        defaults={
            "company": company,
            "property_type": property_type,
            "property_id": getattr(item, "id", 0) or 0,
            "is_published": True,
            "needs_parser_fix": not is_valid,
            "needs_recrawl": False,
            "data_quality_issue": issue,
        },
    )
    if not is_valid:
        eval_rec.needs_parser_fix = True
        eval_rec.data_quality_issue = issue
        eval_rec.is_published = True
        eval_rec.save()
    else:
        # 正常保存は再掲載を含め公開状態へ復旧する。修復フラグの有無には依存しない
        eval_rec.needs_parser_fix = False
        eval_rec.needs_recrawl = False
        eval_rec.is_published = True
        eval_rec.delisted_at = None
        eval_rec.data_quality_issue = ""
        eval_rec.save()
    return is_valid, reasons
