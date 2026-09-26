# -*- coding: utf-8 -*-
import os
import re
import urllib.parse
import logging
from typing import Optional, Dict, Any

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


class PropertyTypeDetector:
    """
    URL・タイトル・HTML・スペック表から物件種別を総合判定する再利用可能モジュール
    判定優先度: Yield Guard (最優先) > specs > title > html_text > url > AI Fallback
    標準化出力: 'apartment' | 'mansion' | 'kodate' | 'tochi' | None
    """

    # 構造キーワード定数（SonarCloud S1192 重複排除）
    RC_STRUCTURE_KEYWORDS = ("RC", "SRC", "鉄筋", "コンクリート", "鉄骨")

    # 投資用絶対判定キーワード（最優先ガードレール）
    SIGNAL_ANNUAL_RENT_EST = "年間予定賃料"
    SIGNAL_GROSS_INCOME = "想定年収"
    SIGNAL_FULL_OCCUPANCY = "満室想定"
    INVESTMENT_STRONG_SIGNALS = [
        "表面利回り", "実質利回り", "想定利回り", "現況利回り", "満室利回り", "満室時利回り",
        "利回り", "オーナーチェンジ", "サブリース",
        SIGNAL_GROSS_INCOME, SIGNAL_FULL_OCCUPANCY, SIGNAL_ANNUAL_RENT_EST, "賃貸中",
    ]

    # 種別ごとの判定キーワード（複合語の優先順位を保つため順序に留意）
    APARTMENT_KEYWORDS = [
        "一棟売りアパート", "一棟アパート", "一棟売りマンション", "一棟マンション",
        "一棟売りビル", "一棟ビル", "収益アパート", "投資用アパート",
        "収益物件", "一棟売り", "一棟"
    ]

    MANSION_KEYWORDS = [
        "区分マンション", "中古マンション", "新築マンション", "区分所有",
        "ライオンズマンション", "パークホームズ", "マンション"
    ]

    KODATE_KEYWORDS = [
        "新築一戸建て", "中古一戸建て", "一戸建て", "新築一戸建", "中古一戸建",
        "一戸建", "新築戸建", "中古戸建", "テラスハウス", "戸建"
    ]

    TOCHI_KEYWORDS = [
        "売土地", "売り土地", "建築条件付土地", "売地", "土地"
    ]

    _ai_cache: Dict[str, str] = {}

    _YIELD_MARKERS = (
        "利回り",
        SIGNAL_GROSS_INCOME,
        SIGNAL_FULL_OCCUPANCY,
        SIGNAL_ANNUAL_RENT_EST,
        "想定年間収入",
    )
    _YIELD_SEP_CHARS = frozenset(" \t　:：=＝約")
    _YIELD_LABEL_SKIP = (
        "利回り", "表面利回り", "実質利回り", "想定利回り", "現況利回り",
        "満室利回り", "満室時利回り",
        SIGNAL_GROSS_INCOME, SIGNAL_FULL_OCCUPANCY, SIGNAL_ANNUAL_RENT_EST,
    )
    @classmethod
    def clear_ai_cache(cls) -> None:
        """テストやジョブ間リセット用のAI判定キャッシュクリア"""
        cls._ai_cache.clear()

    @staticmethod
    def _get_field(obj: Any, field_name: str, default: Any = None) -> Any:
        """dict または モデルオブジェクトからフィールド値を安全に取得"""
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(field_name, default)
        return getattr(obj, field_name, default)

    @classmethod
    def _has_numeric_yield(cls, text: str) -> bool:
        """利回り・想定年収など、数値が伴う収益指標があるか（ReDoS回避の単純走査）。"""
        for marker in cls._YIELD_MARKERS:
            start = 0
            while True:
                pos = text.find(marker, start)
                if pos < 0:
                    break
                i = pos + len(marker)
                while i < len(text) and text[i] in cls._YIELD_SEP_CHARS:
                    i += 1
                if i < len(text) and text[i].isdigit():
                    return True
                start = pos + 1
        return False

    @classmethod
    def _has_yield_signal(cls, text: Optional[str]) -> bool:
        """テキスト内に利回り表記や投資用シグナルが存在するか判定（Yield Guard）

        投資ポータルの共通ナビに「利回り」が含まれるだけの場合は投資確定にしない。
        利回り系は数値が伴う場合、またはオーナーチェンジ等の強いシグナルのみ True。
        """
        if not text or not isinstance(text, str):
            return False
        for sig in ("オーナーチェンジ", "サブリース", "賃貸中"):
            if sig in text:
                return True
        if cls._has_numeric_yield(text):
            return True
        # 残りの投資シグナル（利回り単体語を除く）
        for sig in cls.INVESTMENT_STRONG_SIGNALS:
            if sig in cls._YIELD_LABEL_SKIP:
                continue
            if sig in text:
                return True
        return False

    @classmethod
    def _is_empty_yield_value(cls, v_str: str) -> bool:
        empty_markers = ("", "-", "－", "―", "—", "−", "なし", "非公開", "未定", "－％", "-%")
        return v_str in empty_markers or v_str.startswith("未定")

    @classmethod
    def _gross_yield_positive(cls, v_str: str) -> bool:
        if cls._is_empty_yield_value(v_str):
            return False
        try:
            return float(re.sub(r"[^\d.]", "", v_str)) > 0
        except (ValueError, TypeError):
            return False

    @classmethod
    def _spec_entry_has_yield(cls, key_str: str, v_str: str) -> bool:
        if "grossYield" in key_str:
            return cls._gross_yield_positive(v_str)
        if "利回り" in key_str:
            return (not cls._is_empty_yield_value(v_str)
                    and cls._has_numeric_yield(f"{key_str}{v_str}"))
        if cls._has_yield_signal(v_str):
            return True
        # キー側ラベル（想定年収等）+ 値側数値を連結して判定
        return (
            not cls._is_empty_yield_value(v_str)
            and cls._has_numeric_yield(f"{key_str}{v_str}")
        )

    @classmethod
    def _has_yield_signal_specs(cls, specs: Dict[str, Any]) -> bool:
        """スペック辞書内に利回り表記やgrossYieldが存在するか判定（空欄・宣伝文の混入は除外）"""
        for k, v in specs.items():
            v_str = str(v).strip() if v is not None else ""
            if cls._spec_entry_has_yield(str(k), v_str):
                return True
        return False

    @classmethod
    def _is_rc_zero_land(cls, obj: Any) -> bool:
        """土地面積0かつRC/SRC構造等のマンション物理特徴を満たすか判定"""
        if obj is None:
            return False
        tochi = cls._get_field(obj, "tochiMenseki")
        try:
            tochi_val = float(tochi) if tochi is not None else None
        except (ValueError, TypeError):
            tochi_val = None

        if tochi_val is not None and tochi_val <= 0:
            senyu = cls._get_field(obj, "senyuMenseki")
            structure = str(cls._get_field(obj, "structure") or cls._get_field(obj, "kouzou") or "")
            if senyu or any(x in structure for x in cls.RC_STRUCTURE_KEYWORDS):
                return True
        return False

    @classmethod
    def _sanitize_output(cls, predicted_type: str, text: str = "", obj: Any = None) -> str:
        """AI出力や推定結果を事後サニタイズ（利回りガードおよび物理矛盾ガードの適用）"""
        if cls._has_yield_signal(text):
            return "apartment"

        if obj is not None:
            gross = cls._get_field(obj, "grossYield")
            try:
                if gross is not None and float(gross) > 0:
                    return "apartment"
            except (ValueError, TypeError):
                pass

        if predicted_type == "kodate" and cls._is_rc_zero_land(obj):
            return "mansion"

        return predicted_type

    @classmethod
    def _first_keyword_hit(cls, text: str, keywords) -> Optional[str]:
        for kw in keywords:
            if kw in text:
                return kw
        return None

    @classmethod
    def _match_keywords(cls, text: str) -> Optional[str]:
        """テキストからキーワードマッチにより種別を特定。

        売地等の土地シグナルがあり数値利回りが無い場合は tochi を優先
        （投資ポータルの共通文言「収益物件」より物件固有の売地を優先）。
        """
        if not text or not isinstance(text, str):
            return None

        has_strong_tochi = any(
            k in text for k in ("売地", "売土地", "売り土地", "建築条件付土地")
        )
        # 数値利回り・オーナーチェンジ等の実投資シグナルを売地より優先
        if cls._has_yield_signal(text):
            return "apartment"
        if has_strong_tochi:
            return "tochi"

        keyword_map = (
            (cls.APARTMENT_KEYWORDS, "apartment"),
            (cls.KODATE_KEYWORDS, "kodate"),
            (cls.TOCHI_KEYWORDS, "tochi"),
            (cls.MANSION_KEYWORDS, "mansion"),
        )
        for keywords, ptype in keyword_map:
            if cls._first_keyword_hit(text, keywords):
                return ptype
        return None

    @classmethod
    def _detect_from_specs(cls, specs: Dict[str, Any]) -> Optional[str]:
        """スペック表の特定キーおよび値全体から種別判定"""
        type_keys = ["物件種別", "種別", "建物種別", "物件タイプ", "種目"]
        for k in type_keys:
            if k in specs:
                ptype = cls._match_keywords(str(specs[k]))
                if ptype:
                    return ptype

        for val in specs.values():
            ptype = cls._match_keywords(str(val))
            if ptype:
                return ptype
        return None

    @classmethod
    def _detect_from_url(cls, url: str) -> Optional[str]:
        """URLのパス・クエリ・サブドメインから種別判定"""
        parsed = urllib.parse.urlparse(url)
        path_and_query = (parsed.path + "?" + parsed.query).lower()

        if any(k in path_and_query for k in ("toushi", "apartment", "tohshi", "invest")):
            return "apartment"
        if "mansion" in path_and_query:
            return "mansion"
        if any(k in path_and_query for k in ("kodate", "house", "ikkodate")):
            return "kodate"
        if any(k in path_and_query for k in ("tochi", "land")):
            return "tochi"
        if "toushi" in parsed.netloc.lower():
            return "apartment"
        return None

    @classmethod
    def _detect_rule_based(
        cls,
        url: Optional[str] = None,
        title: Optional[str] = None,
        html_text: Optional[str] = None,
        specs: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if specs and isinstance(specs, dict) and cls._has_yield_signal_specs(specs):
            return "apartment"
        if title:
            ptype = cls._match_keywords(title)
            if ptype:
                return ptype
        if cls._has_yield_signal(html_text):
            return "apartment"
        if specs and isinstance(specs, dict):
            ptype = cls._detect_from_specs(specs)
            if ptype:
                return ptype
        if html_text:
            ptype = cls._match_keywords(html_text)
            if ptype:
                return ptype
        if url:
            return cls._detect_from_url(url)
        return None

    @classmethod
    def detect(
        cls,
        url: Optional[str] = None,
        title: Optional[str] = None,
        html_text: Optional[str] = None,
        specs: Optional[Dict[str, Any]] = None,
        default: Optional[str] = None,
        use_ai: bool = False
    ) -> Optional[str]:
        """
        優先順位:
        数値利回り(specs) > タイトル種別(投資シグナル優先・売地はナビ文言より優先) >
        本文Yield Guard > specs種別 > 本文キーワード > url > AI
        """
        detected = cls._detect_rule_based(url=url, title=title, html_text=html_text, specs=specs)
        if detected:
            return detected

        if use_ai and any((title, html_text, specs, url)):
            return cls.detect_with_ai(
                url=url, title=title, html_text=html_text, specs=specs, default=default or "mansion"
            )

        return default

    @staticmethod
    def _compute_cache_key(
        url: Optional[str] = None,
        title: Optional[str] = None,
        html_text: Optional[str] = None,
        specs: Optional[Dict[str, Any]] = None
    ) -> str:
        """キャッシュキーの導出（SonarCloud S3358 三項演算子のネスト解消）"""
        if url and url.strip():
            return url.strip()
        if title and title.strip():
            return title.strip()
        return f"{str(specs)}_{str(html_text)[:100]}"

    @classmethod
    def _call_gemini_model(cls, prompt_text: str, default: str) -> str:
        """Gemini Flash API を呼び出して推論結果をパース"""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or genai is None:
            return default

        try:
            http_options = types.HttpOptions(timeout=10000) if types else None
            with genai.Client(api_key=api_key, http_options=http_options) as client:
                prompt = (
                    "以下の不動産物件情報から、物件種別を以下のいずれか1つ（mansion / kodate / tochi / apartment）だけで回答してください。\n"
                    "- mansion: 区分マンション、集合住宅の一室\n"
                    "- kodate: 一戸建て、テラスハウス\n"
                    "- tochi: 売地、更地、土地\n"
                    "- apartment: 一棟アパート、一棟マンション、一棟ビル、収益物件、投資用物件\n\n"
                    f"物件情報:\n{prompt_text}\n\n"
                    "回答は小文字の種別名（mansion, kodate, tochi, apartment）の英単語1語のみを出力してください。"
                )
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                )
                raw_ans = (getattr(resp, "text", "") or "").strip().lower()

                for candidate in ("apartment", "kodate", "tochi", "mansion"):
                    if candidate in raw_ans:
                        return candidate
                return default
        except Exception as e:
            logging.warning(f"PropertyTypeDetector: Gemini classification failed, fallback to '{default}': {e}")
            return default

    @classmethod
    def detect_with_ai(
        cls,
        url: Optional[str] = None,
        title: Optional[str] = None,
        html_text: Optional[str] = None,
        specs: Optional[Dict[str, Any]] = None,
        default: str = "mansion"
    ) -> str:
        """
        Gemini 1.5 Flash を用いた高精度分類フォールバック。
        同一物件に対するAI呼び出しは1回のみに制限（インメモリキャッシュ）。
        事後サニタイザー (_sanitize_output) により利回り・物理制約を再検証。
        """
        cache_key = cls._compute_cache_key(url, title, html_text, specs)
        if cache_key in cls._ai_cache:
            return cls._ai_cache[cache_key]

        combined_text = f"URL: {url or ''}\nTitle: {title or ''}\nSpecs: {str(specs or '')}\nText: {(html_text or '')[:500]}"

        if cls._has_yield_signal(combined_text):
            cls._ai_cache[cache_key] = "apartment"
            return "apartment"

        predicted = cls._call_gemini_model(combined_text, default)
        final_res = cls._sanitize_output(predicted, text=combined_text)
        cls._ai_cache[cache_key] = final_res
        return final_res

    @classmethod
    def _has_yield_in_object(cls, property_obj: Any) -> bool:
        """オブジェクト内の利回り表記またはgrossYield存在チェック"""
        gross_yield = cls._get_field(property_obj, "grossYield")
        try:
            if gross_yield is not None and float(gross_yield) > 0:
                return True
        except (ValueError, TypeError):
            pass

        prop_name = str(cls._get_field(property_obj, "propertyName") or "")
        remarks = str(cls._get_field(property_obj, "remarks") or "")
        return cls._has_yield_signal(prop_name) or cls._has_yield_signal(remarks)

    @classmethod
    def _detect_from_type_str(cls, type_str: str) -> Optional[str]:
        """propertyType や クラス名の文字列から種別を判定"""
        lower_str = (type_str or "").lower()
        if "mansion" in lower_str:
            return "mansion"
        if "kodate" in lower_str:
            return "kodate"
        if "apartment" in lower_str or "invest" in lower_str:
            return "apartment"
        if "tochi" in lower_str:
            return "tochi"
        return None

    @classmethod
    def _detect_from_area_fields(cls, property_obj: Any) -> str:
        """面積フィールド等の属性によるフォールバック種別推定"""
        if cls._get_field(property_obj, "senyuMenseki") is not None:
            return "mansion"
        if cls._get_field(property_obj, "tatemonoMenseki") is not None:
            return "apartment" if cls._get_field(property_obj, "grossYield") is not None else "kodate"
        if cls._get_field(property_obj, "tochiMenseki") is not None or cls._get_field(property_obj, "maguchi") is not None:
            return "tochi"
        return "mansion"

    @classmethod
    def detect_from_object(cls, property_obj: Any) -> str:
        """
        dict または Django Model インスタンスから物件種別 ('mansion' | 'kodate' | 'apartment' | 'tochi') を判定。
        （ML推論パイプラインおよびクローラー保存処理での種別判定を共通化）
        """
        if property_obj is None:
            return "mansion"

        # 0. Yield Guard (最優先: grossYield > 0 または 物件名・備考の利回り表記)
        if cls._has_yield_in_object(property_obj):
            return "apartment"

        # 1. 物理矛盾ガード: 土地面積0 + RC構造等は mansion
        if cls._is_rc_zero_land(property_obj):
            return "mansion"

        # 2. propertyType / クラス名による明示判定
        explicit_type = str(cls._get_field(property_obj, "propertyType") or property_obj.__class__.__name__)
        ptype = cls._detect_from_type_str(explicit_type)
        if ptype:
            return ptype

        # 3. スペック項目によるフォールバック推定
        return cls._detect_from_area_fields(property_obj)

    @classmethod
    def detect_investment_type(cls, text: str, default: str = "Apartment") -> str:
        """
        投資物件の表題・テキスト等から Apartment / Mansion / Building を判定。
        各投資用パーサーの重複実装を共通化。
        """
        if not text or not isinstance(text, str):
            return default
        if "アパート" in text:
            return "Apartment"
        if "マンション" in text or "レジ" in text:
            return "Mansion"
        if any(k in text for k in ["ビル", "店舗", "事務所"]):
            return "Building"
        return default

    @classmethod
    def is_investment(cls, ptype: Optional[str]) -> bool:
        """
        物件種別文字列が投資用（apartment / investment / invest）であるかを一元判定。
        Detector/Routerの標準種別 'apartment' およびパーサー種別 'investment' の両方に対応。
        """
        if not ptype:
            return False
        ptype_str = str(ptype).lower()
        return any(k in ptype_str for k in ("apartment", "investment", "invest"))

