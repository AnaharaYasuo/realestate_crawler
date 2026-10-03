import datetime
import re
import unicodedata
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from package.utils.converter import parse_chikunengetsu, parse_price, parse_yen

TSUBO_TO_M2_RATE = Decimal('3.30578')
M2_TO_TSUBO_RATE = Decimal('0.3025')


@dataclass
class NormalizedArea:
    area_m2: Decimal
    area_tsubo: Decimal
    is_wall_center: bool = False
    is_inner_measurement: bool = False


class DataNormalizer:
    """
    全パーサー共通のデータ正規化・クレンジングユーティリティ
    docs/3_data_models/data_normalization_and_cleansing.md に準拠
    """

    @classmethod
    def clean_text(cls, text: str | None) -> str:
        """
        全角英数・記号を半角へ統一し、不可視文字や連続空白を集約・トリムする
        """
        if not text:
            return ""
        # NFKC正規化で全角英数・記号を半角統一
        normalized = unicodedata.normalize('NFKC', str(text))
        # 改行・タブ・全角半角スペースを単一スペースに集約
        cleaned = re.sub(r'[\r\n\t\s]+', ' ', normalized).strip()
        return cleaned

    @classmethod
    def normalize_price(cls, price_str: str | None) -> int | None:
        """
        価格文字列を円単位整数（int）に正規化
        例: "3,980万円" -> 39800000, "1億2,500万円" -> 125000000, "5000円" -> 5000
        """
        if not price_str:
            return None
        cleaned = cls.clean_text(price_str)
        if not cleaned or cleaned in ("-", "―", "未定", "相談", "なし"):
            return None

        # 付帯文字（税込、非課税、相談等）を除去
        cleaned = re.sub(r'\([^)]*\)|（[^）]*）', '', cleaned)
        cleaned = re.sub(r'税込|税別|非課税|相談', '', cleaned).strip()

        # 億・万が含まれる場合は parse_price
        if "億" in cleaned or "万" in cleaned:
            return parse_price(cleaned)
        # 円単位
        if "円" in cleaned:
            return parse_yen(cleaned)
        # 数字のみの場合
        match = re.search(r'^\d+$', cleaned.replace(',', ''))
        if match:
            return int(match.group(0))
        return None

    @classmethod
    def normalize_area(cls, area_str: str | None) -> NormalizedArea | None:
        """
        面積文字列を平米（㎡）および坪（坪）の Decimal に正規化
        壁芯・内法などの属性フラグも分離抽出
        """
        if not area_str:
            return None
        cleaned = cls.clean_text(area_str)
        if not cleaned or cleaned in ("-", "―", "未定", "相談", "不詳", "なし"):
            return None

        is_wall_center = "壁芯" in cleaned
        is_inner_measurement = "内法" in cleaned

        # 坪数判定
        if "坪" in cleaned:
            match = re.search(r'([\d.]+)\s*坪', cleaned)
            if match:
                tsubo = Decimal(match.group(1)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                m2 = (tsubo * TSUBO_TO_M2_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                return NormalizedArea(
                    area_m2=m2,
                    area_tsubo=tsubo,
                    is_wall_center=is_wall_center,
                    is_inner_measurement=is_inner_measurement,
                )

        # ㎡・m2 判定
        match = re.search(r'([\d.]+)\s*(?:㎡|m2|m²)', cleaned)
        if not match:
            match = re.search(r'([\d.]+)', cleaned)

        if match:
            m2 = Decimal(match.group(1)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            tsubo = (m2 * M2_TO_TSUBO_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return NormalizedArea(
                area_m2=m2,
                area_tsubo=tsubo,
                is_wall_center=is_wall_center,
                is_inner_measurement=is_inner_measurement,
            )

        return None

    @classmethod
    def normalize_built_date(cls, date_str: str | None) -> datetime.date | None:
        """
        築年月文字列を datetime.date (日=1日) に正規化
        和暦（令和・平成・昭和）や月省略（年築）にも対応
        """
        if not date_str:
            return None
        cleaned = cls.clean_text(date_str)
        if not cleaned or cleaned in ("-", "―", "不詳", "未定", "なし"):
            return None

        # 年築（月省略）の特別ハンドリング: "2015年築" -> "2015年1月"
        year_only_match = re.search(r'(\d{4})年(?:築)?$', cleaned)
        if year_only_match:
            return datetime.date(int(year_only_match.group(1)), 1, 1)

        wareki_year_only = re.search(r'(令和|平成|昭和)(\d{1,2}|元)年(?:築)?$', cleaned)
        if wareki_year_only:
            era = wareki_year_only.group(1)
            y_str = wareki_year_only.group(2)
            year = 1 if y_str == '元' else int(y_str)
            era_offsets = {'昭和': 1925, '平成': 1988, '令和': 2018}
            return datetime.date(era_offsets[era] + year, 1, 1)

        return parse_chikunengetsu(cleaned)
