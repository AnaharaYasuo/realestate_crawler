import logging
import os
import re
import time
import urllib.parse
from typing import Any, ClassVar

try:
    from package.utils.newrelic_helper import record_llm_event as _record_llm_event
except Exception:  # noqa: BLE001
    _record_llm_event = None  # type: ignore[assignment]

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

    KW_ITTO_URI_APARTMENT = "一棟売りアパート"
    KW_ITTO_APARTMENT = "一棟アパート"
    KW_ITTO_URI_MANSION = "一棟売りマンション"
    KW_ITTO_MANSION = "一棟マンション"
    KW_ITTO_URI_BUILDING = "一棟売りビル"
    KW_MANSION = "マンション"
    KW_TERRACE_HOUSE = "テラスハウス"

    KW_PROPERTY_TYPE_LABEL = "物件タイプ"
    SPECS_PROPERTY_TYPE_KEYS = ("物件種別", "種別", "建物種別", "種目", KW_PROPERTY_TYPE_LABEL)

    ITTO_KEYWORDS = (
        KW_ITTO_URI_APARTMENT, KW_ITTO_APARTMENT, KW_ITTO_URI_MANSION, KW_ITTO_MANSION,
        KW_ITTO_URI_BUILDING, "一棟ビル", "一棟売り", "一棟",
    )

    # 種別ごとの判定キーワード（複合語の優先順位を保つため順序に留意）
    APARTMENT_KEYWORDS = [
        KW_ITTO_URI_APARTMENT, KW_ITTO_APARTMENT, KW_ITTO_URI_MANSION, KW_ITTO_MANSION,
        KW_ITTO_URI_BUILDING, "一棟ビル", "収益アパート", "投資用アパート",
        "収益物件", "一棟売り", "一棟"
    ]

    MANSION_KEYWORDS = [
        "区分マンション", "中古マンション", "新築マンション", "区分所有",
        "ライオンズマンション", "パークホームズ", KW_MANSION
    ]

    KODATE_KEYWORDS = [
        "新築一戸建て", "中古一戸建て", "一戸建て", "新築一戸建", "中古一戸建",
        "一戸建", "新築戸建", "中古戸建", KW_TERRACE_HOUSE, "戸建"
    ]

    TOCHI_KEYWORDS = [
        "売土地", "売り土地", "建築条件付土地", "売地"
    ]



    _ai_cache: ClassVar[dict[str, str]] = {}

    _TOCHI_EXCLUDED_TERMS = ("土地権利", "土地面積", "土地代", "土地付き", "土地・建物", "土地建物")

    @classmethod
    def _is_isolated_tochi(cls, text: str) -> bool:
        """「土地」が「土地権利」「土地面積」等の除外フレーズの一部でない独立した出現を含むか判定"""
        if not text or "土地" not in text:
            return False
        # 除外フレーズを置換して残りに「土地」が含まれるか確認
        clean = text
        for term in cls._TOCHI_EXCLUDED_TERMS:
            clean = clean.replace(term, "")
        return "土地" in clean

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
    def _has_yield_signal(cls, text: str | None) -> bool:
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
    def _has_yield_signal_specs(cls, specs: dict[str, Any]) -> bool:
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
    def _first_keyword_hit(cls, text: str, keywords) -> str | None:
        for kw in keywords:
            if kw in text:
                return kw
        return None

    @classmethod
    def _match_keywords(cls, text: str) -> str | None:
        """テキストからキーワードマッチにより種別を特定。

        売地等の土地シグナルがあり数値利回りが無い場合は tochi を優先
        （投資ポータルの共通文言「収益物件」より物件固有の売地を優先）。
        """
        if not text or not isinstance(text, str):
            return None

        has_definite_tochi = any(
            k in text for k in ("売地", "売土地", "売り土地", "建築条件付土地")
        )
        # 数値利回り・オーナーチェンジ等の実投資シグナルを売地より優先
        if cls._has_yield_signal(text):
            if cls._first_keyword_hit(text, cls.KODATE_KEYWORDS):
                return "invest_kodate"
            return "apartment"
        if has_definite_tochi:
            return "tochi"

        # 建物キーワードを先に判定（「一棟アパート 土地・建物」や単独「土地」混在時の建物優先）
        if cls._first_keyword_hit(text, cls.APARTMENT_KEYWORDS):
            return "apartment"
        if cls._first_keyword_hit(text, cls.KODATE_KEYWORDS):
            return "kodate"
        if cls._is_isolated_tochi(text) or cls._first_keyword_hit(text, cls.TOCHI_KEYWORDS):
            return "tochi"
        if cls._first_keyword_hit(text, cls.MANSION_KEYWORDS):
            return "mansion"
        return None

    FREE_TEXT_SPEC_KEYS = (
        "備考", "remarks", "PR", "コメント", "おすすめ", "ポイント",
        "周辺", "環境", "交通", "アクセス", "学区", "設備", "特徴", "その他",
    )

    @classmethod
    def _is_free_text_spec_key(cls, key_str: str) -> bool:
        if key_str in cls.SPECS_PROPERTY_TYPE_KEYS:
            return False
        return any(ft in key_str for ft in cls.FREE_TEXT_SPEC_KEYS)

    _NEIGHBORHOOD_NOISE_PHRASES = ("用地に最適", "用地として", "徒歩", "の隣", "近隣", "周辺")

    @classmethod
    def _strip_neighborhood_noise(cls, text: str) -> str:
        clauses = re.split(r"[。、！!\s]+", text)
        kept = [c for c in clauses if c and not any(p in c for p in cls._NEIGHBORHOOD_NOISE_PHRASES)]
        return " ".join(kept)

    @classmethod
    def _detect_from_priority_spec_keys(cls, specs: dict[str, Any]) -> str | None:
        for k in cls.SPECS_PROPERTY_TYPE_KEYS:
            if k not in specs:
                continue
            val_str = str(specs[k]).strip()
            if val_str == "土地":
                return "tochi"
            ptype = cls._match_keywords(val_str)
            if ptype:
                return ptype
        return None

    @classmethod
    def _is_pure_land_from_spec_areas(cls, specs: dict[str, Any]) -> bool:
        has_land = cls._is_positive_area_value(specs.get("土地面積") or specs.get("tochiMenseki"))
        has_bldg = cls._is_positive_area_value(
            specs.get("建物面積") or specs.get("tatemonoMenseki") or specs.get("延床面積")
        )
        has_senyu = cls._is_positive_area_value(specs.get("専有面積") or specs.get("senyuMenseki"))
        return bool(has_land and not has_bldg and not has_senyu)

    @classmethod
    def _detect_from_specs(cls, specs: dict[str, Any]) -> str | None:
        """スペック表の特定キーおよび自由記述ノイズを除外した値から種別判定"""
        priority_hit = cls._detect_from_priority_spec_keys(specs)
        if priority_hit:
            return priority_hit

        for k, val in specs.items():
            if not cls._is_free_text_spec_key(str(k)):
                ptype = cls._match_keywords(str(val))
                if ptype:
                    return ptype

        if cls._is_pure_land_from_spec_areas(specs):
            return "tochi"

        for k, val in specs.items():
            if cls._is_free_text_spec_key(str(k)):
                cleaned_val = cls._strip_neighborhood_noise(str(val))
                ptype = cls._match_keywords(cleaned_val)
                if ptype:
                    return ptype
        return None


    @classmethod
    def _detect_from_url(cls, url: str) -> str | None:
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
    def _detect_from_specs_rule(cls, specs: dict[str, Any] | None) -> str | None:
        if not specs or not isinstance(specs, dict):
            return None
        if cls._has_yield_signal_specs(specs):
            return "apartment"
        return cls._detect_from_specs(specs)

    @classmethod
    def _detect_rule_based(
        cls,
        url: str | None = None,
        title: str | None = None,
        html_text: str | None = None,
        specs: dict[str, Any] | None = None,
    ) -> str | None:
        specs_ptype = cls._detect_from_specs_rule(specs)
        if specs_ptype == "apartment":
            if title and cls._first_keyword_hit(title, cls.KODATE_KEYWORDS):
                return "invest_kodate"
            return "apartment"
        if title:
            title_ptype = cls._match_keywords(title)
            if title_ptype:
                return title_ptype

        # 数値付き利回りはURL（/mansion/等）よりも強い投資シグナルとして最優先
        if html_text and cls._has_numeric_yield(html_text):
            return "apartment"
        # 明示的なスペック種別（物件種別: 区分マンション等）はURLより優先
        if specs_ptype:
            return specs_ptype
        if url:
            url_ptype = cls._detect_from_url(url)
            if url_ptype:
                return url_ptype
        if cls._has_yield_signal(html_text):
            return "apartment"
        return cls._match_keywords(html_text) if html_text else None




    @classmethod
    def detect(
        cls,
        url: str | None = None,
        title: str | None = None,
        html_text: str | None = None,
        specs: dict[str, Any] | None = None,
        default: str | None = None,
        use_ai: bool = False
    ) -> str | None:
        """
        優先順位:
        数値利回り(specs) > タイトル種別(投資シグナル優先・売地はナビ文言より優先) >
        本文Yield Guard > specs種別 > 本文キーワード > url > AI
        """
        # 0. 区分投資マンション保護: 利回りがあっても専有面積や階数があれば mansion
        # ただしタイトルに一棟アパート・戸建・土地等の明確な他種別キーワードが含まれる場合はスキップ
        title_has_itto_kw = bool(title and (any(k in title for k in cls.ITTO_KEYWORDS) or "アパート" in title))
        title_has_non_mansion = bool(title and (
            title_has_itto_kw or
            any(k in title for k in cls.KODATE_KEYWORDS) or
            any(k in title for k in cls.TOCHI_KEYWORDS) or
            "売地" in title
        ))
        if not title_has_non_mansion and specs and cls._is_unit_mansion_indicator(specs):
            return "mansion"

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
        url: str | None = None,
        title: str | None = None,
        html_text: str | None = None,
        specs: dict[str, Any] | None = None
    ) -> str:
        """キャッシュキーの導出（SonarCloud S3358 三項演算子のネスト解消）"""
        if url and url.strip():
            return url.strip()
        if title and title.strip():
            return title.strip()
        return f"{specs!s}_{str(html_text)[:100]}"

    @staticmethod
    def _record_gemini_telemetry(
        model: str,
        duration_ms: float,
        resp: Any = None,
        error: Exception | None = None,
    ) -> None:
        """SonarCloud S3776: テレメトリ記録処理を分離して認知複雑度を15以下に抑制"""
        if not _record_llm_event:
            return
        if error is not None:
            _record_llm_event(
                model_name=model,
                prompt_tokens=0,
                completion_tokens=0,
                duration_ms=duration_ms,
                status="error",
                error_msg=str(error)[:200],
                metadata={"caller": "property_type_detector"},
            )
            return

        usage = getattr(resp, "usage_metadata", None)
        _record_llm_event(
            model_name=model,
            prompt_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            completion_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            duration_ms=round(duration_ms, 1),
            status="success",
            metadata={"caller": "property_type_detector"},
        )

    @classmethod
    def _call_gemini_model(cls, prompt_text: str, default: str) -> str:
        """Gemini Flash API を呼び出して推論結果をパース"""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or genai is None:
            return default

        _model = "gemini-2.5-flash"
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
                _t0 = time.time()
                resp = client.models.generate_content(
                    model=_model,
                    contents=prompt,
                )
                _duration_ms = (time.time() - _t0) * 1000
                raw_ans = (getattr(resp, "text", "") or "").strip().lower()

                cls._record_gemini_telemetry(_model, _duration_ms, resp=resp)

                for candidate in ("apartment", "kodate", "tochi", "mansion"):
                    if candidate in raw_ans:
                        return candidate
                return default
        except Exception as e:
            _elapsed_ms = round((time.time() - _t0) * 1000, 1) if "_t0" in locals() else 0.0
            cls._record_gemini_telemetry(_model, _elapsed_ms, error=e)
            logging.warning(f"PropertyTypeDetector: Gemini classification failed, fallback to '{default}': {e}")
            return default

    @classmethod
    def detect_with_ai(
        cls,
        url: str | None = None,
        title: str | None = None,
        html_text: str | None = None,
        specs: dict[str, Any] | None = None,
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

        combined_text = f"URL: {url or ''}\nTitle: {title or ''}\nSpecs: {specs or ''!s}\nText: {(html_text or '')[:500]}"

        if cls._has_yield_signal(combined_text):
            cls._ai_cache[cache_key] = "apartment"
            return "apartment"

        predicted = cls._call_gemini_model(combined_text, default)
        final_res = cls._sanitize_output(predicted, text=combined_text)
        cls._ai_cache[cache_key] = final_res
        return final_res

    @classmethod
    def _check_specs_yield(cls, property_obj: Any) -> bool:
        """辞書またはオブジェクトのspecsから利回りシグナルを抽出"""
        if isinstance(property_obj, dict):
            if cls._has_yield_signal_specs(property_obj):
                return True
            inner_specs = property_obj.get("specs")
            return isinstance(inner_specs, dict) and cls._has_yield_signal_specs(inner_specs)
        specs = cls._get_field(property_obj, "specs")
        return isinstance(specs, dict) and cls._has_yield_signal_specs(specs)

    @classmethod
    def _has_yield_in_object(cls, property_obj: Any) -> bool:
        """オブジェクト内の利回り表記またはgrossYield存在チェック"""
        gross_yield = cls._get_field(property_obj, "grossYield")
        try:
            if gross_yield is not None and float(gross_yield) > 0:
                return True
        except (ValueError, TypeError):
            pass

        prop_name = str(cls._get_field(property_obj, "propertyName") or cls._get_field(property_obj, "物件名") or "")
        remarks = str(cls._get_field(property_obj, "remarks") or cls._get_field(property_obj, "備考") or "")
        if cls._has_yield_signal(prop_name) or cls._has_yield_signal(remarks):
            return True

        return cls._check_specs_yield(property_obj)

    @classmethod
    def _detect_from_type_str(cls, type_str: str) -> str | None:
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

    @staticmethod
    def _is_positive_area_value(val: Any) -> bool:
        if val is None:
            return False
        try:
            cleaned = re.sub(r"[^\d.]", "", str(val))
            return bool(cleaned and float(cleaned) > 0)
        except (ValueError, TypeError):
            return False

    @classmethod
    def _is_unit_floor_indicator(cls, property_obj: Any) -> bool:
        """所在階の判定（「階建」「階数」「地上○階」などの建物全体階数表記は除外）"""
        for f in ("所在階", "floor", "kaisuStr"):
            val = str(cls._get_field(property_obj, f) or "").strip()
            if not val or "階" not in val:
                continue
            if any(x in val for x in ("階建", "階数", "地上", "地下", "全体")):
                continue
            return True
        return False

    @classmethod
    def _has_explicit_non_mansion_indicator(cls, property_obj: Any) -> bool:
        """明示的な一棟アパート・戸建・土地の指定があるか確認（区分判定の上書きを防止）"""
        name = str(cls._get_field(property_obj, "propertyName") or cls._get_field(property_obj, "物件名") or "")
        explicit_type = str(cls._get_field(property_obj, "propertyType") or "")
        for k in cls.SPECS_PROPERTY_TYPE_KEYS:
            explicit_type += " " + str(cls._get_field(property_obj, k) or "")

        # 英語/日本語の明示的種別判定（Apartment, Kodate, Tochi 等）
        detected_explicit = cls._detect_from_type_str(explicit_type)
        if detected_explicit in ("apartment", "kodate", "tochi"):
            return True

        combined = f"{name} {explicit_type}"
        has_apartment = any(kw in combined for kw in cls.ITTO_KEYWORDS) or "アパート" in combined
        has_kodate = any(kw in combined for kw in cls.KODATE_KEYWORDS)
        has_tochi = any(kw in combined for kw in cls.TOCHI_KEYWORDS) or "売地" in combined
        return has_apartment or has_kodate or has_tochi

    @classmethod
    def _is_unit_mansion_indicator(cls, property_obj: Any) -> bool:
        """区分マンションの判定指標（専有面積、所在階、区分・一室表記）があるか"""
        if cls._has_explicit_non_mansion_indicator(property_obj):
            return False

        # 土地面積と建物面積（または延床面積）の双方が正の値を持つ場合、区分所有ではなく一棟/戸建/土地建物複合物件
        has_tochi = cls._is_positive_area_value(cls._get_field(property_obj, "tochiMenseki") or cls._get_field(property_obj, "土地面積"))
        has_tatemono = (
            cls._is_positive_area_value(cls._get_field(property_obj, "tatemonoMenseki") or cls._get_field(property_obj, "tatemonMenseki") or cls._get_field(property_obj, "建物面積"))
            or cls._is_positive_area_value(cls._get_field(property_obj, "nobeyukaMenseki") or cls._get_field(property_obj, "延床面積"))
        )
        if has_tochi and has_tatemono:
            return False

        for f in (
            "senyuMenseki", "専有面積", "壁芯面積",
            "kanrihi", "管理費", "syuzenTsumitate", "修繕積立金",
            "balconyMenseki", "バルコニー面積",
        ):
            if cls._is_positive_area_value(cls._get_field(property_obj, f)):
                return True

        if cls._is_unit_floor_indicator(property_obj):
            return True

        name = str(cls._get_field(property_obj, "propertyName") or cls._get_field(property_obj, "物件名") or "")
        return any(k in name for k in ("区分", "一室", "号室"))

    @classmethod
    def _is_commercial_building_indicator(cls, property_obj: Any) -> bool:
        """商業ビル・一棟売りビルの判定指標があるか"""
        name = str(cls._get_field(property_obj, "propertyName") or cls._get_field(property_obj, "物件名") or "")
        remarks = str(cls._get_field(property_obj, "remarks") or cls._get_field(property_obj, "備考") or "")
        combined = f"{name} {remarks}"
        return any(k in combined for k in ("一棟ビル", cls.KW_ITTO_URI_BUILDING, "売ビル", "商業ビル", "オフィスビル", "一棟貸し", "空ビル"))

    @classmethod
    def _detect_from_area_fields(cls, property_obj: Any) -> str:
        """面積フィールド等の属性によるフォールバック種別推定"""
        if cls._is_commercial_building_indicator(property_obj):
            return "apartment"
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

        # 0. 商業ビル・一棟売りビル保護: 専有面積があってもオフィスビル・売ビルは apartment
        if cls._is_commercial_building_indicator(property_obj):
            return "apartment"

        # 1. 区分投資マンション保護: 利回りがあっても専有面積や階数があれば mansion
        if cls._is_unit_mansion_indicator(property_obj):
            return "mansion"

        # 2. Yield Guard (最優先: grossYield > 0 または 物件名・備考の利回り表記)
        if cls._has_yield_in_object(property_obj):
            prop_name = str(cls._get_field(property_obj, "propertyName") or cls._get_field(property_obj, "物件名") or "")
            if any(k in prop_name for k in ("戸建", "一戸建て", "一戸建", "テラスハウス", "貸家")):
                return "invest_kodate"
            return "apartment"

        # 3. 物理矛盾ガード: 土地面積0 + RC構造等は mansion
        if cls._is_rc_zero_land(property_obj):
            return "mansion"

        # 4. propertyType / クラス名による明示判定
        explicit_type = str(cls._get_field(property_obj, "propertyType") or property_obj.__class__.__name__)
        ptype = cls._detect_from_type_str(explicit_type)
        if ptype:
            return ptype

        # 5. スペック項目によるフォールバック推定
        return cls._detect_from_area_fields(property_obj)

    @classmethod
    def _detect_invest_from_specs(cls, specs: dict[str, Any] | None) -> str | None:
        if not specs or not isinstance(specs, dict):
            return None
        for k in cls.SPECS_PROPERTY_TYPE_KEYS:
            v = str(specs.get(k) or "")
            if any(x in v for x in ("ビル", "店舗", "事務所")):
                return "Building"
            if any(x in v for x in (cls.KW_ITTO_MANSION, cls.KW_ITTO_URI_MANSION, cls.KW_ITTO_APARTMENT, cls.KW_ITTO_URI_APARTMENT, "アパート")):
                return "Apartment"
            if any(x in v for x in ("戸建て", "戸建", "一戸建", "一戸建て", cls.KW_TERRACE_HOUSE)):
                return "Kodate"
            if any(x in v for x in (cls.KW_MANSION, "レジ", "区分")):
                return "Mansion"
        return None

    @classmethod
    def _detect_invest_from_text(cls, text: str | None, default: str) -> str:
        if not text or not isinstance(text, str):
            return default
        if any(k in text for k in ("ビル", "店舗", "事務所")):
            return "Building"
        if any(k in text for k in (cls.KW_ITTO_MANSION, cls.KW_ITTO_URI_MANSION, cls.KW_ITTO_APARTMENT, cls.KW_ITTO_URI_APARTMENT, "アパート")):
            return "Apartment"
        if any(k in text for k in ("戸建て", "戸建", cls.KW_TERRACE_HOUSE, "一戸建")):
            return "Kodate"
        if cls.KW_MANSION in text or "レジ" in text:
            return "Mansion"
        return default



    @classmethod
    def detect_investment_type(
        cls,
        text: str | None = None,
        specs: dict[str, Any] | None = None,
        default: str = "Apartment"
    ) -> str:
        """
        投資物件の表題・スペック表等から Apartment / Mansion / Kodate / Building を判定。
        各投資用パーサーの重複実装を共通化。
        """
        # タイトルに具体的なビル・店舗・事務所表記がある場合は、specsの汎用種別より優先
        if text and isinstance(text, str) and any(
            k in text for k in ("ビル", "店舗", "事務所", "区分店舗", "区分事務所")
        ):
            return "Building"

        # タイトルに一棟マンション/一棟売り等の具体的な一棟表記がある場合は、specsの汎用「マンション」より優先
        if text and isinstance(text, str) and any(
            k in text for k in (cls.KW_ITTO_MANSION, cls.KW_ITTO_URI_MANSION, cls.KW_ITTO_APARTMENT, cls.KW_ITTO_URI_APARTMENT)
        ):
            return "Apartment"

        res_specs = cls._detect_invest_from_specs(specs)
        if res_specs:
            return res_specs
        res_text = cls._detect_invest_from_text(text, default="")
        if res_text:
            return res_text
        if specs and isinstance(specs, dict) and specs.get("専有面積"):
            return "Mansion"
        return default




    @classmethod
    def is_investment(cls, ptype: str | None) -> bool:
        """
        物件種別文字列が投資用（apartment / investment / invest）であるかを一元判定。
        Detector/Routerの標準種別 'apartment' およびパーサー種別 'investment' の両方に対応。
        """
        if not ptype:
            return False
        ptype_str = str(ptype).lower()
        return any(k in ptype_str for k in ("apartment", "investment", "invest"))

    _NOISE_TAGS = frozenset({"header", "nav", "footer", "aside", "script", "style", "noscript"})
    _NOISE_ATTR_TOKENS = ("gnav", "site-header", "sidebar", "recommend", "breadcrumb", "footer")
    _NON_RESIDENTIAL_KEYWORDS = (
        "オフィスビル", "商業ビル", "一棟売りビル", "一棟ビル", "売ビル",
        "店舗・事務所", "区分店舗", "区分事務所", "倉庫", "工場", "駐車場",
    )

    @classmethod
    def _is_noise_element(cls, tag: Any) -> bool:
        name = getattr(tag, "name", None)
        if not name:
            return False
        if name.lower() in cls._NOISE_TAGS:
            return True
        attrs = getattr(tag, "attrs", None) or {}
        classes = " ".join(attrs.get("class") or []) if isinstance(attrs.get("class"), list) else str(attrs.get("class") or "")
        el_id = str(attrs.get("id") or "")
        combined = f"{classes} {el_id}".lower()
        return any(tok in combined for tok in cls._NOISE_ATTR_TOKENS)

    @classmethod
    def _has_noise_ancestor(cls, node: Any) -> bool:
        curr = getattr(node, "parent", None)
        while curr is not None and getattr(curr, "name", None) is not None:
            if cls._is_noise_element(curr):
                return True
            curr = getattr(curr, "parent", None)
        return False

    @classmethod
    def extract_clean_body_text(cls, soup: Any, max_chars: int = 2000) -> str:
        """Layer 1: Strip global header/nav/footer/sidebar/recommendation noise before text detection."""
        if soup is None:
            return ""
        if isinstance(soup, str) or not hasattr(soup, "find_all"):
            return str(soup)[:max_chars]

        chunks: list[str] = []
        total_len = 0
        for text_node in soup.find_all(string=True):
            if cls._has_noise_ancestor(text_node):
                continue
            s = str(text_node).strip()
            if not s:
                continue
            chunks.append(s)
            total_len += len(s) + 1
            if total_len >= max_chars:
                break
        return " ".join(chunks)[:max_chars]

    @classmethod
    def detect_physical_and_tenancy(
        cls,
        url: str | None = None,
        title: str | None = None,
        html_text: str | None = None,
        specs: dict[str, Any] | None = None,
        obj: Any = None,
    ) -> dict[str, Any]:
        """Layer 2: Orthogonal classification of physical structure vs tenancy/investment status."""
        physical = (
            cls.detect_from_object(obj)
            if obj is not None
            else (cls.detect(url=url, title=title, html_text=html_text, specs=specs) or "mansion")
        )
        combined = f"{title or ''} {html_text or ''} {specs or ''!s}"
        if obj is not None:
            combined += f" {cls._get_field(obj, 'propertyName') or ''} {cls._get_field(obj, 'remarks') or ''}"
        is_tenanted = (
            cls._has_yield_signal(combined)
            or (isinstance(specs, dict) and cls._has_yield_signal_specs(specs))
            or (obj is not None and cls._has_yield_in_object(obj))
        )
        is_non_res = any(kw in combined for kw in cls._NON_RESIDENTIAL_KEYWORDS)
        return {
            "physical_type": physical,
            "is_tenanted": bool(is_tenanted),
            "is_non_residential": bool(is_non_res),
        }

    @classmethod
    def validate_physical_invariants(cls, property_obj: Any, expected_type: str) -> tuple[bool, str, str]:
        """Layer 4: Post-parse physical invariant gate verifying area/floor/structure consistency."""
        norm_expected = (expected_type or "mansion").lower()
        has_senyu = cls._is_positive_area_value(cls._get_field(property_obj, "senyuMenseki"))
        has_tochi = cls._is_positive_area_value(cls._get_field(property_obj, "tochiMenseki"))
        has_tatemono = cls._is_positive_area_value(cls._get_field(property_obj, "tatemonoMenseki"))

        if norm_expected == "tochi" and has_senyu and not has_tochi:
            return False, "mansion", "senyuMenseki is positive while tochiMenseki is missing on 'tochi'"

        if norm_expected == "kodate" and cls._is_rc_zero_land(property_obj):
            return False, "mansion", "tochiMenseki is 0 with RC/senyuMenseki on 'kodate'"

        if norm_expected == "mansion" and not has_senyu and has_tochi and has_tatemono:
            has_yield = cls._has_yield_in_object(property_obj)
            corrected = "apartment" if has_yield else "kodate"
            return False, corrected, "senyuMenseki missing while both land and building area exist on 'mansion'"

        return True, norm_expected, ""
