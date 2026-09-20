# -*- coding: utf-8 -*-
import re
import importlib
import logging
from typing import Optional, Dict, Any

from package.utils.property_type_detector import PropertyTypeDetector


KENBIYA_PARSER_MODULE = "package.parser.kenbiyaParser"
KENBIYA_MODEL_MODULE = "package.models.kenbiya"


class UrlRouter:
    """
    URL正規表現から対応サイト・物件種別・パーサーを解決するルーター
    """
    ROUTES = [
        # 三井のリハウス (Mitsui)
        {
            "pattern": re.compile(r"rehouse\.co\.jp/buy/mansion/bkdetail/"),
            "site": "mitsui",
            "property_type": "mansion",
            "parser_module": "package.parser.mitsuiParser",
            "parser_cls": "MitsuiMansionParser",
            "model_module": "package.models.mitsui",
            "model_cls": "MitsuiMansion",
        },
        {
            "pattern": re.compile(r"rehouse\.co\.jp/buy/kodate/bkdetail/"),
            "site": "mitsui",
            "property_type": "kodate",
            "parser_module": "package.parser.mitsuiParser",
            "parser_cls": "MitsuiKodateParser",
            "model_module": "package.models.mitsui",
            "model_cls": "MitsuiKodate",
        },
        {
            "pattern": re.compile(r"rehouse\.co\.jp/buy/tochi/bkdetail/"),
            "site": "mitsui",
            "property_type": "tochi",
            "parser_module": "package.parser.mitsuiParser",
            "parser_cls": "MitsuiTochiParser",
            "model_module": "package.models.mitsui",
            "model_cls": "MitsuiTochi",
        },
        {
            "pattern": re.compile(r"rehouse\.co\.jp/buy/tohshi/.*bkdetail/"),
            "site": "mitsui",
            "property_type": "apartment",
            "parser_module": "package.parser.mitsuiParser",
            "parser_cls": "MitsuiInvestApartmentParser",
            "model_module": "package.models.mitsui",
            "model_cls": "MitsuiInvestmentApartment",
        },

        # 東急リバブル (Tokyu)
        {
            "pattern": re.compile(r"livable\.co\.jp/kounyu/chuko-mansion/.*C[A-Z0-9]+|livable\.co\.jp/mansion/C[A-Z0-9]+"),
            "site": "tokyu",
            "property_type": "mansion",
            "parser_module": "package.parser.tokyuParser",
            "parser_cls": "TokyuMansionParser",
            "model_module": "package.models.tokyu",
            "model_cls": "TokyuMansion",
        },
        {
            "pattern": re.compile(r"livable\.co\.jp/kounyu/kodate/.*C[A-Z0-9]+|livable\.co\.jp/kodate/C[A-Z0-9]+"),
            "site": "tokyu",
            "property_type": "kodate",
            "parser_module": "package.parser.tokyuParser",
            "parser_cls": "TokyuKodateParser",
            "model_module": "package.models.tokyu",
            "model_cls": "TokyuKodate",
        },
        {
            "pattern": re.compile(r"livable\.co\.jp/kounyu/tochi/.*C[A-Z0-9]+|livable\.co\.jp/tochi/C[A-Z0-9]+"),
            "site": "tokyu",
            "property_type": "tochi",
            "parser_module": "package.parser.tokyuParser",
            "parser_cls": "TokyuTochiParser",
            "model_module": "package.models.tokyu",
            "model_cls": "TokyuTochi",
        },
        {
            "pattern": re.compile(r"livable\.co\.jp/toushi/.*C[A-Z0-9]+"),
            "site": "tokyu",
            "property_type": "apartment",
            "parser_module": "package.parser.tokyuParser",
            "parser_cls": "TokyuInvestApartmentParser",
            "model_module": "package.models.tokyu",
            "model_cls": "TokyuInvestmentApartment",
        },

        # 住友不動産ステップ (Sumifu)
        {
            "pattern": re.compile(r"stepon\.co\.jp/mansion/detail[_/]"),
            "site": "sumifu",
            "property_type": "mansion",
            "parser_module": "package.parser.sumifuParser",
            "parser_cls": "SumifuMansionParser",
            "model_module": "package.models.sumifu",
            "model_cls": "SumifuMansion",
        },
        {
            "pattern": re.compile(r"stepon\.co\.jp/kodate/detail[_/]"),
            "site": "sumifu",
            "property_type": "kodate",
            "parser_module": "package.parser.sumifuParser",
            "parser_cls": "SumifuKodateParser",
            "model_module": "package.models.sumifu",
            "model_cls": "SumifuKodate",
        },
        {
            "pattern": re.compile(r"stepon\.co\.jp/tochi/detail[_/]"),
            "site": "sumifu",
            "property_type": "tochi",
            "parser_module": "package.parser.sumifuParser",
            "parser_cls": "SumifuTochiParser",
            "model_module": "package.models.sumifu",
            "model_cls": "SumifuTochi",
        },
        {
            "pattern": re.compile(r"stepon\.co\.jp/pro/detail_"),
            "site": "sumifu",
            "property_type": "apartment",
            "parser_module": "package.parser.sumifuParser",
            "parser_cls": "SumifuInvestmentApartmentParser",
            "model_module": "package.models.sumifu",
            "model_cls": "SumifuInvestmentApartment",
        },

        # アットホーム (Athome)
        {
            "pattern": re.compile(r"athome\.co\.jp/mansion/"),
            "site": "athome",
            "property_type": "mansion",
            "parser_module": "package.parser.athomeParser",
            "parser_cls": "AthomeMansionParser",
            "model_module": "package.models.athome",
            "model_cls": "AthomeMansion",
        },
        {
            "pattern": re.compile(r"athome\.co\.jp/kodate/"),
            "site": "athome",
            "property_type": "kodate",
            "parser_module": "package.parser.athomeParser",
            "parser_cls": "AthomeKodateParser",
            "model_module": "package.models.athome",
            "model_cls": "AthomeKodate",
        },
        {
            "pattern": re.compile(r"athome\.co\.jp/tochi/"),
            "site": "athome",
            "property_type": "tochi",
            "parser_module": "package.parser.athomeParser",
            "parser_cls": "AthomeTochiParser",
            "model_module": "package.models.athome",
            "model_cls": "AthomeTochi",
        },

        # LIFULL HOME'S (Homes)
        {
            "pattern": re.compile(r"homes\.co\.jp/mansion/"),
            "site": "homes",
            "property_type": "mansion",
            "parser_module": "package.parser.homesParser",
            "parser_cls": "HomesMansionParser",
            "model_module": "package.models.homes",
            "model_cls": "HomesMansion",
        },
        {
            "pattern": re.compile(r"homes\.co\.jp/kodate/"),
            "site": "homes",
            "property_type": "kodate",
            "parser_module": "package.parser.homesParser",
            "parser_cls": "HomesKodateParser",
            "model_module": "package.models.homes",
            "model_cls": "HomesKodate",
        },
        {
            "pattern": re.compile(r"homes\.co\.jp/tochi/"),
            "site": "homes",
            "property_type": "tochi",
            "parser_module": "package.parser.homesParser",
            "parser_cls": "HomesTochiParser",
            "model_module": "package.models.homes",
            "model_cls": "HomesTochi",
        },
        {
            "pattern": re.compile(r"toushi\.homes\.co\.jp/bukkendetail/"),
            "site": "homes",
            "property_type": "apartment",
            "parser_module": "package.parser.homesParser",
            "parser_cls": "HomesInvestmentApartmentParser",
            "model_module": "package.models.homes",
            "model_cls": "HomesInvestmentApartment",
        },


        # ミサワホーム (Misawa)
        {
            "pattern": re.compile(r"realestate\.misawa\.co\.jp/.*bukken_type%5B%5D=9|realestate\.misawa\.co\.jp/.*bukken_type=9"),
            "site": "misawa",
            "property_type": "mansion",
            "parser_module": "package.parser.misawaParser",
            "parser_cls": "MisawaMansionParser",
            "model_module": "package.models.misawa",
            "model_cls": "MisawaMansion",
        },
        {
            "pattern": re.compile(r"realestate\.misawa\.co\.jp/.*bukken_type%5B%5D=10|realestate\.misawa\.co\.jp/.*bukken_type=10"),
            "site": "misawa",
            "property_type": "kodate",
            "parser_module": "package.parser.misawaParser",
            "parser_cls": "MisawaKodateParser",
            "model_module": "package.models.misawa",
            "model_cls": "MisawaKodate",
        },

        # 三井住友トラスト (Smtrc)
        {
            "pattern": re.compile(r"smtrc\.jp/buy/kodate/|smtrc\.jp/list/.*bukenkind=2"),
            "site": "smtrc",
            "property_type": "kodate",
            "parser_module": "package.parser.smtrcParser",
            "parser_cls": "SmtrcKodateParser",
            "model_module": "package.models.smtrc",
            "model_cls": "SmtrcKodate",
        },
        {
            "pattern": re.compile(r"smtrc\.jp/buy/tochi/|smtrc\.jp/list/.*bukenkind=3"),
            "site": "smtrc",
            "property_type": "tochi",
            "parser_module": "package.parser.smtrcParser",
            "parser_cls": "SmtrcTochiParser",
            "model_module": "package.models.smtrc",
            "model_cls": "SmtrcTochi",
        },
        {
            "pattern": re.compile(r"smtrc\.jp/buy/investment/|smtrc\.jp/list/.*proptype=33|smtrc\.jp/list/Listviewinvest"),
            "site": "smtrc",
            "property_type": "apartment",
            "parser_module": "package.parser.smtrcParser",
            "parser_cls": "SmtrcInvestmentParser",
            "model_module": "package.models.smtrc",
            "model_cls": "SmtrcInvestment",
        },
        {
            "pattern": re.compile(r"smtrc\.jp/buy/detail/|smtrc\.jp/detail/|smtrc\.jp/buy/mansion/|smtrc\.jp/list/.*bukenkind=1"),
            "site": "smtrc",
            "property_type": "mansion",
            "parser_module": "package.parser.smtrcParser",
            "parser_cls": "SmtrcMansionParser",
            "model_module": "package.models.smtrc",
            "model_cls": "SmtrcMansion",
        },

        # 野村不動産ノムコム (Nomura)
        {
            "pattern": re.compile(r"nomu\.com/mansion/"),
            "site": "nomura",
            "property_type": "mansion",
            "parser_module": "package.parser.nomuraParser",
            "parser_cls": "NomuraMansionParser",
            "model_module": "package.models.nomura",
            "model_cls": "NomuraMansion",
        },
        {
            "pattern": re.compile(r"nomu\.com/house/"),
            "site": "nomura",
            "property_type": "kodate",
            "parser_module": "package.parser.nomuraParser",
            "parser_cls": "NomuraKodateParser",
            "model_module": "package.models.nomura",
            "model_cls": "NomuraKodate",
        },
        {
            "pattern": re.compile(r"nomu\.com/land/"),
            "site": "nomura",
            "property_type": "tochi",
            "parser_module": "package.parser.nomuraParser",
            "parser_cls": "NomuraTochiParser",
            "model_module": "package.models.nomura",
            "model_cls": "NomuraTochi",
        },

        # 健美家 (Kenbiya)
        {
            "pattern": re.compile(r"kenbiya\.com/pp1/.*re_[0-9a-zA-Z]+"),
            "site": "kenbiya",
            "property_type": "mansion",
            "parser_module": KENBIYA_PARSER_MODULE,
            "parser_cls": "KenbiyaMansionParser",
            "model_module": KENBIYA_MODEL_MODULE,
            "model_cls": "KenbiyaMansion",
        },
        {
            "pattern": re.compile(r"kenbiya\.com/pp2/.*re_[0-9a-zA-Z]+"),
            "site": "kenbiya",
            "property_type": "apartment",
            "parser_module": KENBIYA_PARSER_MODULE,
            "parser_cls": "KenbiyaInvestmentApartmentParser",
            "model_module": KENBIYA_MODEL_MODULE,
            "model_cls": "KenbiyaInvestmentApartment",
        },
        {
            "pattern": re.compile(r"kenbiya\.com/pp[34]/.*re_[0-9a-zA-Z]+"),
            "site": "kenbiya",
            "property_type": "apartment",
            "parser_module": KENBIYA_PARSER_MODULE,
            "parser_cls": "KenbiyaInvestmentBuildingParser",
            "model_module": KENBIYA_MODEL_MODULE,
            "model_cls": "KenbiyaInvestmentBuilding",
        },
        {
            "pattern": re.compile(r"kenbiya\.com/pp8/.*re_[0-9a-zA-Z]+"),
            "site": "kenbiya",
            "property_type": "kodate",
            "parser_module": KENBIYA_PARSER_MODULE,
            "parser_cls": "KenbiyaKodateParser",
            "model_module": KENBIYA_MODEL_MODULE,
            "model_cls": "KenbiyaKodate",
        },
        {
            "pattern": re.compile(r"kenbiya\.com/pp5/.*re_[0-9a-zA-Z]+"),
            "site": "kenbiya",
            "property_type": "tochi",
            "parser_module": KENBIYA_PARSER_MODULE,
            "parser_cls": "KenbiyaTochiParser",
            "model_module": KENBIYA_MODEL_MODULE,
            "model_cls": "KenbiyaTochi",
        },
        {
            "pattern": re.compile(r"kenbiya\.com/.*re_[0-9a-zA-Z]+"),
            "site": "kenbiya",
            "property_type": "apartment",
            "parser_module": KENBIYA_PARSER_MODULE,
            "parser_cls": "KenbiyaInvestmentApartmentParser",
            "model_module": KENBIYA_MODEL_MODULE,
            "model_cls": "KenbiyaInvestmentApartment",
        },
    ]

    @classmethod
    def resolve(
        cls,
        url: str,
        title: Optional[str] = None,
        html_text: Optional[str] = None,
        specs: Optional[Dict[str, Any]] = None,
        property_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        URLから対象サイト・物件種別・パーサークラス情報を特定
        オプションで property_type, title, html_text, specs を渡すことで動的な物件種別判別にも対応
        Returns:
            Dict or None (未対応サイト時)
        """
        if not url or not isinstance(url, str):
            return None

        # 1. URL パターンにマッチする全ルートを抽出
        matched_routes = [route for route in cls.ROUTES if route["pattern"].search(url)]
        if not matched_routes:
            return None

        # 2. 目的の property_type の特定 (引数指定 > PropertyTypeDetector動的判定)
        target_ptype = property_type
        if not target_ptype and (title or html_text or specs):
            target_ptype = PropertyTypeDetector.detect(
                url=url,
                title=title,
                html_text=html_text,
                specs=specs
            )

        # 3. 指定・判定された property_type に合致するルートを選択
        if target_ptype:
            # マッチしたルート群の中から該当種別を探す
            for route in matched_routes:
                if route["property_type"] == target_ptype:
                    return route

            # マッチしたサイトの全ルートの中から該当種別を探す（汎用URLの場合）
            matched_site = matched_routes[0]["site"]
            for route in cls.ROUTES:
                if route["site"] == matched_site and route["property_type"] == target_ptype:
                    return route

        # 4. 種別指定なし、または該当なしの場合は先頭の一致ルートを返却
        return matched_routes[0]

    @classmethod
    def create_parser(
        cls,
        url: str,
        title: Optional[str] = None,
        html_text: Optional[str] = None,
        specs: Optional[Dict[str, Any]] = None,
        property_type: Optional[str] = None
    ) -> Optional[Any]:
        """
        URLおよび動的判定情報（title, html_text, specs, property_type）から
        適切なパーサーを解決し、インスタンス化して返却
        """
        route = cls.resolve(
            url=url,
            title=title,
            html_text=html_text,
            specs=specs,
            property_type=property_type
        )
        if not route or not route.get("parser_module") or not route.get("parser_cls"):
            return None

        try:
            mod = importlib.import_module(route["parser_module"])
            parser_cls = getattr(mod, route["parser_cls"])
            return parser_cls()
        except Exception as e:
            logging.error(f"Failed to instantiate parser {route.get('parser_cls')} from {route.get('parser_module')}: {e}")
            return None

