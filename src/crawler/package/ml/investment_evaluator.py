# -*- coding: utf-8 -*-
import math
import logging
from decimal import Decimal
from django.utils import timezone
from package.models.evaluation import LandPricePotential
from django.db import models

logger = logging.getLogger(__name__)

# --- 投資シミュレーション前提パラメータ ---
DEFAULT_DOWN_PAYMENT_RATIO = 0.10  # 自己資金比率 (10%)
DEFAULT_LOAN_INTEREST_RATE = 0.025  # 融資金利 (2.5%)
DEFAULT_OPEX_RATIO = 0.20           # 運営経費率 (20%)

# --- 構造別 法定耐用年数と再調達単価（平米単価：万円） ---
STRUCTURE_PARAMS = {
    "RC": {"lifespan": 47, "unit_price": 20.0},
    "SRC": {"lifespan": 47, "unit_price": 20.0},
    "S": {"lifespan": 34, "unit_price": 15.0},   # 鉄骨造
    "W": {"lifespan": 22, "unit_price": 12.0},   # 木造
}

def detect_structure_type(kouzou_str):
    """
    構造テキストから簡易的に構造カテゴリ(RC, SRC, S, W)を判定する。
    """
    if not kouzou_str:
        return "W"  # デフォルトは木造
    
    kouzou_str = kouzou_str.upper()
    if "SRC" in kouzou_str or "鉄骨鉄筋" in kouzou_str:
        return "SRC"
    elif "RC" in kouzou_str or "鉄筋コン" in kouzou_str:
        return "RC"
    elif "鉄骨" in kouzou_str or "軽量鉄骨" in kouzou_str or "鋼造" in kouzou_str or "S造" in kouzou_str:
        return "S"
    elif "木" in kouzou_str or "W" in kouzou_str:
        return "W"
    
    return "W"  # 判別できない場合は保守的に木造

def parse_chikunen(chikunengetsu_date_or_str):
    """
    築年数を算出する。
    日付型または文字列から経過年数を計算。
    """
    if not chikunengetsu_date_or_str:
        return 20  # 不明な場合は築20年と仮定
        
    current_year = timezone.now().year
    
    # Date型の場合
    if hasattr(chikunengetsu_date_or_str, "year"):
        return max(0, current_year - chikunengetsu_date_or_str.year)
        
    # 文字列型の場合
    chikunen_str = str(chikunengetsu_date_or_str)
    import re
    years = re.findall(r'\d{4}', chikunen_str)
    if years:
        return max(0, current_year - int(years[0]))
    
    # 元号対応（簡易）
    if "平成" in chikunen_str:
        m = re.search(r'平成(\d+|元)年', chikunen_str)
        if m:
            val = m.group(1)
            h_year = 1 if val == "元" else int(val)
            return max(0, current_year - (1988 + h_year))
    elif "昭和" in chikunen_str:
        m = re.search(r'昭和(\d+)年', chikunen_str)
        if m:
            return max(0, current_year - (1925 + int(m.group(1))))
    elif "令和" in chikunen_str:
        m = re.search(r'令和(\d+|元)年', chikunen_str)
        if m:
            val = m.group(1)
            r_year = 1 if val == "元" else int(val)
            return max(0, current_year - (2018 + r_year))

    # 築年数の直接数値表記 (例: "築25年")
    m = re.search(r'築(\d+)年', chikunen_str)
    if m:
        return int(m.group(1))

    return 20  # デフォルト

def calculate_loan_term(structure_type, age):
    """
    融資期間を計算する。
    基本は残存耐用年数（耐用年数 - 築年数）だが、
    銀行の期間おまけ考慮のため、下限を20年、上限を35年として融資期間をシミュレート。
    """
    lifespan = STRUCTURE_PARAMS.get(structure_type, STRUCTURE_PARAMS["W"])["lifespan"]
    remaining = lifespan - age
    
    # 融資期間シミュレーション（残存耐用年数が短くても最低20年、最長35年）
    loan_term = max(20, min(35, remaining))
    return int(loan_term)

def get_average_land_price(prefecture, city):
    """
    LandPricePotential マスタから該当市区町村の平均公示地価を取得する。
    見つからない場合は都道府県内の平均やデフォルト値を使用。
    """
    if not prefecture or not city:
        return 100000  # デフォルト 10万円/㎡
        
    prices = LandPricePotential.objects.filter(
        prefecture__contains=prefecture,
        city__contains=city
    )
    if prices.exists():
        res_price = prices.filter(land_use='residential').first()
        if res_price:
            return res_price.average_land_price
        return prices.first().average_land_price
        
    prices_pref = LandPricePotential.objects.filter(prefecture__contains=prefecture)
    if prices_pref.exists():
        avg = prices_pref.aggregate(models.Avg('average_land_price'))['average_land_price__avg']
        if avg:
            return int(avg)
            
    return 100000  # デフォルト 10万円/㎡

