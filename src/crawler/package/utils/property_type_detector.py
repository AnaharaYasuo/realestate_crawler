# -*- coding: utf-8 -*-
import os
import re
import urllib.parse
import logging
from typing import Optional, Dict, Any

try:
    import google.generativeai as genai
except ImportError:
    genai = None


class PropertyTypeDetector:
    """
    URL・タイトル・HTML・スペック表から物件種別を総合判定する再利用可能モジュール
    判定優先度: Yield Guard (最優先) > specs > title > html_text > url > AI Fallback
    標準化出力: 'apartment' | 'mansion' | 'kodate' | 'tochi' | None
    """

    # 構造キーワード定数（SonarCloud S1192 重複排除）
    RC_STRUCTURE_KEYWORDS = ("RC", "SRC", "鉄筋", "コンクリート", "鉄骨")

    # 投資用絶対判定キーワード（最優先ガードレール）
    INVESTMENT_STRONG_SIGNALS = [
        "表面利回り", "実質利回り", "想定利回り", "現況利回り", "満室利回り", "満室時利回り",
        "利回り", "オーナーチェンジ", "サブリース", "想定年収", "満室想定", "年間予定賃料", "賃貸中"
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
    def _has_yield_signal(cls, text: Optional[str]) -> bool:
        """テキスト内に利回り表記や投資用シグナルが存在するか判定（Yield Guard）"""
        if not text or not isinstance(text, str):
            return False
        for sig in cls.INVESTMENT_STRONG_SIGNALS:
            if sig in text:
                return True
        return False

    @classmethod
    def _has_yield_signal_specs(cls, specs: Dict[str, Any]) -> bool:
        """スペック辞書内に利回り表記やgrossYieldが存在するか判定"""
        for k, v in specs.items():
            if cls._has_yield_signal(str(k)) or cls._has_yield_signal(str(v)):
                return True
            if "grossYield" in str(k) or "利回り" in str(k):
                try:
                    val = float(re.sub(r"[^\d.]", "", str(v)))
                    if val > 0:
                        return True
                except (ValueError, TypeError):
                    pass
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
    def _match_keywords(cls, text: str) -> Optional[str]:
        """テキストからキーワードマッチにより種別を特定（Yield Guard > apartment優先）"""
        if not text or not isinstance(text, str):
            return None

        if cls._has_yield_signal(text):
            return "apartment"

        for kw in cls.APARTMENT_KEYWORDS:
            if kw in text:
                return "apartment"

        for kw in cls.KODATE_KEYWORDS:
            if kw in text:
                return "kodate"

        for kw in cls.TOCHI_KEYWORDS:
            if kw in text:
                return "tochi"

        for kw in cls.MANSION_KEYWORDS:
            if kw in text:
                return "mansion"

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
        優先順位 (Yield Guard > specs > title > html_text > url > AI) に従って物件種別を判定
        """
        if specs and isinstance(specs, dict) and cls._has_yield_signal_specs(specs):
            return "apartment"

        if cls._has_yield_signal(title) or cls._has_yield_signal(html_text):
            return "apartment"

        if specs and isinstance(specs, dict):
            ptype = cls._detect_from_specs(specs)
            if ptype:
                return ptype

        if title:
            ptype = cls._match_keywords(title)
            if ptype:
                return ptype

        if html_text:
            ptype = cls._match_keywords(html_text)
            if ptype:
                return ptype

        if url:
            ptype = cls._detect_from_url(url)
            if ptype:
                return ptype

        if use_ai and (title or html_text or specs or url):
            return cls.detect_with_ai(
                url=url, title=title, html_text=html_text, specs=specs, default=default or "mansion"
            )

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
        同一物件（URLまたはタイトル/スペック）に対するAI呼び出しは1回のみに制限（インメモリキャッシュ）。
        事後サニタイザー (_sanitize_output) により利回り・物理制約を再検証。
        """
        # キャッシュキーの導出（SonarCloud S3358 三項演算子のネスト解消）
        if url and url.strip():
            cache_key = url.strip()
        elif title and title.strip():
            cache_key = title.strip()
        else:
            cache_key = f"{str(specs)}_{str(html_text)[:100]}"

        if cache_key in cls._ai_cache:
            return cls._ai_cache[cache_key]

        combined_text = f"URL: {url or ''}\nTitle: {title or ''}\nSpecs: {str(specs or '')}\nText: {(html_text or '')[:500]}"

        if cls._has_yield_signal(combined_text):
            cls._ai_cache[cache_key] = "apartment"
            return "apartment"

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or genai is None:
            cls._ai_cache[cache_key] = default
            return default

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = (
                "以下の不動産物件情報から、物件種別を以下のいずれか1つ（mansion / kodate / tochi / apartment）だけで回答してください。\n"
                "- mansion: 区分マンション、集合住宅の一室\n"
                "- kodate: 一戸建て、テラスハウス\n"
                "- tochi: 売地、更地、土地\n"
                "- apartment: 一棟アパート、一棟マンション、一棟ビル、収益物件、投資用物件\n\n"
                f"物件情報:\n{combined_text}\n\n"
                "回答は小文字の種別名（mansion, kodate, tochi, apartment）の英単語1語のみを出力してください。"
            )
            resp = model.generate_content(prompt)
            raw_ans = (getattr(resp, "text", "") or "").strip().lower()

            predicted = default
            for candidate in ("apartment", "kodate", "tochi", "mansion"):
                if candidate in raw_ans:
                    predicted = candidate
                    break

            final_res = cls._sanitize_output(predicted, text=combined_text)
            cls._ai_cache[cache_key] = final_res
            return final_res
        except Exception as e:
            logging.warning(f"PropertyTypeDetector: Gemini classification failed, fallback to '{default}': {e}")
            cls._ai_cache[cache_key] = default
            return default

    @classmethod
    def detect_from_object(cls, property_obj: Any) -> str:
        """
        dict または Django Model インスタンスから物件種別 ('mansion' | 'kodate' | 'apartment' | 'tochi') を判定。
        （ML推論パイプラインおよびクローラー保存処理での種別判定を共通化）
        """
        if property_obj is None:
            return "mansion"

        # 0. Yield Guard (最優先: grossYield > 0 または 物件名・備考の利回り表記)
        gross_yield = cls._get_field(property_obj, "grossYield")
        try:
            if gross_yield is not None and float(gross_yield) > 0:
                return "apartment"
        except (ValueError, TypeError):
            pass

        prop_name = str(cls._get_field(property_obj, "propertyName") or "")
        remarks = str(cls._get_field(property_obj, "remarks") or "")
        if cls._has_yield_signal(prop_name) or cls._has_yield_signal(remarks):
            return "apartment"

        # 1. 物理矛盾ガード: 土地面積0 + RC構造等は mansion
        if cls._is_rc_zero_land(property_obj):
            return "mansion"

        # 2. propertyType / クラス名による明示判定
        type_str = str(
            cls._get_field(property_obj, "propertyType") or property_obj.__class__.__name__
        ).lower()
        if "mansion" in type_str:
            return "mansion"
        if "kodate" in type_str:
            return "kodate"
        if "apartment" in type_str or "invest" in type_str:
            return "apartment"
        if "tochi" in type_str:
            return "tochi"

        # 3. スペック項目によるフォールバック推定
        if cls._get_field(property_obj, "senyuMenseki") is not None:
            return "mansion"
        if cls._get_field(property_obj, "tatemonoMenseki") is not None:
            return "apartment" if cls._get_field(property_obj, "grossYield") is not None else "kodate"
        if cls._get_field(property_obj, "tochiMenseki") is not None or cls._get_field(property_obj, "maguchi") is not None:
            return "tochi"

        return "mansion"

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
