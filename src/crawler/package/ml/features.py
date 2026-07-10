# -*- coding: utf-8 -*-
import datetime
import logging
import os

# 再調達単価 (万円/㎡) と法定耐用年数
REPLACEMENT_COSTS = {
    'RC': 25.0,
    'SRC': 25.0,
    'S': 20.0,
    'W': 15.0,
    'LS': 15.0,  # 軽量鉄骨
    'default': 18.0
}

LIFESPAN = {
    'RC': 47,
    'SRC': 47,
    'S': 34,
    'W': 22,
    'LS': 34,
    'default': 30
}

def parse_kouzou(kouzou_str):
    """構造文字列から構造カテゴリを分類"""
    if not kouzou_str:
        return 'default'
    kouzou_str = kouzou_str.upper()
    if 'RC' in kouzou_str or '鉄筋コンクリート' in kouzou_str:
        return 'RC'
    if 'SRC' in kouzou_str or '鉄骨鉄筋' in kouzou_str:
        return 'SRC'
    if '鉄骨' in kouzou_str or '重量鉄骨' in kouzou_str or 'Ｓ造' in kouzou_str:
        if '軽量' in kouzou_str:
            return 'LS'
        return 'S'
    if '木' in kouzou_str or 'Ｗ造' in kouzou_str:
        return 'W'
    return 'default'

def calculate_chikunen(chikunengetsu, base_date=None):
    """築年数を算出 (基準日を指定可能。文字列からのパースにも対応)"""
    import re
    if not base_date:
        base_date = datetime.date.today()
    if not chikunengetsu:
        return 20.0
    
    if isinstance(chikunengetsu, str):
        # 和暦の簡易パース (昭和/平成/令和)
        m = re.search(r'(昭和|平成|令和)(\d{1,2})年(?:(\d{1,2})月)?', chikunengetsu)
        if m:
            era = m.group(1)
            year = int(m.group(2))
            month = int(m.group(3)) if m.group(3) else 1
            if era == '昭和':
                gregorian_year = 1925 + year
            elif era == '平成':
                gregorian_year = 1988 + year
            elif era == '令和':
                gregorian_year = 2018 + year
            try:
                dt = datetime.date(gregorian_year, month, 1)
                return (base_date - dt).days / 365.25
            except:
                return 20.0
                
        # 西暦のパース (YYYY-MM-DD or YYYY年MM月など)
        m = re.search(r'(\d{4})[年/\.-](\d{1,2})', chikunengetsu)
        if m:
            try:
                dt = datetime.date(int(m.group(1)), int(m.group(2)), 1)
                return (base_date - dt).days / 365.25
            except:
                pass
                
        # 単純な日付形式 YYYY-MM-DD
        try:
            dt = datetime.datetime.strptime(chikunengetsu, "%Y-%m-%d").date()
            return (base_date - dt).days / 365.25
        except:
            return 20.0
    elif isinstance(chikunengetsu, (datetime.date, datetime.datetime)):
        if isinstance(chikunengetsu, datetime.datetime):
            chikunengetsu = chikunengetsu.date()
        return (base_date - chikunengetsu).days / 365.25
    return 20.0

