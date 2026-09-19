# -*- coding: utf-8 -*-
import re
from typing import Optional, Dict, Any


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
            "pattern": re.compile(r"stepon\.co\.jp/mansion/detail/"),
            "site": "sumifu",
            "property_type": "mansion",
            "parser_module": "package.parser.sumifuParser",
            "parser_cls": "SumifuMansionParser",
            "model_module": "package.models.sumifu",
            "model_cls": "SumifuMansion",
        },
        {
            "pattern": re.compile(r"stepon\.co\.jp/kodate/detail/"),
            "site": "sumifu",
            "property_type": "kodate",
            "parser_module": "package.parser.sumifuParser",
            "parser_cls": "SumifuKodateParser",
            "model_module": "package.models.sumifu",
            "model_cls": "SumifuKodate",
        },
        {
            "pattern": re.compile(r"stepon\.co\.jp/tochi/detail/"),
            "site": "sumifu",
            "property_type": "tochi",
            "parser_module": "package.parser.sumifuParser",
            "parser_cls": "SumifuTochiParser",
            "model_module": "package.models.sumifu",
            "model_cls": "SumifuTochi",
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
            "pattern": re.compile(r"smtrc\.jp/buy/detail/|smtrc\.jp/detail/"),
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
    ]

    @classmethod
    def resolve(cls, url: str) -> Optional[Dict[str, Any]]:
        """
        URLから対象サイト・物件種別・パーサークラス情報を特定
        Returns:
            Dict or None (未対応サイト時)
        """
        if not url or not isinstance(url, str):
            return None

        for route in cls.ROUTES:
            if route["pattern"].search(url):
                return route
        return None
