# -*- coding: utf-8 -*-
from typing import Optional, Dict, Any


class PropertyTypeDetector:
    """
    URL・タイトル・HTML・スペック表から物件種別を総合判定する再利用可能モジュール
    判定優先度: specs > title > html_text > url
    標準化出力: 'apartment' | 'mansion' | 'kodate' | 'tochi' | None
    """

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
    def _match_keywords(cls, text: str) -> Optional[str]:
        """テキストからキーワードマッチにより種別を特定（apartment優先）"""
        if not text or not isinstance(text, str):
            return None

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
        default: Optional[str] = None
    ) -> Optional[str]:
        """
        優先順位 (specs > title > html_text > url) に従って物件種別を判定
        """
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

        return default
