import re
from datetime import datetime, timezone
from typing import Any

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

        cls._check_common_required(item, ptype, reasons)
        price_val = cls._validate_price(item, ptype, reasons)
        area = cls._extract_and_validate_area(item, ptype, reasons)
        cls._validate_unit_price(item, ptype, price_val, area, reasons)
        cls._validate_age(item, ptype, reasons)
        cls._validate_type_specific_specs(item, ptype, reasons)

        return len(reasons) == 0, reasons

    @classmethod
    def _check_common_required(cls, item: Any, ptype: str, reasons: list[str]) -> None:
        """全ページに必ず存在する項目 (物件名・住所・交通) の欠損検査"""
        if _blank(getattr(item, "propertyName", None)):
            reasons.append(ERR_MISSING_NAME)
        if _blank(getattr(item, "address", None)):
            reasons.append(ERR_MISSING_ADDRESS)
        if (
            _blank(getattr(item, "traffic", None))
            and _blank(getattr(item, "station1", None))
            and _blank(getattr(item, "railway1", None))
            and _blank(getattr(item, "busStation1", None))
            and _blank(getattr(item, "transport1", None))
        ):
            is_invest = "invest" in ptype or "apartment" in ptype or cls._is_low_price_allowed(item, ptype)
            if not is_invest:
                reasons.append(ERR_MISSING_TRAFFIC)

    @classmethod
    def _is_under_construction(cls, item: Any) -> bool:
        """建築中・未完成物件の判定（築年月未抽出を許容する）"""
        genkyo = str(getattr(item, "genkyo", "") or getattr(item, "currentStatus", "") or "")
        if any(tok in genkyo for tok in ("未完成", "建築中", "新築（未完成）")):
            return True
        name = str(getattr(item, "propertyName", "") or "")
        biko = str(getattr(item, "biko", "") or "")
        combined = f"{name} {biko}"
        return any(tok in combined for tok in ("建築中", "新築未完成", "建築確認番号"))

    @classmethod
    def _check_madori_and_age(cls, item: Any, reasons: list[str]) -> None:
        """居住用 (mansion/kodate) で必ず存在する間取り・築年月の欠損検査（モデル未定義時はスキップ）"""
        has_madori_field = True
        has_age_field = True
        if hasattr(item, "_meta") and hasattr(item._meta, "get_fields"):
            field_names = {f.name for f in item._meta.get_fields()}
            has_madori_field = "madori" in field_names
            has_age_field = "chikunengetsu" in field_names or "chikunengetsuStr" in field_names

        if has_madori_field:
            madori_val = getattr(item, "madori", None)
            if _blank(madori_val) and str(madori_val or "").strip() not in ("-", "―", "ー", "未定", "相談"):
                # 投資用区分マンションはスペック表に間取り表記がない場合があるため除外
                if not cls._is_invest_unit_mansion(item):
                    reasons.append(ERR_MISSING_MADORI)
        if has_age_field and _blank(getattr(item, "chikunengetsu", None)) and _blank(getattr(item, "chikunengetsuStr", None)):
            if not cls._is_under_construction(item):
                reasons.append(ERR_MISSING_AGE)

    _LOW_PRICE_CHIMOKU = {"山林", "原野", "雑種地", "農地", "畑", "田", "保安林", "ため池", "公衆用道路", "墓地"}
    _LOW_PRICE_KEYWORDS = (
        "山林", "原野", "雑種地", "農地", "資材置場", "持分", "オーナーチェンジ",
        "古家", "空き家", "空家", "ヘルス・ケア", "ヘルスケア", "リゾート",
        "その他用地", "倉庫用地", "別荘地", "分譲地", "再建築不可", "借地権",
    )
    _RURAL_KEYWORDS = ("郡", "村", "大字", "字", "温泉")
    _INVEST_PTYPES = {
        "investment", "invest", "apartment", "investmentapartment",
        "investment_apartment", "invest_apartment", "invest_kodate",
        "investment_kodate", "investmentkodate",
    }

    @staticmethod
    def _has_positive_numeric_attr(item: Any, *attrs: str) -> bool:
        for attr in attrs:
            raw = getattr(item, attr, None)
            if raw is None:
                continue
            try:
                if float(raw) > 0:
                    return True
            except (ValueError, TypeError):
                continue
        return False

    @classmethod
    def _is_rural_or_tochi_low_price(cls, item: Any, ptype: str, _full_text: str) -> bool:
        try:
            price_num = float(getattr(item, "price", 0) or 0)
        except (ValueError, TypeError):
            return False
        if price_num < 100000:
            return False
        if ptype not in ("tochi", "kodate", "invest_kodate"):
            return False
        addr = str(getattr(item, "address", "") or "")
        return any(rk in addr for rk in cls._RURAL_KEYWORDS)

    @classmethod
    def _is_low_price_allowed(cls, item: Any, ptype: str) -> bool:
        """山林・原野・雑種地・農地・持分売買・投資区分・ヘルスケア・リゾート等低価格（10万〜100万円未満）が正常なケース"""
        chimoku = str(getattr(item, "chimoku", "") or "")
        if any(target in chimoku for target in cls._LOW_PRICE_CHIMOKU):
            return True

        full_text = f"{getattr(item, 'propertyName', '') or ''} {getattr(item, 'biko', '') or ''}"
        if any(kw in full_text for kw in cls._LOW_PRICE_KEYWORDS):
            return True

        if cls._is_rural_or_tochi_low_price(item, ptype, full_text):
            return True

        url_str = str(getattr(item, "pageUrl", "") or "").lower()
        if "toushi" in url_str or "invest" in url_str:
            return True

        if ptype not in cls._INVEST_PTYPES:
            return False

        invest_keywords = ("利回り", "賃料", "家賃", "満室", "稼働", "一棟", "区分")
        return (
            any(kw in full_text for kw in invest_keywords)
            or cls._has_positive_numeric_attr(item, "yieldRate", "grossYield")
            or cls._has_positive_numeric_attr(item, "annualRent", "monthlyRent")
        )

    @classmethod
    def _is_invest_unit_mansion(cls, item: Any) -> bool:
        """投資ポータル由来または利回り・想定年収を伴う投資用区分マンション判定"""
        url_str = str(getattr(item, "pageUrl", "") or "").lower()
        if "toushi" in url_str or "invest" in url_str:
            return True
        raw_yield = getattr(item, "yieldRate", None) or getattr(item, "grossYield", None)
        if raw_yield is not None:
            try:
                if float(raw_yield) > 0:
                    return True
            except (ValueError, TypeError):
                pass
        name = str(getattr(item, "propertyName", "") or "")
        biko = str(getattr(item, "biko", "") or "")
        full_text = f"{name} {biko}"
        return any(kw in full_text for kw in ["オーナーチェンジ", "利回り", "投資用"])

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
        elif price_man > 500000.0:
            reasons.append(f"価格異常 ({price_man:.1f}万円: 50億円超の異常値疑い)")
        return price_val

    @staticmethod
    def _parse_candidate_float(val: Any) -> float | None:
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    @classmethod
    def _is_invest_area_exempt(cls, item: Any, ptype: str) -> bool:
        if cls._is_low_price_allowed(item, ptype):
            return True
        if not ("invest" in ptype or "apartment" in ptype):
            return False

        for attr in ("yieldRate", "grossYield", "rent", "monthlyRent", "annualRent"):
            val = cls._parse_candidate_float(getattr(item, attr, None))
            if val is not None and val > 0:
                return True
        return False

    @classmethod
    def _extract_and_validate_area(cls, item: Any, ptype: str, reasons: list[str]) -> float:
        area = 0.0
        if ptype in ("mansion", "invest_mansion"):
            attrs = ("senyuMenseki",)
        elif ptype == "tochi":
            attrs = ("tochiMenseki",)
        else:
            attrs = ("senyuMenseki", "tatemonoMenseki", "tochiMenseki")

        candidates = [
            cls._parse_candidate_float(getattr(item, attr, None))
            for attr in attrs
        ]
        parsed = [c for c in candidates if c is not None]
        if parsed:
            # > 5.0 を優先、なければ > 0.0 の正の値を優先
            valid_areas = [val for val in parsed if val > 5.0]
            if valid_areas:
                area = max(valid_areas)
            else:
                positive_areas = [val for val in parsed if val > 0.0]
                area = max(positive_areas) if positive_areas else parsed[0]

        if area <= 5.0:
            if not cls._is_invest_area_exempt(item, ptype):
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
            elif unit_price > 50000000.0:
                reasons.append(f"単価異常 (平米単価 {unit_price:.0f}円: 5000万円/㎡超)")


    @staticmethod
    def _validate_age(item: Any, ptype: str, reasons: list[str]) -> None:
        current_year = datetime.now(timezone.utc).year
        # 戸建て・古民家（京町家等）は明治初期（1850年以降）を許容、マンション・投資等は1900年以降
        min_year = 1850 if "kodate" in ptype else 1900
        chikunengetsu = getattr(item, "chikunengetsu", None)
        if chikunengetsu and isinstance(chikunengetsu, datetime):
            if chikunengetsu.year < min_year:
                reasons.append(f"築年数異常 ({chikunengetsu.year}年: {min_year}年以前)")
            elif chikunengetsu.year > current_year + 3:
                reasons.append(f"築年数異常 ({chikunengetsu.year}年: 未来年)")
            return

        chikunen_str = getattr(item, "chikunengetsuStr", None)
        if chikunen_str and isinstance(chikunen_str, str):
            match = re.search(r"(\d{4})年", chikunen_str)
            if match:
                y = int(match.group(1))
                if y < min_year:
                    reasons.append(f"築年数異常 ({y}年: {min_year}年以前)")
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
            cls._check_investment_specs(item, ptype, reasons)

    @staticmethod
    def _has_located_floor(kaisu_str: Any) -> bool:
        """
        kaisuStr から所在階情報（例: '3階/7階建', '所在階: 5階', '5階部分'）の有無を判定。
        建物全体の総階数（'地上7階', '7階建'）のみの場合は所在階未抽出として False を返す。
        """
        if not kaisu_str or str(kaisu_str).strip() in ["", "-", "None"]:
            return False
        s = str(kaisu_str).strip()
        # 所在階表記が明示されている場合
        if any(term in s for term in ["所在階", "階部分", "階／", "階/"]):
            return True
        # スラッシュ区切りで所在階/建物階数となっている場合 (例: 3階 / 地上7階, 地下1階 / 地上7階建)
        tokens = [t.strip() for t in s.replace('/', ' ').replace('／', ' ').split() if t.strip()]
        if len(tokens) >= 2:
            return any(
                '階' in token
                and not ('地上' in token or '建' in token or '総' in token)
                and any(ch.isdigit() for ch in token)
                for token in tokens
            )
        if len(tokens) == 1:
            tok = tokens[0]
            if '階' in tok and not ('地上' in tok or '地下' in tok or '建' in tok or '総' in tok):
                return any(ch.isdigit() for ch in tok)
        return False

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
            # 投資用区分マンションはサイトスペック表に所在階が非掲載の場合があるため除外
            if not cls._is_invest_unit_mansion(item):
                reasons.append(ERR_MISSING_FLOOR)

    @staticmethod
    def _check_kodate_specs(item: Any, reasons: list[str]) -> None:
        tatemono = getattr(item, "tatemonoMenseki", None)
        try:
            if not tatemono or float(tatemono) <= 0:
                reasons.append(ERR_MISSING_TATEMONO)
        except (ValueError, TypeError):
            reasons.append(ERR_MISSING_TATEMONO)

        # マンション・区分所有やビル区分が混入している場合は土地面積必須チェックを免除
        shumoku = getattr(item, "shumoku", "") or getattr(item, "bukkenShubetsu", "") or ""
        page_url = getattr(item, "pageUrl", "") or ""
        is_sectional_or_mansion = any(
            kw in shumoku for kw in ["マンション", "区分", "ビル", "店舗", "事務所"]
        ) or "/buy/mansion/" in page_url

        if not is_sectional_or_mansion:
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

    @classmethod
    def _check_investment_specs(cls, item: Any, ptype: str, reasons: list[str]) -> None:
        yield_rate = getattr(item, "yieldRate", None) or getattr(item, "grossYield", None)
        if yield_rate is not None:
            try:
                y_val = float(yield_rate)
                # 利回り未記載または未算出のゼロ値は許容
                # 一千万円未満の低廉投資物件のみ特例として上限千パーセントまで許容
                # それ以外の一般投資用不動産は上限百パーセントを維持
                price = getattr(item, "price", 0) or 0
                try:
                    price_val = float(price)
                except (ValueError, TypeError):
                    price_val = 0.0
                is_low_price_invest = price_val > 0 and price_val < 10000000.0
                max_yield = 1000.0 if is_low_price_invest else 100.0
                if y_val < 0 or y_val > max_yield:
                    reasons.append(f"利回り異常 ({y_val:.1f}%: 0%未満または{max_yield:.0f}%超)")
            except (ValueError, TypeError):
                reasons.append(f"利回り異常 ({yield_rate}: 数値変換不能)")


def tag_property_integrity(item: Any, property_type: str, company: str) -> tuple[bool, list[str]]:
    """
    保存後の共通整合性タグ付け。検証NGなら needs_parser_fix=True (オートヒール対象)、
    OKなら解消する。単件保存・バッチ保存・validate_data.py から共通利用。
    """
    from package.models.evaluation import PropertyEvaluation

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
