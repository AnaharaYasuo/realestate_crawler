# -*- coding: utf-8 -*-
import re
import datetime
from decimal import Decimal
import unicodedata

def parse_price(price_str):
    """
    価格文字列を数値に変換する (円単位)
    例: "1億2,000万円" -> 120000000
    """
    if not price_str or price_str == "-":
        return 0
    
    price_work = price_str.replace(',', '').replace(' ', '')
    oku = 0
    man = 0
    
    try:
        if "億" in price_work:
            parts = price_work.split("億")
            oku = int(parts[0]) * 10000
            if len(parts) > 1 and parts[1]:
                man_match = re.search(r'(\d+)', parts[1])
                if man_match:
                    man = int(man_match.group(1))
        else:
            man_match = re.search(r'(\d+)', price_work)
            if man_match:
                man = int(man_match.group(1))
        
        return (oku + man) * 10000
    except:
        return 0

def parse_menseki(menseki_str):
    """
    面積文字列を Decimal に変換する
    例: "70.52㎡" -> Decimal("70.52")
    """
    if not menseki_str or menseki_str == "-":
        return Decimal("0")
    
    try:
        # 数字とドット以外の文字を除去
        val = menseki_str.replace(',', '').split('㎡')[0].strip()
        match = re.search(r'([0-9\.]+)', val)
        if match:
            return Decimal(match.group(1))
    except:
        pass
    return Decimal("0")

def parse_chikunengetsu(date_str):
    """
    築年月文字列を date オブジェクトに変換する
    例: "1998年3月" -> date(1998, 3, 1)
    """
    if not date_str or date_str == "不詳" or date_str == "-":
        return datetime.date(1900, 1, 1)
    
    try:
        match = re.search(r'(\d+)年(\d+)月', date_str)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            return datetime.date(year, month, 1)
    except:
        pass
    return datetime.date(1900, 1, 1)

def parse_numeric(text):
    """
    文字列から最初の数値のみを抽出して整数で返す
    例: "地上10階" -> 10
    """
    if not text:
        return 0
    try:
        match = re.search(r'(\d+)', text)
        if match:
            return int(match.group(1))
    except:
        pass
    return 0

def truncate_str(text, length):
    """
    全角・半角を区別して文字列を切り詰める
    """
    if not text:
        return ""
    count = 0
    sliced_text = ''
    for c in text:
        if unicodedata.east_asian_width(c) in 'FWA':
            count += 2
        else:
            count += 1
        if count > length:
            break
        sliced_text += c
    return sliced_text
