# -*- coding: utf-8 -*-
import os
import sys
from decimal import Decimal

# 作業ディレクトリをPythonパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import realestateSettings
realestateSettings.configure()

from package.models.evaluation import MunicipalPotential, StationPotential

def import_municipal_data():
    print("Importing municipal potential data...")
    
    # 東京都23区 + 主要都市の人口増減率(%)と平均所得(千円)
    municipalities = [
        # 東京都23区
        {"prefecture": "東京都", "city": "千代田区", "population_growth_rate": Decimal("1.50"), "average_income": 12000},
        {"prefecture": "東京都", "city": "港区", "population_growth_rate": Decimal("1.80"), "average_income": 11000},
        {"prefecture": "東京都", "city": "渋谷区", "population_growth_rate": Decimal("1.20"), "average_income": 8500},
        {"prefecture": "東京都", "city": "中央区", "population_growth_rate": Decimal("2.00"), "average_income": 7500},
        {"prefecture": "東京都", "city": "文京区", "population_growth_rate": Decimal("0.80"), "average_income": 6800},
        {"prefecture": "東京都", "city": "目黒区", "population_growth_rate": Decimal("0.60"), "average_income": 6400},
        {"prefecture": "東京都", "city": "世田谷区", "population_growth_rate": Decimal("0.40"), "average_income": 5600},
        {"prefecture": "東京都", "city": "新宿区", "population_growth_rate": Decimal("0.50"), "average_income": 5500},
        {"prefecture": "東京都", "city": "品川区", "population_growth_rate": Decimal("0.70"), "average_income": 5200},
        {"prefecture": "東京都", "city": "杉並区", "population_growth_rate": Decimal("0.30"), "average_income": 4800},
        {"prefecture": "東京都", "city": "江東区", "population_growth_rate": Decimal("1.10"), "average_income": 4500},
        {"prefecture": "東京都", "city": "豊島区", "population_growth_rate": Decimal("0.50"), "average_income": 4400},
        {"prefecture": "東京都", "city": "大田区", "population_growth_rate": Decimal("0.20"), "average_income": 4400},
        {"prefecture": "東京都", "city": "中野区", "population_growth_rate": Decimal("0.10"), "average_income": 4200},
        {"prefecture": "東京都", "city": "台東区", "population_growth_rate": Decimal("0.80"), "average_income": 4100},
        {"prefecture": "東京都", "city": "練馬区", "population_growth_rate": Decimal("0.20"), "average_income": 3900},
        {"prefecture": "東京都", "city": "墨田区", "population_growth_rate": Decimal("0.60"), "average_income": 3800},
        {"prefecture": "東京都", "city": "板橋区", "population_growth_rate": Decimal("-0.10"), "average_income": 3600},
        {"prefecture": "東京都", "city": "北区", "population_growth_rate": Decimal("-0.20"), "average_income": 3600},
        {"prefecture": "東京都", "city": "荒川区", "population_growth_rate": Decimal("0.30"), "average_income": 3500},
        {"prefecture": "東京都", "city": "江戸川区", "population_growth_rate": Decimal("-0.20"), "average_income": 3400},
        {"prefecture": "東京都", "city": "葛飾区", "population_growth_rate": Decimal("-0.40"), "average_income": 3300},
        {"prefecture": "東京都", "city": "足立区", "population_growth_rate": Decimal("-0.50"), "average_income": 3200},
        # 愛知県 (住友不動産テスト用)
        {"prefecture": "愛知県", "city": "名古屋市千種区", "population_growth_rate": Decimal("0.25"), "average_income": 4300},
        {"prefecture": "愛知県", "city": "名古屋市東区", "population_growth_rate": Decimal("0.40"), "average_income": 4500},
        {"prefecture": "愛知県", "city": "名古屋市中区", "population_growth_rate": Decimal("0.60"), "average_income": 4100},
        {"prefecture": "愛知県", "city": "名古屋市昭和区", "population_growth_rate": Decimal("0.10"), "average_income": 4600},
        {"prefecture": "愛知県", "city": "名古屋市瑞穂区", "population_growth_rate": Decimal("0.05"), "average_income": 4400},
        {"prefecture": "愛知県", "city": "名古屋市西区", "population_growth_rate": Decimal("0.15"), "average_income": 3500},
        {"prefecture": "愛知県", "city": "名古屋市北区", "population_growth_rate": Decimal("-0.10"), "average_income": 3200},
        {"prefecture": "愛知県", "city": "名古屋市中村区", "population_growth_rate": Decimal("0.20"), "average_income": 3400},
    ]

    count = 0
    for m in municipalities:
        obj, created = MunicipalPotential.objects.update_or_create(
            prefecture=m["prefecture"],
            city=m["city"],
            defaults={
                "population_growth_rate": m["population_growth_rate"],
                "average_income": m["average_income"]
            }
        )
        if created:
            count += 1

    print(f"Successfully processed {len(municipalities)} municipalities (created {count} new).")


