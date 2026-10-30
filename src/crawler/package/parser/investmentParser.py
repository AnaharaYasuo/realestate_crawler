import logging
import re

from package.parser.baseParser import InvestmentParserBase
from package.utils import converter

NON_DIGIT_PATTERN = r'\D'


class InvestmentParser(InvestmentParserBase):
    def _parseAddress(self, response, specs=None):
        return super()._parseAddress(response, specs)

    def _parseChimoku(self, response, specs=None):
        return super()._parseChimoku(response, specs)

    def _parseCurrentStatus(self, response, specs=None):
        return super()._parseCurrentStatus(response, specs)

    def _parseGenkyo(self, response, specs=None):
        return super()._parseGenkyo(response, specs)

    def _parseHikiwatashi(self, response, specs=None):
        return super()._parseHikiwatashi(response, specs)

    def _parseMonthlyRent(self, response, specs=None):
        return super()._parseMonthlyRent(response, specs)

    def _parsePrice(self, response, specs=None):
        return super()._parsePrice(response, specs)

    def _parsePriceStr(self, response, specs=None):
        return super()._parsePriceStr(response, specs)

    def _parsePropertyDetailPage(self, item, response):
        return super()._parsePropertyDetailPage(item, response)

    def _parsePropertyName(self, response, specs=None):
        return super()._parsePropertyName(response, specs)

    def _parseRights(self, response, specs=None):
        return super()._parseRights(response, specs)

    def _parseSetsudou(self, response, specs=None):
        return super()._parseSetsudou(response, specs)

    def _parseTransport1(self, response, specs=None):
        return super()._parseTransport1(response, specs)

    def _parseYoutoChiiki(self, response, specs=None):
        return super()._parseYoutoChiiki(response, specs)

    def _parseGrossYield(self, response, specs=None):
        return super()._parseGrossYield(response, specs)

    def _parseAnnualRent(self, response, specs=None):
        return super()._parseAnnualRent(response, specs)

    def _parseChikunengetsu(self, response, specs=None):
        return super()._parseChikunengetsu(response, specs)

    def _parseKouzou(self, response, specs=None) -> str:
        return super()._parseKouzou(response, specs)

    def _parseTochiMenseki(self, response, specs=None):
        return super()._parseTochiMenseki(response, specs)

    def _parseTatemonoMenseki(self, response, specs=None):
        return super()._parseTatemonoMenseki(response, specs)

    def getCharset(self):
        return "utf-8"

    def _clean_text(self, text):
        if text is None:
            return ""
        if hasattr(text, 'get_text'):
            text = text.get_text()
        return text.strip().replace('\n', '').replace('\t', '').replace('\r', '')

    def _parse_price(self, text):
        """
        Parse Japanese price string like '1億5,000万円' or '1.5億円' to integer 150000000.
        Delegates to canonical converter functions to prevent decimal '億円' 10x bugs.
        """
        if not text:
            return None
        cleaned = str(text).strip()
        if not cleaned or cleaned == "-":
            return None
        if "億" in cleaned or "万" in cleaned:
            val = converter.parse_price(cleaned)
            return val if val and val > 0 else None
        val = converter.parse_yen(cleaned)
        return val if val and val > 0 else None

    def _parse_yield(self, text):
        """
        Parse yield string like '5.5%' or '5.5' to float 5.5.
        """
        if not text:
            return None
        try:
            clean = re.sub(r'[^\d.]', '', text)
            return float(clean)
        except Exception:
            logging.warning(f"Failed to parse yield: {text}")
            return None
