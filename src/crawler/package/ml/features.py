# -*- coding: utf-8 -*-
import datetime
import logging
import os
from typing import Dict, Tuple, Any, Optional

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
            gregorian_year = 2000
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

# グローバルキャッシュ変数
_muni_cache: Dict[Tuple[str, str], Any] = {}
_muni_pref_cache: Dict[str, list] = {}
_station_cache: Dict[str, Any] = {}
_lp_cache: Dict[Tuple[str, str, str], Any] = {}
_lp_pref_res_cache: Dict[str, list] = {}
_lp_pref_comm_cache: Dict[str, list] = {}
_hazard_cache: Dict[Tuple[str, str], Any] = {}
_zone_cache: Dict[str, Any] = {}

def _init_global_caches():
    """
    特徴量抽出のボトルネックを解消するため、
    全 Potential 関連マスタを一括でインメモリキャッシュします。
    """
    global _muni_cache, _muni_pref_cache, _station_cache, _lp_cache, _lp_pref_res_cache, _lp_pref_comm_cache, _hazard_cache, _zone_cache
    from package.models.evaluation import MunicipalPotential, StationPotential, LandPricePotential, HazardMapPotential, UrbanPlanningZonePotential

    if not _muni_cache:
        for m in MunicipalPotential.objects.all():
            _muni_cache[(m.prefecture, m.city)] = m
            _muni_pref_cache.setdefault(m.prefecture, []).append(m)
            
    if not _station_cache:
        for s in StationPotential.objects.all():
            _station_cache[s.station_name] = s
            
    if not _lp_cache:
        for lp in LandPricePotential.objects.all():
            _lp_cache[(lp.prefecture, lp.city, lp.land_use)] = lp
            if lp.land_use == 'residential':
                _lp_pref_res_cache.setdefault(lp.prefecture, []).append(lp)
            elif lp.land_use == 'commercial':
                _lp_pref_comm_cache.setdefault(lp.prefecture, []).append(lp)
            
    if not _hazard_cache:
        for hz in HazardMapPotential.objects.all():
            _hazard_cache[(hz.prefecture, hz.city)] = hz
            
    if not _zone_cache:
        for z in UrbanPlanningZonePotential.objects.all():
            _zone_cache[z.zone_name] = z

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
    
    if not address1 or not address2:
        full_address = get_attr(property_obj, 'address', '') or ''
        import re
        m = re.match(r'^(東京都|大阪府|京都府|北海道|[^県]+県)([^区市町]+[区市町])', full_address)
        if m:
            if not address1:
                address1 = m.group(1)
            if not address2:
                address2 = m.group(2)
                
    station1 = get_attr(property_obj, 'station1', '') or ''
    company = get_attr(property_obj, 'company', 'unknown') or 'unknown'
    
    from decimal import Decimal
    def safe_float(val, default_val):
        if val is None:
            return default_val
        if isinstance(val, (int, float, Decimal)):
            return float(val)
        if isinstance(val, str):
            m_val = re.search(r'([0-9\.]+)', val)
            if m_val:
                try:
                    return float(m_val.group(1))
                except:
                    pass
        return default_val

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
    
    # グローバルキャッシュの初期化
    _init_global_caches()
    
    # 2. 自治体ポテンシャルマスタとの結合
    pop_growth = 0.0
    income = 3000
    total_population = 100000
    income_growth_rate = 0.0
    muni = _muni_cache.get((address1, address2))
    if muni:
        pop_growth = float(muni.population_growth_rate)
        income = muni.average_income
        total_population = muni.total_population if muni.total_population is not None else 100000
        income_growth_rate = float(muni.income_growth_rate) if muni.income_growth_rate is not None else 0.0
    else:
        muni_pref_vals = _muni_pref_cache.get(address1, [])
        if muni_pref_vals:
            pop_growth = sum(float(x.population_growth_rate) for x in muni_pref_vals) / len(muni_pref_vals)
            income = int(sum(x.average_income for x in muni_pref_vals) / len(muni_pref_vals))
            total_population = int(sum(x.total_population for x in muni_pref_vals if x.total_population is not None) / len(muni_pref_vals)) if any(x.total_population is not None for x in muni_pref_vals) else 100000
            income_growth_rate = sum(float(x.income_growth_rate) for x in muni_pref_vals if x.income_growth_rate is not None) / len(muni_pref_vals) if any(x.income_growth_rate is not None for x in muni_pref_vals) else 0.0

    # 3. 駅ポテンシャルマスタとの結合
    passenger_volume = 10000
    if station1:
        station_clean = station1.replace("駅", "")
        station_pot = _station_cache.get(station_clean)
        if station_pot:
            passenger_volume = station_pot.passenger_volume

    # 地域の人口密度（density）に基づき、駅距離に対するペナルティ倍率を動的調整する
    # 人口密度が 4,000人/㎢ 以上の過密・主要交通エリアは影響度 1.0 (フルに徒歩分数が価格へ影響)
    # 人口密度が減る（地方や郊外のマイカー社会）に従って、駅距離の影響度を最低 0.4 まで逓減
    pop_density = 4000.0
    if muni and muni.population_density is not None:
        pop_density = float(muni.population_density)
    else:
        muni_pref_vals = _muni_pref_cache.get(address1, [])
        if muni_pref_vals:
            pop_density = sum(float(x.population_density) for x in muni_pref_vals if x.population_density is not None) / len(muni_pref_vals) if any(x.population_density is not None for x in muni_pref_vals) else 4000.0

    walk_min_penalty_scale = max(0.4, min(1.0, 0.4 + 0.6 * (pop_density / 4000.0)))
    effective_walk_min = float(walk_min) * walk_min_penalty_scale

    # 4. 用途地域規制（上限容積率・建ぺい率）の正規表現抽出とマスタ引き当て
    import re
    
    def extract_limit(text):
        if not text:
            return None
        text = str(text)
        match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
        if match:
            return float(match.group(1))
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
                zone_rec = None
                for name, z in _zone_cache.items():
                    if zone_keyword in name:
                        zone_rec = z
                        break
                if zone_rec:
                    if max_youseki is None:
                        max_youseki = float(zone_rec.max_youseki)
                    if max_kenpei is None:
                        max_kenpei = float(zone_rec.max_kenpei)
            except:
                pass
                
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
    lp_res = _lp_cache.get((address1, address2, 'residential'))
    if lp_res:
        res_price = lp_res.average_land_price
        res_rosenka = lp_res.estimated_rosenka_price
        res_fixed = lp_res.estimated_fixed_asset_price
    else:
        lp_pref_res = _lp_pref_res_cache.get(address1, [])
        if lp_pref_res:
            res_price = sum(x.average_land_price for x in lp_pref_res) / len(lp_pref_res)
            res_rosenka = sum(x.estimated_rosenka_price for x in lp_pref_res if x.estimated_rosenka_price is not None) / len(lp_pref_res)
            res_fixed = sum(x.estimated_fixed_asset_price for x in lp_pref_res if x.estimated_fixed_asset_price is not None) / len(lp_pref_res)
            
    # 商業地価の取得
    comm_price = None
    comm_rosenka = None
    comm_fixed = None
    lp_comm = _lp_cache.get((address1, address2, 'commercial'))
    if lp_comm:
        comm_price = lp_comm.average_land_price
        comm_rosenka = lp_comm.estimated_rosenka_price
        comm_fixed = lp_comm.estimated_fixed_asset_price
    else:
        lp_pref_comm = _lp_pref_comm_cache.get(address1, [])
        if lp_pref_comm:
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

    # 変動率の取得とブレンド
    res_growth = float(lp_res.land_price_growth_rate) if lp_res and lp_res.land_price_growth_rate is not None else None
    comm_growth = float(lp_comm.land_price_growth_rate) if lp_comm and lp_comm.land_price_growth_rate is not None else None
    
    if res_growth is None:
        lp_pref_res = _lp_pref_res_cache.get(address1, [])
        if lp_pref_res:
            res_growth = sum(float(x.land_price_growth_rate) for x in lp_pref_res if x.land_price_growth_rate is not None) / len(lp_pref_res) if any(x.land_price_growth_rate is not None for x in lp_pref_res) else 0.0
            
    if comm_growth is None:
        lp_pref_comm = _lp_pref_comm_cache.get(address1, [])
        if lp_pref_comm:
            comm_growth = sum(float(x.land_price_growth_rate) for x in lp_pref_comm if x.land_price_growth_rate is not None) / len(lp_pref_comm) if any(x.land_price_growth_rate is not None for x in lp_pref_comm) else 0.0

    def blend_float_value(res_val, comm_val, default):
        if res_val is not None and comm_val is not None:
            return float(res_val * weight_res + comm_val * weight_comm)
        elif res_val is not None:
            return float(res_val)
        elif comm_val is not None:
            return float(comm_val)
        return default

    land_price_growth_rate = blend_float_value(res_growth, comm_growth, 0.0)

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
            keys_pref = [k for k in mkt_comparison_master.keys() if k[0] == address1 and k[2] == property_type and k[3] == age_band]
            if keys_pref:
                avg_unit_price = sum(mkt_comparison_master[k] for k in keys_pref) / len(keys_pref)
            else:
                avg_unit_price = 30.0
        mkt_comparison_value = avg_unit_price * eval_area
    else:
        mkt_comparison_value = eval_area * (average_land_price / 10000.0)

    # (c) 収益想定価格 (Income Approach Value)
    gross_yield = get_attr(property_obj, 'grossYield', None)
    annual_rent = get_attr(property_obj, 'annualRent', None)
    
    if annual_rent is not None:
        rent = float(annual_rent)
    else:
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
        if chikunen > 45.0:
            is_shin_taishin = 0

    # 8. ハザードマップ災害リスク (浸水・土砂リスクの追加)
    flood_risk_level = 0
    landslide_risk_level = 0
    try:
        hz = _hazard_cache.get((address1, address2))
        if hz:
            flood_risk_level = int(hz.flood_risk_level)
            landslide_risk_level = int(hz.landslide_risk_level)
    except:
        pass

    # 土地（tochi）固有の鑑定特徴量の算出
    maguchi_val = 6.0
    road_width_val = 4.0
    setback_ratio = 0.0
    actual_volume_limit = max_youseki
    volume_digest_factor = 1.0
    road_condition_factor = 1.0
    frontage_penalty_factor = 1.0
    residual_land_value = 0.0
    road_direction_str = ""
    road_type_str = ""
    road_structure_str = ""
    chimoku_str = ""
    
    if property_type in ['tochi', 'kodate', 'apartment']:
        import re
        if property_type == 'tochi':
            # 主要評価面積を土地面積とする
            area = tochi_area
            
        maguchi = get_attr(property_obj, 'maguchi', None)
        road_width = get_attr(property_obj, 'roadWidth', None) or get_attr(property_obj, 'douroHaba', None)
        road_direction_str = get_attr(property_obj, 'roadDirection', '') or get_attr(property_obj, 'douroMuki', '') or ''
        road_type_str = get_attr(property_obj, 'roadType', '') or get_attr(property_obj, 'douroKubun', '') or ''
        road_structure_str = get_attr(property_obj, 'roadStructure', '') or get_attr(property_obj, 'setsudou', '') or ''
        chimoku_str = get_attr(property_obj, 'chimoku', '') or ''
        
        # 動的パースのフォールバックロジック (カラムに値が入っていない場合)
        raw_setsudou = get_attr(property_obj, 'setsudou', '') or ''
        
        if not road_width and raw_setsudou:
            m_width = re.search(r'([0-9\.]+)\s*[mｍ]', raw_setsudou)
            if m_width:
                road_width = float(m_width.group(1))
                
        if not maguchi and raw_setsudou:
            m_maguchi = re.search(r'(?:間口|接面)\s*(?:約)?\s*([0-9\.]+)\s*[mｍ]', raw_setsudou)
            if m_maguchi:
                maguchi = float(m_maguchi.group(1))
                
        if not road_direction_str and raw_setsudou:
            for direction in ["北東", "北西", "南東", "南西", "東", "西", "南", "北"]:
                if direction in raw_setsudou:
                    road_direction_str = direction
                    break
                    
        if not road_type_str and raw_setsudou:
            if "公道" in raw_setsudou:
                road_type_str = "公道"
            elif "私道" in raw_setsudou:
                road_type_str = "私道"
        
        maguchi_val = safe_float(maguchi, 6.0)
        road_width_val = safe_float(road_width, 4.0)
        
        # ① セットバック（後退）面積比率
        if road_width_val < 4.0:
            setback_width = (4.0 - road_width_val) / 2.0
            setback_area = maguchi_val * setback_width
            if tochi_area > 0:
                setback_ratio = min(1.0, setback_area / tochi_area)
                
        # ② 実質上限容積率制限 (幅員制限)
        youto = get_attr(property_obj, 'youtoChiiki', '') or ''
        is_commercial = any(x in youto for x in ["商業", "近隣商業", "工業", "準工業", "工業専用"])
        multiplier = 0.6 if is_commercial else 0.4
        road_volume_limit = road_width_val * multiplier * 100.0
        actual_volume_limit = min(max_youseki, road_volume_limit)
        
        # ③ 北側道路緩和・容積消化効率係数
        if "北" in road_direction_str and road_width_val >= 4.0:
            volume_digest_factor = 1.15
        elif "南" in road_direction_str:
            est_depth = tochi_area / maguchi_val if maguchi_val > 0 else 10.0
            if est_depth < 10.0:
                volume_digest_factor = 0.85
                
        # ④ 接道条件加算補正
        if any(x in road_structure_str for x in ["角地", "準角地", "三方", "四方"]):
            road_condition_factor = 1.05
        elif any(x in road_structure_str for x in ["二方", "両面道路"]):
            road_condition_factor = 1.03
            
        # ⑤ 間口狭小ペナルティ
        if maguchi_val < 2.0:
            frontage_penalty_factor = 0.25
        elif maguchi_val < 4.0:
            frontage_penalty_factor = 0.90
            
        # ⑥ 土地残余法比準地価
        residual_land_value = tochi_area * (average_land_price / 10000.0) * volume_digest_factor * road_condition_factor * frontage_penalty_factor * (1.0 - setback_ratio)

    # ⑦ 最大建築面積、最大延床面積 (前面道路幅員制限考慮)
    max_building_area = 0.0
    max_floor_area = 0.0
    
    # 角地による建ぺい率緩和 (+10.0%)
    road_struct = get_attr(property_obj, 'roadStructure', '') or get_attr(property_obj, 'setsudou', '') or ''
    is_corner = any(x in str(road_struct) for x in ["角地", "準角地", "三方", "四方"])
    effective_kenpei = max_kenpei
    if is_corner:
        effective_kenpei = min(100.0, max_kenpei + 10.0)

    if tochi_area > 0:
        max_building_area = tochi_area * (effective_kenpei / 100.0)
        vol_limit = actual_volume_limit if 'actual_volume_limit' in locals() else max_youseki
        max_floor_area = tochi_area * (vol_limit / 100.0)

    # ⑧ かげ地割合（吉野金次式）の簡易抽出
    biko_text = get_attr(property_obj, 'biko', '') or ''
    tochi_text = get_attr(property_obj, 'tochikenri', '') or ''
    
    is_hatasao = any(x in str(biko_text) or x in str(tochi_text) for x in ["旗竿", "路地状", "敷地延長", "敷延"])
    is_fuseigei = any(x in str(biko_text) or x in str(tochi_text) for x in ["不整形", "変形地", "台形地", "袋地"])
    
    # オブジェクトに明示的なかげ地割合属性がある場合は優先
    kagechi_ratio = safe_float(get_attr(property_obj, 'kagechi_ratio', None), None)
    if kagechi_ratio is None:
        if is_hatasao:
            kagechi_ratio = 0.25 # 旗竿地は平均的にかげ地割合25%と仮定
        elif is_fuseigei:
            kagechi_ratio = 0.15 # 不整形地は平均的にかげ地割合15%と仮定
        else:
            kagechi_ratio = 0.0

    # 特徴量辞書を返却
    feats = {
        "area": area if property_type in ['mansion', 'tochi'] else tatemono_area,
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
        "max_kenpei": max_kenpei,
        # 土地用追加特徴量
        "maguchi": maguchi_val,
        "road_width": road_width_val,
        "setback_ratio": setback_ratio,
        "actual_volume_limit": actual_volume_limit,
        "volume_digest_factor": volume_digest_factor,
        "road_condition_factor": road_condition_factor,
        "frontage_penalty_factor": frontage_penalty_factor,
        "residual_land_value": residual_land_value,
        "max_building_area": max_building_area,
        "max_floor_area": max_floor_area,
        "kagechi_ratio": kagechi_ratio,
        "total_population": total_population,
        "income_growth_rate": income_growth_rate,
        "land_price_growth_rate": land_price_growth_rate,
        "effective_walk_min": effective_walk_min,
        "population_density": pop_density
    }
    
    # カテゴリカル（文字列）
    feats["prefecture"] = address1
    feats["city"] = address2
    feats["station"] = station1
    feats["company"] = company
    feats["kouzou"] = kouzou_str
    # 土地カテゴリカル
    feats["road_direction"] = road_direction_str
    feats["road_type"] = road_type_str
    feats["road_structure"] = road_structure_str
    feats["chimoku"] = chimoku_str
    
    return feats