def calculate_sekisan_price(property_obj, prefecture, city):
    """
    物件の積算価格を算出する。
    積算価格 ＝ 土地評価額 ＋ 建物評価額
    """
    tochi_menseki = float(getattr(property_obj, "tochiMenseki", 0.0) or 0.0)
    tatemono_menseki = float(getattr(property_obj, "tatemonoMenseki", 0.0) or getattr(property_obj, "senyuMenseki", 0.0) or 0.0)
    kouzou_str = getattr(property_obj, "kouzou", "")
    chikunen_str = getattr(property_obj, "chikunengetsuStr", "")
    chikunen_date = getattr(property_obj, "chikunengetsu", None)
    
    # 1. 土地評価額
    land_price_per_m2 = get_average_land_price(prefecture, city)
    land_value = tochi_menseki * land_price_per_m2 / 10000.0  # 万円単位
    
    # 2. 建物評価額
    struct_type = detect_structure_type(kouzou_str)
    age = parse_chikunen(chikunen_date if chikunen_date else chikunen_str)
    
    struct_info = STRUCTURE_PARAMS.get(struct_type, STRUCTURE_PARAMS["W"])
    lifespan = struct_info["lifespan"]
    unit_price = struct_info["unit_price"]  # 万円/㎡
    
    # 残存耐用年数比率の計算
    remaining = max(0, lifespan - age)
    remaining_ratio = float(remaining) / float(lifespan) if lifespan > 0 else 0.0
    
    # 建物再調達価格 × 面積 × 残存耐用年数比率
    building_value = tatemono_menseki * unit_price * remaining_ratio
    
    sekisan_price = land_value + building_value
    logger.info(f"Sekisan Price Calc: Land={land_value:.1f}万 (Area={tochi_menseki}㎡, Price/㎡={land_price_per_m2}), Building={building_value:.1f}万 (Area={tatemono_menseki}㎡, Age={age}, Type={struct_type}), Total={sekisan_price:.1f}万")
    
    return int(sekisan_price)

def calculate_pmt(principal, annual_rate, years):
    """
    元利均等返済額（年間）を算出する。
    """
    if principal <= 0 or years <= 0:
        return 0
    if annual_rate <= 0:
        return principal / years
        
    r = annual_rate / 12.0
    n = years * 12
    pmt_monthly = principal * (r * math.pow(1 + r, n)) / (math.pow(1 + r, n) - 1)
    return pmt_monthly * 12

