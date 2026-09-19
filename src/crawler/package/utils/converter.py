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
        return None
    
    price_work = price_str.replace(',', '').replace(' ', '')
    oku = 0.0
    man = 0.0
    
    try:
        if "億" in price_work:
            parts = price_work.split("億")
            oku = float(parts[0]) * 10000.0
            if len(parts) > 1 and parts[1]:
                man_match = re.search(r'(\d+(?:\.\d+)?)', parts[1])
                if man_match:
                    man = float(man_match.group(1))
        else:
            man_match = re.search(r'(\d+(?:\.\d+)?)', price_work)
            if man_match:
                man = float(man_match.group(1))
        
        return int(round((oku + man) * 10000))

    except Exception:
        return None

def parse_yen(text):
    """
    円単位の文字列を数値に変換する
    例: "15,760円" -> 15760
    """
    if not text or text == "-":
        return None
    try:
        # 数字以外の文字を除去
        val = re.sub(r'\D', '', text)
        if val:
            return int(val)
    except Exception:
        pass
    return 0

def parse_menseki(menseki_str):
    """
    面積文字列を Decimal に変換する
    例: "70.52㎡" -> Decimal("70.52")
    """
    if not menseki_str or menseki_str == "-":
        return None
    
    try:
        # 数字とドット以外の文字を除去
        val = menseki_str.replace(',', '').split('㎡')[0].strip()
        match = re.search(r'([0-9\.]+)', val)
        if match:
            return Decimal(match.group(1))
    except Exception:
        pass
    return None

def parse_chikunengetsu(date_str):
    """
    築年月文字列を date オブジェクトに変換する
    例: "1998年3月" -> date(1998, 3, 1)
    """
    if not date_str or date_str == "不詳" or date_str == "-":
        return None
    
    try:
        match = re.search(r'(\d+)年(\d+)月', date_str)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            return datetime.date(year, month, 1)
    except Exception:
        pass
    return None

def parse_numeric(text):
    """
    文字列から最初の数値のみを抽出して整数で返す
    例: "地上10階" -> 10
    """
    if not text:
        return None
    try:
        match = re.search(r'(\d+)', text)
        if match:
            return int(match.group(1))
    except Exception:
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

def parse_ratio(text):
    """
    割合・パーセント文字列を Decimal に変換する
    例: "8.0％" -> Decimal("8.00")
    """
    if not text or text == "-":
        return None
    try:
        val = text.replace('％', '').replace('%', '').strip()
        match = re.search(r'([0-9\.]+)', val)
        if match:
            return Decimal(match.group(1))
    except Exception:
        pass
    return None

parse_number = parse_numeric

def parse_rent(rent_str):
    """
    賃料・収入文字列を数値に変換する (円単位)
    「万」または「億」が含まれる場合は parse_price (万円ベース)、そうでない場合は parse_yen (円ベース) を使用する。
    """
    if not rent_str:
        return None
    rent_str = rent_str.strip()
    if "万" in rent_str or "億" in rent_str:
        return parse_price(rent_str)
    return parse_yen(rent_str)


def parse_chidai(chidai_str: str) -> int | None:
    """
    地代（借地料）文字列を月額円（int）に正規化して変換する。
    例:
      - "20年 20,000円" -> 20000
      - "20,000円/月" -> 20000
      - "月額2.5万円" -> 25000
      - "年額120,000円" -> 10000 (月額換算)
      - "24万円/年" -> 20000 (月額換算)
      - "－", "なし" -> None
    """
    if not chidai_str:
        return None
    s = str(chidai_str).strip()
    if not s or s in ["－", "-", "―", "--", "なし", "無", "未定", "相談"]:
        return None

    is_annual = bool(re.search(r'年額|年間|/年|年あたり', s))

    # 1. 万円表記の検出 (例: "2.5万円", "月額2万円", "24万円/年")
    man_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*万(?:\s*円)?', s)
    if man_match:
        try:
            val_man = float(man_match.group(1))
            val_yen = int(val_man * 10000)
            if is_annual:
                return round(val_yen / 12)
            return val_yen
        except (ValueError, TypeError):
            pass

    # 2. 円表記の検出 (例: "20,000円", "20年 20,000円", "120,000円/年")
    # "20年" などの期間数値を誤検出しないよう、"円"の直前の数値を捕捉
    yen_match = re.search(r'([0-9,]+)\s*円', s)
    if yen_match:
        try:
            val_str = yen_match.group(1).replace(",", "").strip()
            val_yen = int(val_str)
            if is_annual:
                return round(val_yen / 12)
            return val_yen
        except (ValueError, TypeError):
            pass

    # 3. 数値のみまたはフォールバック
    clean_num = re.sub(r'[^0-9]', '', s)
    if clean_num:
        try:
            val_yen = int(clean_num)
            if is_annual:
                return round(val_yen / 12)
            return val_yen
        except (ValueError, TypeError):
            pass

    return None
