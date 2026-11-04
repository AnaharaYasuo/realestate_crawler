"""
多面プロ鑑定 評価コンテキスト収集・構築エンジン (Issue #1197)

物件情報、周辺環境・自治体ポテンシャル、駅乗降客数、国交省ハザード情報、
およびマンションレビュー（mansion-review.jp）の過去取引事例データを統合収集・整理し、
プロ鑑定プロンプトに注入するための客観評価コンテキストを生成する。
"""

import logging
from typing import Any

from package.ml.features.parsers import extract_clean_address
from package.ml.features.reference_data import (
    _init_global_caches,
    blend_land_prices,
    query_hazard_features,
    query_municipal_potential,
    query_station_volume,
)
from package.ml.mansion_review import fetch_mansion_review_data

logger = logging.getLogger(__name__)


def build_appraisal_context(prop, ptype_jp: str) -> dict[str, Any]:
    """
    対象物件および周辺・外部の基礎客観データを収集・統合する。
    """
    _init_global_caches()
    pref, city, station_raw, _ = extract_clean_address(prop)

    # 1. 自治体・マクロポテンシャル（人口推移、所得、人口密度）
    pop_growth, income, total_pop, income_growth, pop_density = query_municipal_potential(pref, city)

    # 2. 駅ポテンシャル（乗降客数）
    station_clean = station_raw or getattr(prop, "station1", "") or getattr(prop, "station", "") or ""
    passenger_vol = query_station_volume(station_clean) if station_clean else None

    # 3. 国交省ハザード情報（浸水リスクレベル、土砂災害リスクレベル）
    flood_level, landslide_level = query_hazard_features(pref, city)

    # 4. 周辺基準地価・路線価・固定資産税評価目安
    max_youseki = float(getattr(prop, "floor_area_ratio", None) or getattr(prop, "youseki", 200.0) or 200.0)
    avg_lp, est_rosenka, _, lp_growth = blend_land_prices(pref, city, max_youseki)

    # 5. マンションレビュー過去取引事例（マンション種別限定）
    mansion_review_data = None
    is_mansion = "マンション" in ptype_jp or "区分" in ptype_jp
    if is_mansion:
        m_name = getattr(prop, "propertyName", "") or getattr(prop, "mansionName", "") or ""
        if m_name:
            mansion_review_data = fetch_mansion_review_data(m_name, timeout=5)

    return {
        "prefecture": pref,
        "city": city,
        "station": station_clean,
        "passenger_volume": passenger_vol,
        "population_growth_rate": pop_growth,
        "average_income": income,
        "total_population": total_pop,
        "income_growth_rate": income_growth,
        "population_density": pop_density,
        "flood_risk_level": flood_level,
        "landslide_risk_level": landslide_level,
        "average_land_price_sqm": avg_lp,
        "estimated_rosenka_price_sqm": est_rosenka,
        "land_price_growth_rate": lp_growth,
        "mansion_review": mansion_review_data,
    }


def _format_mansion_review_text(mr: dict[str, Any]) -> str:
    """マンションレビュー情報のフォーマット補助関数"""
    mr_lines = []
    if mr.get("estimated_tsubo_price_man"):
        mr_lines.append(f"推定相場坪単価: {mr['estimated_tsubo_price_man']}万円/坪")
    if mr.get("estimated_market_price_man"):
        mr_lines.append(f"推定適正価格: {mr['estimated_market_price_man']:,}万円")
    hist = mr.get("history_samples", [])
    hist_str = f" / 過去販売事例: {'; '.join(hist[:2])}" if hist else ""
    mr_summary = "、".join(mr_lines) if mr_lines else "登録あり"
    return f"・マンションレビュー過去取引事例データ ({mr.get('mansion_name', '')}): {mr_summary}{hist_str}"


def format_appraisal_context_text(ctx: dict[str, Any]) -> str:
    """
    収集した基礎情報をプロンプト注入用のテキストセクションに整形する。
    """
    raw_income = ctx.get("average_income", 0) or 0
    # average_income は千円単位で保存されているため、10で割って万円単位に換算する
    income_man = int(raw_income / 10) if raw_income > 0 else 0

    # 乗降客数の表示（未公表・非公表時は架空1万人にフォールバックせず明示）
    vol_val = ctx.get("passenger_volume")
    vol_text = f"推計日次乗降客数 {vol_val:,}人" if vol_val is not None and vol_val > 0 else "乗降客数 未公表/統計非対象"

    # 自治体所得の表示（未公表時は架空300万にフォールバックせず明示）
    pop_gr = ctx.get("population_growth_rate")
    pop_gr_str = f"人口増減率 {pop_gr:.2f}%" if pop_gr is not None else "人口増減率 未公表"
    income_str = f"平均所得 {income_man}万円" if income_man > 0 else "平均所得 未公表"

    lines = [
        "【公的・客観的基礎データ】",
        f"・自治体マクロ指標 ({ctx.get('prefecture', '')} {ctx.get('city', '')}): "
        f"{pop_gr_str} / {income_str} / "
        f"人口密度 {ctx.get('population_density', 0.0):.0f}人/km2",
        f"・駅ポテンシャル ({ctx.get('station', '-') or '最寄り駅'}): {vol_text}",
        f"・周辺公的基準地価指標: 平均地価 {ctx.get('average_land_price_sqm', 0):,}円/m2 "
        f"(想定路線価 {ctx.get('estimated_rosenka_price_sqm', 0):,}円/m2、地価動向 {ctx.get('land_price_growth_rate', 0.0):+.2f}%)"
    ]

    fl_lvl = ctx.get("flood_risk_level", 0)
    ls_lvl = ctx.get("landslide_risk_level", 0)
    flood_desc = "低（区域外または軽微）" if fl_lvl <= 1 else f"警戒レベル{fl_lvl}（浸水想定・内水リスクあり）"
    ls_desc = "低（区域外）" if ls_lvl <= 1 else f"警戒レベル{ls_lvl}（急傾斜地・土砂災害警戒区域あり）"
    lines.append(f"・国交省ハザードリスク指標: 浸水リスク={flood_desc} / 土砂災害リスク={ls_desc}")

    mr = ctx.get("mansion_review")
    if mr:
        lines.append(_format_mansion_review_text(mr))

    return "\n".join(lines)
