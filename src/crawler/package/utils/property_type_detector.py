# -*- coding: utf-8 -*-
import os
import re
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
    def _sanitize_output(cls, predicted_type: str, text: str = "", obj: Any = None) -> str:
        """AI出力や推定結果を事後サニタイズ（利回りガードおよび物理矛盾ガードの適用）"""
        # 1. 利回り・収益シグナルの検知 -> 無条件で apartment
        if cls._has_yield_signal(text):
            return "apartment"
        if obj is not None:
            gross = getattr(obj, "grossYield", None) if not isinstance(obj, dict) else obj.get("grossYield", None)
            try:
                if gross is not None and float(gross) > 0:
                    return "apartment"
            except (ValueError, TypeError):
                pass

        # 2. 土地面積0 + RC構造 -> kodate禁止、mansion是正
        if predicted_type == "kodate" and obj is not None:
            tochi = getattr(obj, "tochiMenseki", None) if not isinstance(obj, dict) else obj.get("tochiMenseki", None)
            senyu = getattr(obj, "senyuMenseki", None) if not isinstance(obj, dict) else obj.get("senyuMenseki", None)
            structure = str(
                (getattr(obj, "structure", "") or getattr(obj, "kouzou", ""))
                if not isinstance(obj, dict)
                else (obj.get("structure", "") or obj.get("kouzou", ""))
            )
            try:
                tochi_val = float(tochi) if tochi is not None else None
            except (ValueError, TypeError):
                tochi_val = None
            if tochi_val is not None and tochi_val <= 0:
                if senyu or any(x in structure for x in ["RC", "SRC", "鉄筋", "コンクリート", "鉄骨"]):
                    return "mansion"

        return predicted_type

    @classmethod
    def _match_keywords(cls, text: str) -> Optional[str]:
        """テキストからキーワードマッチにより種別を特定（Yield Guard > apartment優先）"""
        if not text or not isinstance(text, str):
            return None

        # 0. 利回り・収益指標ガード (Yield Guard)
        if cls._has_yield_signal(text):
            return "apartment"

        # 1. 一棟・アパート・投資用（「一棟マンション」を「マンション」より優先）
        for kw in cls.APARTMENT_KEYWORDS:
            if kw in text:
                return "apartment"

        # 2. 戸建
        for kw in cls.KODATE_KEYWORDS:
            if kw in text:
                return "kodate"

        # 3. 土地
        for kw in cls.TOCHI_KEYWORDS:
            if kw in text:
                return "tochi"

        # 4. マンション（区分・一般）
        for kw in cls.MANSION_KEYWORDS:
            if kw in text:
                return "mansion"

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
        # 0. Yield Guard (利回り表記の最優先検知)
        if specs and isinstance(specs, dict):
            for k, v in specs.items():
                if cls._has_yield_signal(str(k)) or cls._has_yield_signal(str(v)):
                    return "apartment"
                if "grossYield" in str(k) or "利回り" in str(k):
                    try:
                        val = float(re.sub(r"[^\d.]", "", str(v)))
                        if val > 0:
                            return "apartment"
                    except (ValueError, TypeError):
                        pass

        if cls._has_yield_signal(title) or cls._has_yield_signal(html_text):
            return "apartment"

        # 1. specs 辞書からの判定 (最優先)
        if specs and isinstance(specs, dict):
            # 物件種別関連のキーを優先確認
            type_keys = ["物件種別", "種別", "建物種別", "物件タイプ", "種目"]
            for k in type_keys:
                if k in specs:
                    ptype = cls._match_keywords(str(specs[k]))
                    if ptype:
                        return ptype
            # specs 全体の値も確認
            for val in specs.values():
                ptype = cls._match_keywords(str(val))
                if ptype:
                    return ptype

        # 2. ページタイトルからの判定
        if title:
            ptype = cls._match_keywords(title)
            if ptype:
                return ptype

        # 3. HTML 本文・パンくずテキストからの判定
        if html_text:
            ptype = cls._match_keywords(html_text)
            if ptype:
                return ptype

        # 4. URL パス・クエリからの判定
        if url:
            import urllib.parse
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

            # サブドメインの特化判定 (例: toushi.homes.co.jp)
            if "toushi" in parsed.netloc.lower():
                return "apartment"

        # 5. ルールで特定不能な場合の AI フォールバック
        if use_ai and (title or html_text or specs or url):
            return cls.detect_with_ai(
                url=url, title=title, html_text=html_text, specs=specs, default=default or "mansion"
            )

        return default

    _ai_cache: Dict[str, str] = {}

    @classmethod
    def clear_ai_cache(cls) -> None:
        """テストやジョブ間リセット用のAI判定キャッシュクリア"""
        cls._ai_cache.clear()

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
        # キャッシュキーの導出（URL優先、なければタイトルやスペック表ハッシュ）
        cache_key = (
            url.strip() if url
            else (title.strip() if title else None)
        ) or f"{str(specs)}_{str(html_text)[:100]}"

        if cache_key in cls._ai_cache:
            return cls._ai_cache[cache_key]

        combined_text = f"URL: {url or ''}\nTitle: {title or ''}\nSpecs: {str(specs or '')}\nText: {(html_text or '')[:500]}"

        # 事前 Yield Guard
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

            # 事後サニタイザー
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

        if isinstance(property_obj, dict):
            return cls._detect_from_dict(property_obj)
        return cls._detect_from_django(property_obj)

    @classmethod
    def _detect_from_dict(cls, property_obj: Dict[str, Any]) -> str:
        # 0. Yield Guard（最優先: grossYield > 0 または 物件名・備考の利回り表記）
        gross_yield = property_obj.get("grossYield", None)
        try:
            if gross_yield is not None and float(gross_yield) > 0:
                return "apartment"
        except (ValueError, TypeError):
            pass

        prop_name = str(property_obj.get("propertyName", "") or "")
        remarks = str(property_obj.get("remarks", "") or "")
        if cls._has_yield_signal(prop_name) or cls._has_yield_signal(remarks):
            return "apartment"

        tochi = property_obj.get("tochiMenseki", None)
        senyu = property_obj.get("senyuMenseki", None)
        structure = str(property_obj.get("structure", "") or property_obj.get("kouzou", "") or "")
        try:
            tochi_val = float(tochi) if tochi is not None else None
        except (ValueError, TypeError):
            tochi_val = None
        if tochi_val is not None and tochi_val <= 0:
            if senyu or any(x in structure for x in ["RC", "SRC", "鉄筋", "コンクリート", "鉄骨"]):
                return "mansion"

        ptype = str(property_obj.get("propertyType", "")).lower()
        if "mansion" in ptype:
            return "mansion"
        if "kodate" in ptype:
            return "kodate"
        if "apartment" in ptype or "invest" in ptype:
            return "apartment"
        if "tochi" in ptype:
            return "tochi"

        if "senyuMenseki" in property_obj:
            return "mansion"
        if "tatemonoMenseki" in property_obj:
            if "grossYield" in property_obj:
                return "apartment"
            return "kodate"
        if "tochiMenseki" in property_obj or "maguchi" in property_obj:
            return "tochi"
        return "mansion"

    @classmethod
    def _detect_from_django(cls, property_obj: Any) -> str:
        # 0. Yield Guard（最優先: grossYield > 0 または 物件名・備考の利回り表記）
        gross_yield = getattr(property_obj, "grossYield", None)
        try:
            if gross_yield is not None and float(gross_yield) > 0:
                return "apartment"
        except (ValueError, TypeError):
            pass

        prop_name = str(getattr(property_obj, "propertyName", "") or "")
        remarks = str(getattr(property_obj, "remarks", "") or "")
        if cls._has_yield_signal(prop_name) or cls._has_yield_signal(remarks):
            return "apartment"

        tochi = getattr(property_obj, "tochiMenseki", None)
        senyu = getattr(property_obj, "senyuMenseki", None)
        structure = str(getattr(property_obj, "structure", "") or getattr(property_obj, "kouzou", "") or "")
        try:
            tochi_val = float(tochi) if tochi is not None else None
        except (ValueError, TypeError):
            tochi_val = None
        if tochi_val is not None and tochi_val <= 0:
            if senyu or any(x in structure for x in ["RC", "SRC", "鉄筋", "コンクリート", "鉄骨"]):
                return "mansion"

        class_name = property_obj.__class__.__name__.lower()
        if "mansion" in class_name:
            return "mansion"
        elif "kodate" in class_name:
            return "kodate"
        elif "apartment" in class_name or "invest" in class_name:
            return "apartment"
        elif "tochi" in class_name:
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
        elif "マンション" in text or "レジ" in text:
            return "Mansion"
        elif any(k in text for k in ["ビル", "店舗", "事務所"]):
            return "Building"
        return default
