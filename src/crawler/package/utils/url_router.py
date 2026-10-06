# -*- coding: utf-8 -*-
import re
import importlib
import logging
from typing import Optional, Dict, Any, List

from package.utils.property_type_detector import PropertyTypeDetector


KENBIYA_PARSER_MODULE = "package.parser.kenbiyaParser"
KENBIYA_MODEL_MODULE = "package.models.kenbiya"
REARIE_PARSER_MODULE = "package.parser.rearieParser"
REARIE_MODEL_MODULE = "package.models.rearie"
MITSUI_PARSER_MODULE = "package.parser.mitsuiParser"
MITSUI_MODEL_MODULE = "package.models.mitsui"
TOKYU_PARSER_MODULE = "package.parser.tokyuParser"
TOKYU_MODEL_MODULE = "package.models.tokyu"
SUMIFU_PARSER_MODULE = "package.parser.sumifuParser"
SUMIFU_MODEL_MODULE = "package.models.sumifu"
ATHOME_PARSER_MODULE = "package.parser.athomeParser"
ATHOME_MODEL_MODULE = "package.models.athome"
HOMES_PARSER_MODULE = "package.parser.homesParser"
HOMES_MODEL_MODULE = "package.models.homes"
SMTRC_PARSER_MODULE = "package.parser.smtrcParser"
SMTRC_MODEL_MODULE = "package.models.smtrc"
NOMURA_PARSER_MODULE = "package.parser.nomuraParser"
NOMURA_MODEL_MODULE = "package.models.nomura"
SUMAI1_PARSER_MODULE = "package.parser.sumai1Parser"
SUMAI1_MODEL_MODULE = "package.models.sumai1"
HEIM_PARSER_MODULE = "package.parser.heimParser"
HEIM_MODEL_MODULE = "package.models.heim"
DAIKYO_PARSER_MODULE = "package.parser.daikyoParser"
DAIKYO_MODEL_MODULE = "package.models.daikyo"
MIZUHO_PARSER_MODULE = "package.parser.mizuhoParser"
MIZUHO_MODEL_MODULE = "package.models.mizuho"
DAIWA_PARSER_MODULE = "package.parser.daiwaParser"
DAIWA_MODEL_MODULE = "package.models.daiwa"
ODAKYU_PARSER_MODULE = "package.parser.odakyuParser"
ODAKYU_MODEL_MODULE = "package.models.odakyu"
KEIO_PARSER_MODULE = "package.parser.keioParser"
KEIO_MODEL_MODULE = "package.models.keio"
KEIKYU_PARSER_MODULE = "package.parser.keikyuParser"
KEIKYU_MODEL_MODULE = "package.models.keikyu"
KEISEI_PARSER_MODULE = "package.parser.keiseiParser"
KEISEI_MODEL_MODULE = "package.models.keisei"
SUMIRIN_PARSER_MODULE = "package.parser.sumirinParser"
SUMIRIN_MODEL_MODULE = "package.models.sumirin"


