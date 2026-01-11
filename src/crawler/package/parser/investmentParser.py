from django.db import models
from bs4 import BeautifulSoup
import re
import logging
import traceback
from package.parser.baseParser import ParserBase

class InvestmentParser(ParserBase):
    
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
        Parse Japanese price string like '1億5,000万円' to integer 150000000.
        Returns None if parsing fails.
        """
        if not text:
            return None
        
        try:
            text = text.replace(",", "").strip()
            total = 0
            
            # Create a simplified version for common formats
            # Handle '億'
            if '億' in text:
                parts = text.split('億')
                oku_part = parts[0]
                total += int(re.sub(r'[^0-9]', '', oku_part)) * 100000000
                remainder = parts[1]
            else:
                remainder = text
                
            # Handle '万'
            if '万' in remainder:
                man_part = remainder.split('万')[0]
                # If there was '億', man_part might be empty or just numeric
                if man_part:
                    total += int(re.sub(r'[^0-9]', '', man_part)) * 10000
            elif remainder and not '億' in text: # pure number?
                # Sometimes prices are just raw numbers
                clean_num = re.sub(r'[^0-9]', '', remainder)
                if clean_num:
                    total += int(clean_num)
                    
            return total if total > 0 else None
        except Exception:
            logging.warning(f"Failed to parse price: {text}")
            return None

    def _parse_yield(self, text):
        """
        Parse yield string like '5.5%' or '5.5' to float 5.5.
        """
        if not text:
            return None
        try:
            clean = re.sub(r'[^0-9\.]', '', text)
            return float(clean)
        except Exception:
            logging.warning(f"Failed to parse yield: {text}")
            return None