def import_station_data():
    print("Importing station passenger volume data...")
    
    # 主要駅の1日平均乗降客数 (路線名はクローラーに合わせる)
    stations = [
        # 都心・JR・主要私鉄
        {"station_name": "新宿", "railway_line": "JR山手線", "passenger_volume": 750000},
        {"station_name": "新宿", "railway_line": "東京メトロ丸ノ内線", "passenger_volume": 240000},
        {"station_name": "渋谷", "railway_line": "JR山手線", "passenger_volume": 650000},
        {"station_name": "池袋", "railway_line": "JR山手線", "passenger_volume": 550000},
        {"station_name": "東京", "railway_line": "JR山手線", "passenger_volume": 450000},
        {"station_name": "品川", "railway_line": "JR山手線", "passenger_volume": 380000},
        {"station_name": "秋葉原", "railway_line": "JR山手線", "passenger_volume": 240000},
        {"station_name": "有楽町", "railway_line": "JR山手線", "passenger_volume": 170000},
        {"station_name": "御茶ノ水", "railway_line": "JR中央線", "passenger_volume": 100000},
        {"station_name": "御茶ノ水", "railway_line": "中央・総武緩行線", "passenger_volume": 100000},
        
        # 地下鉄（千代田線・半蔵門線・有楽町線・大江戸線等）
        {"station_name": "新御茶ノ水", "railway_line": "東京メトロ千代田線", "passenger_volume": 80000},
        {"station_name": "新御茶ノ水", "railway_line": "千代田線", "passenger_volume": 80000},
        {"station_name": "神保町", "railway_line": "都営三田線", "passenger_volume": 90000},
        {"station_name": "神保町", "railway_line": "都営新宿線", "passenger_volume": 85000},
        {"station_name": "神保町", "railway_line": "東京メトロ半蔵門線", "passenger_volume": 90000},
        {"station_name": "半蔵門", "railway_line": "東京メトロ半蔵門線", "passenger_volume": 60000},
        {"station_name": "半蔵門", "railway_line": "半蔵門線", "passenger_volume": 60000},
        {"station_name": "麹町", "railway_line": "東京メトロ有楽町線", "passenger_volume": 50000},
        {"station_name": "麹町", "railway_line": "有楽町線", "passenger_volume": 50000},
        {"station_name": "市ケ谷", "railway_line": "JR中央線", "passenger_volume": 120000},
        {"station_name": "市ケ谷", "railway_line": "東京メトロ有楽町線", "passenger_volume": 80000},
        {"station_name": "市ケ谷", "railway_line": "東京メトロ南北線", "passenger_volume": 50000},
        {"station_name": "飯田橋", "railway_line": "JR中央線", "passenger_volume": 150000},
        {"station_name": "飯田橋", "railway_line": "東京メトロ東西線", "passenger_volume": 170000},
        {"station_name": "飯田橋", "railway_line": "都営大江戸線", "passenger_volume": 80000},
        {"station_name": "飯田橋", "railway_line": "東京メトロ南北線", "passenger_volume": 60000},
        {"station_name": "小川町", "railway_line": "都営新宿線", "passenger_volume": 40000},
        {"station_name": "淡路町", "railway_line": "東京メトロ丸ノ内線", "passenger_volume": 45000},
        {"station_name": "永田町", "railway_line": "東京メトロ有楽町線", "passenger_volume": 70000},
        {"station_name": "赤坂見附", "railway_line": "東京メトロ銀座線", "passenger_volume": 80000},
        {"station_name": "広尾", "railway_line": "東京メトロ日比谷線", "passenger_volume": 60000},
        {"station_name": "麻布十番", "railway_line": "東京メトロ南北線", "passenger_volume": 55000},
        
        # 名古屋（住友不動産テスト用）
        {"station_name": "覚王山", "railway_line": "名古屋市営東山線", "passenger_volume": 15000},
        {"station_name": "新栄町", "railway_line": "名古屋市営東山線", "passenger_volume": 12000},
        {"station_name": "高畑", "railway_line": "名古屋市営東山線", "passenger_volume": 10000},
        {"station_name": "高岳", "railway_line": "名古屋市営桜通線", "passenger_volume": 8000},
        {"station_name": "池下", "railway_line": "名古屋市営東山線", "passenger_volume": 11000},
    ]

    count = 0
    for s in stations:
        obj, created = StationPotential.objects.update_or_create(
            station_name=s["station_name"],
            railway_line=s["railway_line"],
            defaults={
                "passenger_volume": s["passenger_volume"]
            }
        )
        if created:
            count += 1

    print(f"Successfully processed {len(stations)} stations (created {count} new).")


if __name__ == "__main__":
    import_municipal_data()
    import_station_data()
    print("Seed data import completed successfully!")