HEIM_DETAIL_PATTERN = re.compile(
    r"tokyo816\.jp/(?:plan_detail|bunjou/property)/|tokyo816\.jp/.*detail\.php|sumu-heim\.jp"
)
DAIKYO_DETAIL_PATTERN = re.compile(r"daikyo-anabuki\.co\.jp/buy/detail/")
MIZUHO_BUYERS_PATTERN = re.compile(r"mizuho-re\.co\.jp/buyers/")
KEIO_SALE_PATTERN = re.compile(r"chukai\.keiofudosan\.co\.jp/sale/")
KEIKYU_DETAIL_PATTERN = re.compile(r"keikyu-sumai\.com/contents/code/detail/")
KEISEI_DETAIL_PATTERN = re.compile(r"keisei-land\.co\.jp/contents/code/detail/")


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
            "parser_module": MITSUI_PARSER_MODULE,
            "parser_cls": "MitsuiMansionParser",
            "model_module": MITSUI_MODEL_MODULE,
            "model_cls": "MitsuiMansion",
        },
        {
            "pattern": re.compile(r"rehouse\.co\.jp/buy/kodate/bkdetail/"),
            "site": "mitsui",
            "property_type": "kodate",
            "parser_module": MITSUI_PARSER_MODULE,
            "parser_cls": "MitsuiKodateParser",
            "model_module": MITSUI_MODEL_MODULE,
            "model_cls": "MitsuiKodate",
        },
        {
            "pattern": re.compile(r"rehouse\.co\.jp/buy/tochi/bkdetail/"),
            "site": "mitsui",
            "property_type": "tochi",
            "parser_module": MITSUI_PARSER_MODULE,
            "parser_cls": "MitsuiTochiParser",
            "model_module": MITSUI_MODEL_MODULE,
            "model_cls": "MitsuiTochi",
        },
        {
            "pattern": re.compile(r"rehouse\.co\.jp/buy/tohshi/.*bkdetail/"),
            "site": "mitsui",
            "property_type": "apartment",
            "parser_module": MITSUI_PARSER_MODULE,
            "parser_cls": "MitsuiInvestmentApartmentParser",
            "model_module": MITSUI_MODEL_MODULE,
            "model_cls": "MitsuiInvestmentApartment",
        },

        # 東急リバブル (Tokyu)
        {
            "pattern": re.compile(r"livable\.co\.jp/kounyu/chuko-mansion/.*C[A-Z0-9]+|livable\.co\.jp/mansion/C[A-Z0-9]+"),
            "site": "tokyu",
            "property_type": "mansion",
            "parser_module": TOKYU_PARSER_MODULE,
            "parser_cls": "TokyuMansionParser",
            "model_module": TOKYU_MODEL_MODULE,
            "model_cls": "TokyuMansion",
        },
        {
            "pattern": re.compile(r"livable\.co\.jp/kounyu/kodate/.*C[A-Z0-9]+|livable\.co\.jp/kodate/C[A-Z0-9]+"),
            "site": "tokyu",
            "property_type": "kodate",
            "parser_module": TOKYU_PARSER_MODULE,
            "parser_cls": "TokyuKodateParser",
            "model_module": TOKYU_MODEL_MODULE,
            "model_cls": "TokyuKodate",
        },
        {
            "pattern": re.compile(r"livable\.co\.jp/kounyu/tochi/.*C[A-Z0-9]+|livable\.co\.jp/tochi/C[A-Z0-9]+"),
            "site": "tokyu",
            "property_type": "tochi",
            "parser_module": TOKYU_PARSER_MODULE,
            "parser_cls": "TokyuTochiParser",
            "model_module": TOKYU_MODEL_MODULE,
            "model_cls": "TokyuTochi",
        },
        {
            "pattern": re.compile(r"livable\.co\.jp/(?:toushi|fudosan-toushi)/.*C[A-Z0-9]+"),
            "site": "tokyu",
            "property_type": "apartment",
            "parser_module": TOKYU_PARSER_MODULE,
            "parser_cls": "TokyuInvestmentApartmentParser",
            "model_module": TOKYU_MODEL_MODULE,
            "model_cls": "TokyuInvestmentApartment",
        },

        # 住友不動産ステップ (Sumifu)
        {
            "pattern": re.compile(r"stepon\.co\.jp/mansion/detail[_/]"),
            "site": "sumifu",
            "property_type": "mansion",
            "parser_module": SUMIFU_PARSER_MODULE,
            "parser_cls": "SumifuMansionParser",
            "model_module": SUMIFU_MODEL_MODULE,
            "model_cls": "SumifuMansion",
        },
        {
            "pattern": re.compile(r"stepon\.co\.jp/kodate/detail[_/]"),
            "site": "sumifu",
            "property_type": "kodate",
            "parser_module": SUMIFU_PARSER_MODULE,
            "parser_cls": "SumifuKodateParser",
            "model_module": SUMIFU_MODEL_MODULE,
            "model_cls": "SumifuKodate",
        },
        {
            "pattern": re.compile(r"stepon\.co\.jp/tochi/detail[_/]"),
            "site": "sumifu",
            "property_type": "tochi",
            "parser_module": SUMIFU_PARSER_MODULE,
            "parser_cls": "SumifuTochiParser",
            "model_module": SUMIFU_MODEL_MODULE,
            "model_cls": "SumifuTochi",
        },
        {
            "pattern": re.compile(r"stepon\.co\.jp/pro/detail_"),
            "site": "sumifu",
            "property_type": "apartment",
            "parser_module": SUMIFU_PARSER_MODULE,
            "parser_cls": "SumifuInvestmentApartmentParser",
            "model_module": SUMIFU_MODEL_MODULE,
            "model_cls": "SumifuInvestmentApartment",
        },

        # アットホーム (Athome)
        {
            "pattern": re.compile(r"athome\.co\.jp/mansion/"),
            "site": "athome",
            "property_type": "mansion",
            "parser_module": ATHOME_PARSER_MODULE,
            "parser_cls": "AthomeMansionParser",
            "model_module": ATHOME_MODEL_MODULE,
            "model_cls": "AthomeMansion",
        },
        {
            "pattern": re.compile(r"athome\.co\.jp/kodate/"),
            "site": "athome",
            "property_type": "kodate",
            "parser_module": ATHOME_PARSER_MODULE,
            "parser_cls": "AthomeKodateParser",
            "model_module": ATHOME_MODEL_MODULE,
            "model_cls": "AthomeKodate",
        },
        {
            "pattern": re.compile(r"athome\.co\.jp/tochi/"),
            "site": "athome",
            "property_type": "tochi",
            "parser_module": ATHOME_PARSER_MODULE,
            "parser_cls": "AthomeTochiParser",
            "model_module": ATHOME_MODEL_MODULE,
            "model_cls": "AthomeTochi",
        },
        {
            "pattern": re.compile(r"athome\.co\.jp/buy_other/"),
            "site": "athome",
            "property_type": "tochi",
            "parser_module": ATHOME_PARSER_MODULE,
            "parser_cls": "AthomeTochiParser",
            "model_module": ATHOME_MODEL_MODULE,
            "model_cls": "AthomeTochi",
        },

        # LIFULL HOME'S (Homes)
        {
            "pattern": re.compile(r"homes\.co\.jp/mansion/"),
            "site": "homes",
            "property_type": "mansion",
            "parser_module": HOMES_PARSER_MODULE,
            "parser_cls": "HomesMansionParser",
            "model_module": HOMES_MODEL_MODULE,
            "model_cls": "HomesMansion",
        },
        {
            "pattern": re.compile(r"homes\.co\.jp/kodate/"),
            "site": "homes",
            "property_type": "kodate",
            "parser_module": HOMES_PARSER_MODULE,
            "parser_cls": "HomesKodateParser",
            "model_module": HOMES_MODEL_MODULE,
            "model_cls": "HomesKodate",
        },
        {
            "pattern": re.compile(r"homes\.co\.jp/tochi/"),
            "site": "homes",
            "property_type": "tochi",
            "parser_module": HOMES_PARSER_MODULE,
            "parser_cls": "HomesTochiParser",
            "model_module": HOMES_MODEL_MODULE,
            "model_cls": "HomesTochi",
        },
        {
            "pattern": re.compile(r"toushi\.homes\.co\.jp/bukkendetail/"),
            "site": "homes",
            "property_type": "apartment",
            "parser_module": HOMES_PARSER_MODULE,
            "parser_cls": "HomesInvestmentApartmentParser",
            "model_module": HOMES_MODEL_MODULE,
            "model_cls": "HomesInvestmentApartment",
        },
        # 投資ポータル上の土地（tbg[]=5 等）。property_type=tochi 指定時に解決される
        {
            "pattern": re.compile(r"toushi\.homes\.co\.jp/bukkendetail/"),
            "site": "homes",
            "property_type": "tochi",
            "parser_module": HOMES_PARSER_MODULE,
            "parser_cls": "HomesTochiParser",
            "model_module": HOMES_MODEL_MODULE,
            "model_cls": "HomesTochi",
        },


        # ミサワホーム (Misawa)
        {
            "pattern": re.compile(r"realestate\.misawa\.co\.jp/[^?]*\?[^#]*bukken_type(?:%5B%5D)?=9"),
            "site": "misawa",
            "property_type": "mansion",
            "parser_module": "package.parser.misawaParser",
            "parser_cls": "MisawaMansionParser",
            "model_module": "package.models.misawa",
            "model_cls": "MisawaMansion",
        },
        {
            "pattern": re.compile(r"realestate\.misawa\.co\.jp/[^?]*\?[^#]*bukken_type(?:%5B%5D)?=10"),
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
            "parser_module": SMTRC_PARSER_MODULE,
            "parser_cls": "SmtrcKodateParser",
            "model_module": SMTRC_MODEL_MODULE,
            "model_cls": "SmtrcKodate",
        },
        {
            "pattern": re.compile(r"smtrc\.jp/buy/tochi/|smtrc\.jp/list/.*bukenkind=3"),
            "site": "smtrc",
            "property_type": "tochi",
            "parser_module": SMTRC_PARSER_MODULE,
            "parser_cls": "SmtrcTochiParser",
            "model_module": SMTRC_MODEL_MODULE,
            "model_cls": "SmtrcTochi",
        },
        {
            "pattern": re.compile(r"smtrc\.jp/buy/investment/|smtrc\.jp/list/.*proptype=33|smtrc\.jp/list/Listviewinvest"),
            "site": "smtrc",
            "property_type": "apartment",
            "parser_module": SMTRC_PARSER_MODULE,
            "parser_cls": "SmtrcInvestmentParser",
            "model_module": SMTRC_MODEL_MODULE,
            "model_cls": "SmtrcInvestment",
        },
        {
            "pattern": re.compile(r"smtrc\.jp/buy/detail/|smtrc\.jp/detail/|smtrc\.jp/buy/mansion/|smtrc\.jp/list/.*bukenkind=1"),
            "site": "smtrc",
            "property_type": "mansion",
            "parser_module": SMTRC_PARSER_MODULE,
            "parser_cls": "SmtrcMansionParser",
            "model_module": SMTRC_MODEL_MODULE,
            "model_cls": "SmtrcMansion",
        },

        # 野村不動産ノムコム (Nomura)
        {
            "pattern": re.compile(r"nomu\.com/pro/"),
            "site": "nomura",
            "property_type": "apartment",
            "parser_module": NOMURA_PARSER_MODULE,
            "parser_cls": "NomuraInvestmentApartmentParser",
            "model_module": NOMURA_MODEL_MODULE,
            "model_cls": "NomuraInvestmentApartment",
        },
        {
            "pattern": re.compile(r"nomu\.com/mansion/"),
            "site": "nomura",
            "property_type": "mansion",
            "parser_module": NOMURA_PARSER_MODULE,
            "parser_cls": "NomuraMansionParser",
            "model_module": NOMURA_MODEL_MODULE,
            "model_cls": "NomuraMansion",
        },
        {
            "pattern": re.compile(r"nomu\.com/house/"),
            "site": "nomura",
            "property_type": "kodate",
            "parser_module": NOMURA_PARSER_MODULE,
            "parser_cls": "NomuraKodateParser",
            "model_module": NOMURA_MODEL_MODULE,
            "model_cls": "NomuraKodate",
        },
        {
            "pattern": re.compile(r"nomu\.com/land/"),
            "site": "nomura",
            "property_type": "tochi",
            "parser_module": NOMURA_PARSER_MODULE,
            "parser_cls": "NomuraTochiParser",
            "model_module": NOMURA_MODEL_MODULE,
            "model_cls": "NomuraTochi",
        },

        # 健美家 (Kenbiya)
        {
            "pattern": re.compile(r"kenbiya\.com/pp1/.*re_[a-zA-Z\d]+"),
            "site": "kenbiya",
            "property_type": "mansion",
            "parser_module": KENBIYA_PARSER_MODULE,
            "parser_cls": "KenbiyaMansionParser",
            "model_module": KENBIYA_MODEL_MODULE,
            "model_cls": "KenbiyaMansion",
        },
        {
            "pattern": re.compile(r"kenbiya\.com/pp2/.*re_[a-zA-Z\d]+"),
            "site": "kenbiya",
            "property_type": "apartment",
            "parser_module": KENBIYA_PARSER_MODULE,
            "parser_cls": "KenbiyaInvestmentApartmentParser",
            "model_module": KENBIYA_MODEL_MODULE,
            "model_cls": "KenbiyaInvestmentApartment",
        },
        {
            "pattern": re.compile(r"kenbiya\.com/pp[34]/.*re_[a-zA-Z\d]+"),
            "site": "kenbiya",
            "property_type": "apartment",
            "parser_module": KENBIYA_PARSER_MODULE,
            "parser_cls": "KenbiyaInvestmentBuildingParser",
            "model_module": KENBIYA_MODEL_MODULE,
            "model_cls": "KenbiyaInvestmentBuilding",
        },
        {
            "pattern": re.compile(r"kenbiya\.com/pp8/.*re_[a-zA-Z\d]+"),
            "site": "kenbiya",
            "property_type": "kodate",
            "parser_module": KENBIYA_PARSER_MODULE,
            "parser_cls": "KenbiyaKodateParser",
            "model_module": KENBIYA_MODEL_MODULE,
            "model_cls": "KenbiyaKodate",
        },
        {
            "pattern": re.compile(r"kenbiya\.com/pp5/.*re_[a-zA-Z\d]+"),
            "site": "kenbiya",
            "property_type": "tochi",
            "parser_module": KENBIYA_PARSER_MODULE,
            "parser_cls": "KenbiyaTochiParser",
            "model_module": KENBIYA_MODEL_MODULE,
            "model_cls": "KenbiyaTochi",
        },
        {
            "pattern": re.compile(r"kenbiya\.com/.*re_[a-zA-Z\d]+"),
            "site": "kenbiya",
            "property_type": "apartment",
            "parser_module": KENBIYA_PARSER_MODULE,
            "parser_cls": "KenbiyaInvestmentApartmentParser",
            "model_module": KENBIYA_MODEL_MODULE,
            "model_cls": "KenbiyaInvestmentApartment",
        },

        # パナソニック ホームズ 不動産 (Rearie)
        {
            "pattern": re.compile(r"homes\.panasonic\.com/rearie/buy/property/mansion/"),
            "site": "rearie",
            "property_type": "mansion",
            "parser_module": REARIE_PARSER_MODULE,
            "parser_cls": "RearieMansionParser",
            "model_module": REARIE_MODEL_MODULE,
            "model_cls": "RearieMansion",
        },
        {
            "pattern": re.compile(r"homes\.panasonic\.com/rearie/buy/property/house/"),
            "site": "rearie",
            "property_type": "kodate",
            "parser_module": REARIE_PARSER_MODULE,
            "parser_cls": "RearieKodateParser",
            "model_module": REARIE_MODEL_MODULE,
            "model_cls": "RearieKodate",
        },
        {
            "pattern": re.compile(r"homes\.panasonic\.com/rearie/buy/property/land/"),
            "site": "rearie",
            "property_type": "tochi",
            "parser_module": REARIE_PARSER_MODULE,
            "parser_cls": "RearieTochiParser",
            "model_module": REARIE_MODEL_MODULE,
            "model_cls": "RearieTochi",
        },

        # 住まい1 (Sumai1)
        {
            "pattern": re.compile(r"sumai1\.com/buyers/mansion/bukken/buk_"),
            "site": "sumai1",
            "property_type": "mansion",
            "parser_module": SUMAI1_PARSER_MODULE,
            "parser_cls": "Sumai1MansionParser",
            "model_module": SUMAI1_MODEL_MODULE,
            "model_cls": "Sumai1Mansion",
        },
        {
            "pattern": re.compile(r"sumai1\.com/buyers/kodate/bukken/buk_"),
            "site": "sumai1",
            "property_type": "kodate",
            "parser_module": SUMAI1_PARSER_MODULE,
            "parser_cls": "Sumai1KodateParser",
            "model_module": SUMAI1_MODEL_MODULE,
            "model_cls": "Sumai1Kodate",
        },
        {
            "pattern": re.compile(r"sumai1\.com/buyers/tochi/bukken/buk_"),
            "site": "sumai1",
            "property_type": "tochi",
            "parser_module": SUMAI1_PARSER_MODULE,
            "parser_cls": "Sumai1TochiParser",
            "model_module": SUMAI1_MODEL_MODULE,
            "model_cls": "Sumai1Tochi",
        },
        {
            "pattern": re.compile(r"sumai1\.com/buyers/investor/bukken/buk_"),
            "site": "sumai1",
            "property_type": "apartment",
            "parser_module": SUMAI1_PARSER_MODULE,
            "parser_cls": "Sumai1InvestmentParser",
            "model_module": SUMAI1_MODEL_MODULE,
            "model_cls": "Sumai1Investment",
        },

        # セキスイハイム (Heim)
        {
            "pattern": HEIM_DETAIL_PATTERN,
            "site": "heim",
            "property_type": "kodate",
            "parser_module": HEIM_PARSER_MODULE,
            "parser_cls": "HeimKodateParser",
            "model_module": HEIM_MODEL_MODULE,
            "model_cls": "HeimKodate",
        },
        {
            "pattern": HEIM_DETAIL_PATTERN,
            "site": "heim",
            "property_type": "mansion",
            "parser_module": HEIM_PARSER_MODULE,
            "parser_cls": "HeimMansionParser",
            "model_module": HEIM_MODEL_MODULE,
            "model_cls": "HeimMansion",
        },
        {
            "pattern": HEIM_DETAIL_PATTERN,
            "site": "heim",
            "property_type": "tochi",
            "parser_module": HEIM_PARSER_MODULE,
            "parser_cls": "HeimTochiParser",
            "model_module": HEIM_MODEL_MODULE,
            "model_cls": "HeimTochi",
        },

        # 大京穴吹不動産 (Daikyo)
        {
            "pattern": DAIKYO_DETAIL_PATTERN,
            "site": "daikyo",
            "property_type": "mansion",
            "parser_module": DAIKYO_PARSER_MODULE,
            "parser_cls": "DaikyoMansionParser",
            "model_module": DAIKYO_MODEL_MODULE,
            "model_cls": "DaikyoMansion",
        },
        {
            "pattern": DAIKYO_DETAIL_PATTERN,
            "site": "daikyo",
            "property_type": "kodate",
            "parser_module": DAIKYO_PARSER_MODULE,
            "parser_cls": "DaikyoKodateParser",
            "model_module": DAIKYO_MODEL_MODULE,
            "model_cls": "DaikyoKodate",
        },
        {
            "pattern": DAIKYO_DETAIL_PATTERN,
            "site": "daikyo",
            "property_type": "tochi",
            "parser_module": DAIKYO_PARSER_MODULE,
            "parser_cls": "DaikyoTochiParser",
            "model_module": DAIKYO_MODEL_MODULE,
            "model_cls": "DaikyoTochi",
        },

        # みずほ不動産販売 (Mizuho)
        {
            "pattern": re.compile(r"mizuho-re\.co\.jp/investors/"),
            "site": "mizuho",
            "property_type": "apartment",
            "parser_module": MIZUHO_PARSER_MODULE,
            "parser_cls": "MizuhoInvestmentParser",
            "model_module": MIZUHO_MODEL_MODULE,
            "model_cls": "MizuhoInvestment",
        },
        {
            "pattern": MIZUHO_BUYERS_PATTERN,
            "site": "mizuho",
            "property_type": "mansion",
            "parser_module": MIZUHO_PARSER_MODULE,
            "parser_cls": "MizuhoMansionParser",
            "model_module": MIZUHO_MODEL_MODULE,
            "model_cls": "MizuhoMansion",
        },
        {
            "pattern": MIZUHO_BUYERS_PATTERN,
            "site": "mizuho",
            "property_type": "kodate",
            "parser_module": MIZUHO_PARSER_MODULE,
            "parser_cls": "MizuhoKodateParser",
            "model_module": MIZUHO_MODEL_MODULE,
            "model_cls": "MizuhoKodate",
        },
        {
            "pattern": MIZUHO_BUYERS_PATTERN,
            "site": "mizuho",
            "property_type": "tochi",
            "parser_module": MIZUHO_PARSER_MODULE,
            "parser_cls": "MizuhoTochiParser",
            "model_module": MIZUHO_MODEL_MODULE,
            "model_cls": "MizuhoTochi",
        },

        # 大和ハウスリアルエステート (Daiwa)
        {
            "pattern": re.compile(r"dh-realestate\.co\.jp/buy/mansion/"),
            "site": "daiwa",
            "property_type": "mansion",
            "parser_module": DAIWA_PARSER_MODULE,
            "parser_cls": "DaiwaMansionParser",
            "model_module": DAIWA_MODEL_MODULE,
            "model_cls": "DaiwaMansion",
        },
        {
            "pattern": re.compile(r"dh-realestate\.co\.jp/buy/kodate/"),
            "site": "daiwa",
            "property_type": "kodate",
            "parser_module": DAIWA_PARSER_MODULE,
            "parser_cls": "DaiwaKodateParser",
            "model_module": DAIWA_MODEL_MODULE,
            "model_cls": "DaiwaKodate",
        },
        {
            "pattern": re.compile(r"dh-realestate\.co\.jp/buy/tochi/"),
            "site": "daiwa",
            "property_type": "tochi",
            "parser_module": DAIWA_PARSER_MODULE,
            "parser_cls": "DaiwaTochiParser",
            "model_module": DAIWA_MODEL_MODULE,
            "model_cls": "DaiwaTochi",
        },

        # 東急リバブル提携 住み替え (Tokyu Sumikae)
        {
            "pattern": re.compile(r"sumikae\.ttfuhan\.co\.jp/mansion/"),
            "site": "tokyu",
            "property_type": "mansion",
            "parser_module": TOKYU_PARSER_MODULE,
            "parser_cls": "TokyuMansionParser",
            "model_module": TOKYU_MODEL_MODULE,
            "model_cls": "TokyuMansion",
        },
        {
            "pattern": re.compile(r"sumikae\.ttfuhan\.co\.jp/kodate/"),
            "site": "tokyu",
            "property_type": "kodate",
            "parser_module": TOKYU_PARSER_MODULE,
            "parser_cls": "TokyuKodateParser",
            "model_module": TOKYU_MODEL_MODULE,
            "model_cls": "TokyuKodate",
        },
        {
            "pattern": re.compile(r"sumikae\.ttfuhan\.co\.jp/tochi/"),
            "site": "tokyu",
            "property_type": "tochi",
            "parser_module": TOKYU_PARSER_MODULE,
            "parser_cls": "TokyuTochiParser",
            "model_module": TOKYU_MODEL_MODULE,
            "model_cls": "TokyuTochi",
        },

        # 小田急不動産 (Odakyu)
        {
            "pattern": re.compile(r"odakyu-chukai\.com/invest/"),
            "site": "odakyu",
            "property_type": "apartment",
            "parser_module": ODAKYU_PARSER_MODULE,
            "parser_cls": "OdakyuInvestmentParser",
            "model_module": ODAKYU_MODEL_MODULE,
            "model_cls": "OdakyuInvestment",
        },
        {
            "pattern": re.compile(r"odakyu-chukai\.com/mansion/"),
            "site": "odakyu",
            "property_type": "mansion",
            "parser_module": ODAKYU_PARSER_MODULE,
            "parser_cls": "OdakyuMansionParser",
            "model_module": ODAKYU_MODEL_MODULE,
            "model_cls": "OdakyuMansion",
        },
        {
            "pattern": re.compile(r"odakyu-chukai\.com/kodate/"),
            "site": "odakyu",
            "property_type": "kodate",
            "parser_module": ODAKYU_PARSER_MODULE,
            "parser_cls": "OdakyuKodateParser",
            "model_module": ODAKYU_MODEL_MODULE,
            "model_cls": "OdakyuKodate",
        },
        {
            "pattern": re.compile(r"odakyu-chukai\.com/tochi/"),
            "site": "odakyu",
            "property_type": "tochi",
            "parser_module": ODAKYU_PARSER_MODULE,
            "parser_cls": "OdakyuTochiParser",
            "model_module": ODAKYU_MODEL_MODULE,
            "model_cls": "OdakyuTochi",
        },

        # 京王不動産 (Keio)
        {
            "pattern": KEIO_SALE_PATTERN,
            "site": "keio",
            "property_type": "mansion",
            "parser_module": KEIO_PARSER_MODULE,
            "parser_cls": "KeioMansionParser",
            "model_module": KEIO_MODEL_MODULE,
            "model_cls": "KeioMansion",
        },
        {
            "pattern": KEIO_SALE_PATTERN,
            "site": "keio",
            "property_type": "kodate",
            "parser_module": KEIO_PARSER_MODULE,
            "parser_cls": "KeioKodateParser",
            "model_module": KEIO_MODEL_MODULE,
            "model_cls": "KeioKodate",
        },
        {
            "pattern": KEIO_SALE_PATTERN,
            "site": "keio",
            "property_type": "tochi",
            "parser_module": KEIO_PARSER_MODULE,
            "parser_cls": "KeioTochiParser",
            "model_module": KEIO_MODEL_MODULE,
            "model_cls": "KeioTochi",
        },

        # 京急すまい (Keikyu)
        {
            "pattern": KEIKYU_DETAIL_PATTERN,
            "site": "keikyu",
            "property_type": "mansion",
            "parser_module": KEIKYU_PARSER_MODULE,
            "parser_cls": "KeikyuMansionParser",
            "model_module": KEIKYU_MODEL_MODULE,
            "model_cls": "KeikyuMansion",
        },
        {
            "pattern": KEIKYU_DETAIL_PATTERN,
            "site": "keikyu",
            "property_type": "kodate",
            "parser_module": KEIKYU_PARSER_MODULE,
            "parser_cls": "KeikyuKodateParser",
            "model_module": KEIKYU_MODEL_MODULE,
            "model_cls": "KeikyuKodate",
        },
        {
            "pattern": KEIKYU_DETAIL_PATTERN,
            "site": "keikyu",
            "property_type": "tochi",
            "parser_module": KEIKYU_PARSER_MODULE,
            "parser_cls": "KeikyuTochiParser",
            "model_module": KEIKYU_MODEL_MODULE,
            "model_cls": "KeikyuTochi",
        },

        # 京成不動産 (Keisei)
        {
            "pattern": KEISEI_DETAIL_PATTERN,
            "site": "keisei",
            "property_type": "mansion",
            "parser_module": KEISEI_PARSER_MODULE,
            "parser_cls": "KeiseiMansionParser",
            "model_module": KEISEI_MODEL_MODULE,
            "model_cls": "KeiseiMansion",
        },
        {
            "pattern": KEISEI_DETAIL_PATTERN,
            "site": "keisei",
            "property_type": "kodate",
            "parser_module": KEISEI_PARSER_MODULE,
            "parser_cls": "KeiseiKodateParser",
            "model_module": KEISEI_MODEL_MODULE,
            "model_cls": "KeiseiKodate",
        },
        {
            "pattern": KEISEI_DETAIL_PATTERN,
            "site": "keisei",
            "property_type": "tochi",
            "parser_module": KEISEI_PARSER_MODULE,
            "parser_cls": "KeiseiTochiParser",
            "model_module": KEISEI_MODEL_MODULE,
            "model_cls": "KeiseiTochi",
        },

        # 住友林業ホームサービス すみなび (Sumirin)
        {
            "pattern": re.compile(r"suminavi\.com/buy/estate/estateInfo/mansion/"),
            "site": "sumirin",
            "property_type": "mansion",
            "parser_module": SUMIRIN_PARSER_MODULE,
            "parser_cls": "SumirinMansionParser",
            "model_module": SUMIRIN_MODEL_MODULE,
            "model_cls": "SumirinMansion",
        },
        {
            "pattern": re.compile(r"suminavi\.com/buy/estate/estateInfo/kodate/"),
            "site": "sumirin",
            "property_type": "kodate",
            "parser_module": SUMIRIN_PARSER_MODULE,
            "parser_cls": "SumirinKodateParser",
            "model_module": SUMIRIN_MODEL_MODULE,
            "model_cls": "SumirinKodate",
        },
        {
            "pattern": re.compile(r"suminavi\.com/buy/estate/estateInfo/tochi/"),
            "site": "sumirin",
            "property_type": "tochi",
            "parser_module": SUMIRIN_PARSER_MODULE,
            "parser_cls": "SumirinTochiParser",
            "model_module": SUMIRIN_MODEL_MODULE,
            "model_cls": "SumirinTochi",
        },
        {
            "pattern": re.compile(r"suminavi\.com/buy/estate/estateInfo/toushi/"),
            "site": "sumirin",
            "property_type": "apartment",
            "parser_module": SUMIRIN_PARSER_MODULE,
            "parser_cls": "SumirinInvestmentParser",
            "model_module": SUMIRIN_MODEL_MODULE,
            "model_cls": "SumirinInvestment",
        },
    ]

    @classmethod
    def _find_best_route(cls, matched_routes: List[Dict[str, Any]], target_ptype: str) -> Optional[Dict[str, Any]]:
        for route in matched_routes:
            if route["property_type"] == target_ptype:
                return route
        matched_site = matched_routes[0]["site"]
        for route in cls.ROUTES:
            if route["site"] == matched_site and route["property_type"] == target_ptype:
                return route
        return None

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
        # URLのみでも detect し、同一パターンの複数ルート（例: toushi homes apartment/tochi）を区別する
        target_ptype = property_type
        if not target_ptype:
            target_ptype = PropertyTypeDetector.detect(
                url=url,
                title=title,
                html_text=html_text,
                specs=specs,
            )

        # 3. 指定・判定された property_type に合致するルートを選択
        if target_ptype:
            best = cls._find_best_route(matched_routes, target_ptype)
            if best:
                return best

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
            logging.exception(f"Failed to instantiate parser {route.get('parser_cls')} from {route.get('parser_module')}: {e}")
            return None