def build_features(property_obj, property_type, base_date=None, mkt_comparison_master=None):
    """
    共通特徴量エンジニアリング関数 (Djangoモデルオブジェクトまたは辞書に対応)
    """
    from package.models.evaluation import MunicipalPotential, StationPotential, LandPricePotential, HazardMapPotential, UrbanPlanningZonePotential
    
    def get_attr(obj, name, default=None):
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    # 1. 基本属性の抽出
    address1 = get_attr(property_obj, 'address1', '') or ''
    address2 = get_attr(property_obj, 'address2', '') or ''
    station1 = get_attr(property_obj, 'station1', '') or ''
    company = get_attr(property_obj, 'company', 'unknown') or 'unknown'
    
    # 基準日の設定
    if not base_date:
        input_date = get_attr(property_obj, 'inputDate', None)
        if input_date:
            base_date = input_date
        else:
            base_date = datetime.date.today()
            
    chikunengetsu = get_attr(property_obj, 'chikunengetsu', None)
    if not chikunengetsu:
        chikunengetsu = get_attr(property_obj, 'chikunengetsuStr', None)
    chikunen = calculate_chikunen(chikunengetsu, base_date)
    
    walk_min = get_attr(property_obj, 'railwayWalkMinute1', None)
    if walk_min is None: walk_min = 15
    walk_min = int(walk_min)
    
    # 各種面積
    senyu_menseki = get_attr(property_obj, 'senyuMenseki', 0.0)
    tatemono_menseki = get_attr(property_obj, 'tatemonoMenseki', 0.0)
    tochi_menseki = get_attr(property_obj, 'tochiMenseki', 0.0)
    
    area = float(senyu_menseki) if senyu_menseki else 0.0
    tatemono_area = float(tatemono_menseki) if tatemono_menseki else 0.0
    tochi_area = float(tochi_menseki) if tochi_menseki else 0.0
    
    # 2. 自治体ポテンシャルマスタとの結合
    pop_growth = 0.0
    income = 3000
    muni = MunicipalPotential.objects.filter(prefecture=address1, city=address2).first()
    if muni:
        pop_growth = float(muni.population_growth_rate)
        income = muni.average_income
    else:
        # 都道府県の平均にバックオフ
        muni_pref = MunicipalPotential.objects.filter(prefecture=address1)
        if muni_pref.exists():
            pop_growth = sum(float(x.population_growth_rate) for x in muni_pref) / len(muni_pref)
            income = int(sum(x.average_income for x in muni_pref) / len(muni_pref))

    # 3. 駅ポテンシャルマスタとの結合
    passenger_volume = 10000
    if station1:
        station_clean = station1.replace("駅", "")
        station_pot = StationPotential.objects.filter(station_name=station_clean).first()
        if station_pot:
            passenger_volume = station_pot.passenger_volume

    # 4. 用途地域規制（上限容積率・建ぺい率）の正規表現抽出とマスタ引き当て
    import re
    
    def extract_limit(text):
        if not text:
            return None
        text = str(text)
        # "200%" や "建ぺい率60%" などのパーセント数値を抽出
        match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
        if match:
            return float(match.group(1))
        # 数値のみの抽出 (10% - 1000%の範囲に制限)
        match = re.search(r'(\d+(?:\.\d+)?)', text)
        if match:
            val = float(match.group(1))
            if 10.0 <= val <= 1000.0:
                return val
        return None

    max_youseki = None
    max_kenpei = None
    
    youseki_raw = get_attr(property_obj, 'yousekiStr', None) or get_attr(property_obj, 'youseki', None)
    kenpei_raw = get_attr(property_obj, 'kenpeiStr', None) or get_attr(property_obj, 'kenpei', None)
    
    max_youseki = extract_limit(youseki_raw)
    max_kenpei = extract_limit(kenpei_raw)
    
    # 抽出できない場合、用途地域テキストからマスタ引き当てを試みる
    if max_youseki is None or max_kenpei is None:
        zone_keyword = None
        if youseki_raw:
            keywords = [
                "第一種低層", "第二種低層", "第一種中高層", "第二種中高層",
                "第一種住居", "第二種住居", "準住居", "田園住居",
                "近隣商業", "商業", "準工業", "工業", "工業専用"
            ]
            for kw in keywords:
                if kw in str(youseki_raw):
                    zone_keyword = kw
                    break
        
        if zone_keyword:
            try:
                zone_rec = UrbanPlanningZonePotential.objects.filter(zone_name__icontains=zone_keyword).first()
                if zone_rec:
                    if max_youseki is None:
                        max_youseki = float(zone_rec.max_youseki)
                    if max_kenpei is None:
                        max_kenpei = float(zone_rec.max_kenpei)
            except:
                pass
                
    # 最終的なデフォルト値
    if max_youseki is None:
        max_youseki = 200.0
    if max_kenpei is None:
        max_kenpei = 60.0

    # 5. 公示地価ポテンシャルマスタとの結合 (上限容積率に基づく住宅地/商業地価の動的ブレンド)
    if max_youseki <= 150.0:
        weight_comm = 0.0
    elif max_youseki >= 450.0:
        weight_comm = 1.0
    else:
        weight_comm = (max_youseki - 150.0) / 300.0
        
    weight_res = 1.0 - weight_comm
    
    # 住宅地価の取得
    res_price = None
    res_rosenka = None
    res_fixed = None
    lp_res = LandPricePotential.objects.filter(prefecture=address1, city=address2, land_use='residential').first()
    if lp_res:
        res_price = lp_res.average_land_price
        res_rosenka = lp_res.estimated_rosenka_price
        res_fixed = lp_res.estimated_fixed_asset_price
    else:
        lp_pref_res = LandPricePotential.objects.filter(prefecture=address1, land_use='residential')
        if lp_pref_res.exists():
            res_price = sum(x.average_land_price for x in lp_pref_res) / len(lp_pref_res)
            res_rosenka = sum(x.estimated_rosenka_price for x in lp_pref_res if x.estimated_rosenka_price is not None) / len(lp_pref_res)
            res_fixed = sum(x.estimated_fixed_asset_price for x in lp_pref_res if x.estimated_fixed_asset_price is not None) / len(lp_pref_res)
            
    # 商業地価の取得
    comm_price = None
    comm_rosenka = None
    comm_fixed = None
    lp_comm = LandPricePotential.objects.filter(prefecture=address1, city=address2, land_use='commercial').first()
    if lp_comm:
        comm_price = lp_comm.average_land_price
        comm_rosenka = lp_comm.estimated_rosenka_price
        comm_fixed = lp_comm.estimated_fixed_asset_price
    else:
        lp_pref_comm = LandPricePotential.objects.filter(prefecture=address1, land_use='commercial')
        if lp_pref_comm.exists():
            comm_price = sum(x.average_land_price for x in lp_pref_comm) / len(lp_pref_comm)
            comm_rosenka = sum(x.estimated_rosenka_price for x in lp_pref_comm if x.estimated_rosenka_price is not None) / len(lp_pref_comm)
            comm_fixed = sum(x.estimated_fixed_asset_price for x in lp_pref_comm if x.estimated_fixed_asset_price is not None) / len(lp_pref_comm)
            
    # ブレンド価格の計算
    def blend_value(res_val, comm_val, default):
        if res_val is not None and comm_val is not None:
            return int(res_val * weight_res + comm_val * weight_comm)
        elif res_val is not None:
            return int(res_val)
        elif comm_val is not None:
            return int(comm_val)
        return default

    average_land_price = blend_value(res_price, comm_price, 350000)
    estimated_rosenka_price = blend_value(res_rosenka, comm_rosenka, int(average_land_price * 0.8))
    estimated_fixed_asset_price = blend_value(res_fixed, comm_fixed, int(average_land_price * 0.7))

    # 6. 最有効利用特徴量 (Kodate / Apartment) の算出
    digest_volume_ratio = 0.0
    surplus_volume_potential = 0.0
    non_conforming_flag = 0
    
    if property_type in ['kodate', 'apartment'] and tochi_area > 0:
        digest_volume_ratio = (tatemono_area / tochi_area) * 100.0
        surplus_volume_potential = max(0.0, max_youseki - digest_volume_ratio)
        if digest_volume_ratio > max_youseki:
            non_conforming_flag = 1

    # 6. 不動産鑑定メタ特徴量
    # (a) 積算想定価格 (Cost Approach Value)
    kouzou_str = get_attr(property_obj, 'kouzou', '') or ''
    kouzou_cat = parse_kouzou(kouzou_str)
    cost_unit = REPLACEMENT_COSTS[kouzou_cat]
    lifespan = LIFESPAN[kouzou_cat]
    remaining_rate = max(0.1, (lifespan - chikunen) / lifespan)
    
    if property_type == 'mansion':
        land_value = (area * 0.2) * (average_land_price / 10000.0)
        building_value = area * cost_unit * remaining_rate
        cost_approach_value = land_value + building_value
    else:
        land_value = tochi_area * (average_land_price / 10000.0)
        building_value = tatemono_area * cost_unit * remaining_rate
        cost_approach_value = land_value + building_value

    # (b) 比準想定価格 (Market Comparison Value)
    mkt_comparison_value = 0.0
    eval_area = area if property_type == 'mansion' else tatemono_area
    if eval_area <= 0:
        eval_area = 50.0
        
    if mkt_comparison_master:
        age_band = int(chikunen // 10)
        key = (address1, address2, property_type, age_band)
        avg_unit_price = mkt_comparison_master.get(key)
        if avg_unit_price is None:
            # 都道府県レベルでバックオフ
            keys_pref = [k for k in mkt_comparison_master.keys() if k[0] == address1 and k[2] == property_type and k[3] == age_band]
            if keys_pref:
                avg_unit_price = sum(mkt_comparison_master[k] for k in keys_pref) / len(keys_pref)
            else:
                avg_unit_price = 30.0  # 全国平均30万円/㎡
        mkt_comparison_value = avg_unit_price * eval_area
    else:
        mkt_comparison_value = eval_area * (average_land_price / 10000.0)

    # (c) 収益想定価格 (Income Approach Value)
    gross_yield = get_attr(property_obj, 'grossYield', None)
    annual_rent = get_attr(property_obj, 'annualRent', None)
    
    if annual_rent is not None:
        rent = float(annual_rent)
    else:
        # 実需物件は公示地価の5%を想定年間家賃とする
        rent = eval_area * (average_land_price / 10000.0) * 0.05
        
    if gross_yield is not None:
        cap_rate = float(gross_yield) / 100.0
        if cap_rate <= 0: cap_rate = 0.06
    else:
        cap_rate = 0.06
        if income > 600:
            cap_rate = 0.055
        if income > 900:
            cap_rate = 0.045
            
    income_approach_value = rent / cap_rate

    # 7. 耐震基準フラグ (新旧耐震の判定: 1981年6月1日以降が新耐震)
    is_shin_taishin = 1  # デフォルト新耐震
    if chikunengetsu and isinstance(chikunengetsu, datetime.date):
        if chikunengetsu < datetime.date(1981, 6, 1):
            is_shin_taishin = 0
    else:
        # 築年月がない場合のフォールバック: 築45年超なら旧耐震と判定
        if chikunen > 45.0:
            is_shin_taishin = 0

    # 8. ハザードマップ災害リスク (浸水・土砂リスクの追加)
    flood_risk_level = 0
    landslide_risk_level = 0
    try:
        hz = HazardMapPotential.objects.filter(prefecture=address1, city=address2).first()
        if hz:
            flood_risk_level = int(hz.flood_risk_level)
            landslide_risk_level = int(hz.landslide_risk_level)
    except:
        pass

    # 特徴量辞書を返却
    feats = {
        "area": area if property_type == 'mansion' else tatemono_area,
        "tochi_menseki": tochi_area,
        "chikunen": chikunen,
        "walk_min": walk_min,
        "kanrihi": int(get_attr(property_obj, 'kanrihi', 0) or 0),
        "syuzen": int(get_attr(property_obj, 'syuzenTsumitate', 0) or 0),
        "pop_growth": pop_growth,
        "income": income,
        "passenger_volume": passenger_volume,
        "average_land_price": average_land_price,
        "estimated_rosenka_price": estimated_rosenka_price,
        "estimated_fixed_asset_price": estimated_fixed_asset_price,
        "digest_volume_ratio": digest_volume_ratio,
        "surplus_volume_potential": surplus_volume_potential,
        "non_conforming_flag": non_conforming_flag,
        "cost_approach_value": cost_approach_value,
        "mkt_comparison_value": mkt_comparison_value,
        "income_approach_value": income_approach_value,
        "gross_yield": float(gross_yield) if gross_yield else 0.0,
        "annual_rent": float(annual_rent) if annual_rent else 0.0,
        "is_shin_taishin": is_shin_taishin,
        "flood_risk_level": flood_risk_level,
        "landslide_risk_level": landslide_risk_level,
        "max_youseki": max_youseki,
        "max_kenpei": max_kenpei
    }
    
    # カテゴリカル（文字列）
    feats["prefecture"] = address1
    feats["city"] = address2
    feats["station"] = station1
    feats["company"] = company
    feats["kouzou"] = kouzou_str
    
    return feats
