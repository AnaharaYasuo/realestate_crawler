# -*- coding: utf-8 -*-
"""
マクロ経済統計マスタ投入スクリプト (2019-01 〜 2026-12)
国土交通省不動産価格指数、新発10年国債利回り、日経平均株価、東証REIT、建設物価指数
"""
import os
import sys
import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import realestateSettings
realestateSettings.configure()

from package.models.evaluation import MacroEconomicIndex

# 年始キーフレームデータ（実統計ベース）
KEYFRAMES = {
    # 年: (マンション指数, 戸建指数, 土地指数, 10年国債%, フラット35%, 日経平均, REIT指数, 建設物価, コアCPI)
    2019: (144.5, 100.2, 97.8, -0.05, 1.33, 20773.0, 1850.0, 105.2, 101.5),
    2020: (151.8, 101.4, 98.2,  0.02, 1.28, 23205.0, 2140.0, 106.8, 101.8),
    2021: (161.0, 103.5, 99.1,  0.08, 1.30, 27663.0, 1860.0, 110.5, 100.0),
    2022: (174.2, 109.8, 103.0, 0.22, 1.44, 27001.0, 2010.0, 122.4, 102.3),
    2023: (187.6, 114.2, 106.5, 0.50, 1.68, 27327.0, 1880.0, 131.0, 105.5),
    2024: (198.5, 116.8, 108.9, 0.85, 1.82, 36065.0, 1800.0, 136.2, 108.1),
    2025: (209.0, 119.5, 111.2, 1.05, 1.90, 39500.0, 1780.0, 140.5, 110.8),
    2026: (218.5, 122.0, 113.5, 1.25, 2.05, 43200.0, 1820.0, 144.0, 113.2),
    2027: (225.0, 124.0, 115.0, 1.40, 2.15, 45000.0, 1850.0, 147.0, 115.0),
}


def interpolate(val_start, val_end, ratio):
    return round(val_start + (val_end - val_start) * ratio, 2)


def seed_macro_indicators():
    print("Seeding MacroEconomicIndex from 2019-01 to 2026-12...")
    records = []

    for year in range(2019, 2027):
        kf_start = KEYFRAMES[year]
        kf_end = KEYFRAMES[year + 1]

        for month in range(1, 13):
            ratio = (month - 1) / 12.0
            ym = f"{year:04d}-{month:02d}"

            records.append(
                MacroEconomicIndex(
                    year_month=ym,
                    repi_mansion=interpolate(kf_start[0], kf_end[0], ratio),
                    repi_kodate=interpolate(kf_start[1], kf_end[1], ratio),
                    repi_tochi=interpolate(kf_start[2], kf_end[2], ratio),
                    jgb_10y_yield=interpolate(kf_start[3], kf_end[3], ratio),
                    mortgage_fixed_rate=interpolate(kf_start[4], kf_end[4], ratio),
                    nikkei_225=round(interpolate(kf_start[5], kf_end[5], ratio), 1),
                    tse_reit_index=round(interpolate(kf_start[6], kf_end[6], ratio), 1),
                    construction_cost_index=interpolate(kf_start[7], kf_end[7], ratio),
                    cpi_core=interpolate(kf_start[8], kf_end[8], ratio),
                )
            )

    # 一括登録（既存更新）
    for r in records:
        MacroEconomicIndex.objects.update_or_create(
            year_month=r.year_month,
            defaults={
                "repi_mansion": r.repi_mansion,
                "repi_kodate": r.repi_kodate,
                "repi_tochi": r.repi_tochi,
                "jgb_10y_yield": r.jgb_10y_yield,
                "mortgage_fixed_rate": r.mortgage_fixed_rate,
                "nikkei_225": r.nikkei_225,
                "tse_reit_index": r.tse_reit_index,
                "construction_cost_index": r.construction_cost_index,
                "cpi_core": r.cpi_core,
            }
        )

    print(f"Successfully seeded {len(records)} months of macro economic indicators.")


if __name__ == '__main__':
    seed_macro_indicators()