def evaluate_investment_property(property_obj, evaluation_record):
    """
    投資用物件の収支・融資評価を行い、PropertyEvaluation レコードを更新する。
    """
    price_man = float(property_obj.price) / 10000.0 if property_obj.price else 0.0
    if price_man <= 0.0:
        logger.warning(f"Skipping investment evaluation: price is 0 or invalid for {property_obj.pageUrl}")
        return evaluation_record

    if price_man < 10.0:
        logger.warning(f"Skipping investment evaluation: price is abnormally low ({price_man:.1f} million yen) for {property_obj.pageUrl}")
        return evaluation_record

    # 1. 住所から市区町村を取得
    address = getattr(property_obj, "address", "")
    prefecture = ""
    city = ""
    import re
    pref_match = re.match(r'^(東京都|京都府|大阪府|北海道|[^県]+[県])', address)
    if pref_match:
        prefecture = pref_match.group(1)
        city_part = address[len(prefecture):]
        city_match = re.match(r'^([^市町村]+[市区町村])', city_part)
        if city_match:
            city = city_match.group(1)

    # 2. 積算価格の算出
    sekisan_price = calculate_sekisan_price(property_obj, prefecture, city)
    sekisan_ratio = (sekisan_price / price_man * 100.0) if price_man > 0 else 0.0

    # 3. 賃料の取得と収支計算
    annual_rent = float(getattr(property_obj, "annualRent", 0) or 0)
    if annual_rent <= 0:
        yield_pct = float(getattr(property_obj, "grossYield", 0) or 0)
        if yield_pct > 0:
            annual_rent = price_man * (yield_pct / 100.0)
            
    if annual_rent <= 0:
        annual_rent = price_man * 0.08
        
    if annual_rent > 100000:
        annual_rent_man = annual_rent / 10000.0
    else:
        annual_rent_man = annual_rent

    noi = annual_rent_man * (1.0 - DEFAULT_OPEX_RATIO)

    # 借地権の場合、支払地代をNOIから差し引く (更地想定価格の 1.0% / 年 と仮定)
    tochikenri = getattr(property_obj, "tochikenri", "") or ""
    if tochikenri and any(x in tochikenri.lower() for x in ["借地", "賃借", "定期"]):
        base_price = sekisan_price if sekisan_price > 0 else price_man
        land_rent_annual_man = base_price * 0.010
        noi = max(0.0, noi - land_rent_annual_man)

    # 4. ローン返済シミュレーション (再建築不可の場合は融資不可のため頭金100%)
    biko = getattr(property_obj, "biko", "") or ""
    is_saikenchiku_fuka = any("再建築不可" in str(x) for x in [tochikenri, biko])
    
    if is_saikenchiku_fuka:
        down_payment = price_man
        loan_principal = 0.0
    else:
        down_payment = price_man * DEFAULT_DOWN_PAYMENT_RATIO
        loan_principal = price_man - down_payment
    
    kouzou_str = getattr(property_obj, "kouzou", "")
    struct_type = detect_structure_type(kouzou_str)
    age = parse_chikunen(getattr(property_obj, "chikunengetsu", None) or getattr(property_obj, "chikunengetsuStr", ""))
    
    loan_term = calculate_loan_term(struct_type, age)
    annual_repayment = calculate_pmt(loan_principal, DEFAULT_LOAN_INTEREST_RATE, loan_term)

    # 5. キャッシュフロー & 指標計算
    cf = noi - annual_repayment
    dscr = (noi / annual_repayment) if annual_repayment > 0 else 9.99
    coc = (cf / down_payment * 100.0) if down_payment > 0 else 0.0

    # --- スコア化ロジック ---
    
    coc_score = min(100.0, max(0.0, coc / 12.0 * 100.0))
    cf_yield = (cf / price_man * 100.0) if price_man > 0 else 0.0
    cf_yield_score = min(100.0, max(0.0, cf_yield / 2.0 * 100.0))
    
    cashflow_score = (coc_score + cf_yield_score) / 2.0

    sekisan_score = min(100.0, max(0.0, (sekisan_ratio - 50.0) / 50.0 * 100.0))
    dscr_score_val = min(100.0, max(0.0, (float(dscr) - 1.0) / 0.3 * 100.0))
    
    finance_score = (sekisan_score * 0.7) + (dscr_score_val * 0.3)

    predicted_price = float(evaluation_record.second_stage_predicted_price or evaluation_record.first_stage_predicted_price or 0.0)
    if predicted_price > 0 and price_man > 0:
        asset_ratio = predicted_price / price_man
        asset_score = min(100.0, max(0.0, (asset_ratio - 0.8) / 0.4 * 100.0))
    else:
        asset_score = 50.0

    total_investment_score = (asset_score * 0.4) + (cashflow_score * 0.4) + (finance_score * 0.2)

    # 制限用のヘルパー関数
    def limit_decimal(val, max_val=9999.99, min_val=-9999.99):
        try:
            return Decimal(max(min_val, min(max_val, float(val))))
        except Exception:
            return Decimal(0.0)

    # --- PropertyEvaluationレコードの更新 ---
    evaluation_record.estimated_sekisan_price = int(sekisan_price)
    evaluation_record.net_operating_income = int(noi)
    evaluation_record.debt_service = int(annual_repayment)
    evaluation_record.cash_flow = int(cf)
    evaluation_record.dscr = limit_decimal(dscr)
    evaluation_record.coc_return = limit_decimal(coc)
    evaluation_record.sekisan_ratio = limit_decimal(sekisan_ratio)
    evaluation_record.cashflow_score = float(f"{cashflow_score:.2f}")
    evaluation_record.finance_score = float(f"{finance_score:.2f}")
    evaluation_record.total_investment_score = float(f"{total_investment_score:.2f}")
    
    evaluation_record.investment_score = float(f"{total_investment_score:.2f}")
    
    logger.info(f"Investment Eval Result for {property_obj.pageUrl}: Price={price_man:.1f}万, Sekisan={sekisan_price}万 ({sekisan_ratio:.1f}%), NOI={noi:.1f}万, Repayment={annual_repayment:.1f}万, CF={cf:.1f}万, DSCR={dscr:.2f}, CoC={coc:.2f}%, TotalScore={total_investment_score:.1f}")
    
    return evaluation_record
