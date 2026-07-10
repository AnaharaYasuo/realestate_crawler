# -*- coding: utf-8 -*-
import os
import sys
import csv
import logging
import argparse

# Django環境のロード
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import realestateSettings
realestateSettings.configure()

from package.models.evaluation import StationPotential

def generate_sample_mlit_csv(filepath):
    """
    テスト用の国土数値情報風の駅乗降客数サンプルCSVを生成する。
    """
    logging.info(f"Generating sample MLIT station passenger volume CSV at: {filepath}")
    
    # 国土数値情報（駅別乗降人員）に近いフォーマット
    # 路線名, 駅名, 代表値（1日平均乗降人員数）
    sample_data = [
        ["JR東海道本線", "横浜", "420000"],
        ["東急東横線", "横浜", "360000"],
        ["相鉄本線", "横浜", "230000"],
        ["京急本線", "横浜", "190000"],
        ["みなとみらい線", "みなとみらい", "25000"],
        ["みなとみらい線", "元町・中華街", "30000"],
        ["京急本線", "上大岡", "140000"],
        ["東急東横線", "武蔵小杉", "180000"],
        ["JR南武線", "武蔵小杉", "130000"],
        ["東急田園都市線", "たまプラーザ", "80000"],
        ["東急東横線", "日吉", "150000"],
        ["東急大井町線", "自由が丘", "55000"],
        ["東急東横線", "自由が丘", "95000"],
        ["小田急小田原線", "町田", "290000"],
        ["JR横浜線", "町田", "110000"],
    ]
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["line_name", "station_name", "passenger_volume"]) # ヘッダー
        writer.writerows(sample_data)


def import_mlit_stations(csv_path):
    """
    国土数値情報CSVを読み込み、駅ポテンシャルテーブルに同期する。
    """
    if not os.path.exists(csv_path):
        logging.error(f"CSV file not found: {csv_path}")
        return False
        
    logging.info(f"Importing station data from MLIT CSV: {csv_path}...")
    
    processed = 0
    created_count = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # カラム名マッピング (国土数値情報のカラム名に合わせる、またはマッピング対応)
            # 本デモでは "line_name", "station_name", "passenger_volume" を想定
            line = row.get("line_name", "").strip()
            station = row.get("station_name", "").strip()
            vol_str = row.get("passenger_volume", "0").strip()
            
            if not line or not station:
                continue
                
            try:
                volume = int(vol_str)
            except ValueError:
                volume = 0
                
            # 駅名から「駅」という文字を除外して正規化 (クローラーとの結合を確実にするため)
            station_clean = station.replace("駅", "")
            
            obj, created = StationPotential.objects.update_or_create(
                station_name=station_clean,
                railway_line=line,
                defaults={
                    "passenger_volume": volume
                }
            )
            processed += 1
            if created:
                created_count += 1
                
    print(f"MLIT Station Import: Processed {processed} records (Created {created_count} new).")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    parser = argparse.ArgumentParser(description="Import station passenger volume from MLIT CSV.")
    parser.add_argument("--csv", help="Path to the MLIT station passenger volume CSV file.")
    args = parser.parse_args()
    
    csv_file = args.csv
    is_temp = False
    
    if not csv_file:
        # 引数なしの場合はTempディレクトリにサンプルCSVを作ってそれを読み込む
        csv_file = "/app/src/crawler/scripts/temp_mlit_stations_sample.csv"
        generate_sample_mlit_csv(csv_file)
        is_temp = True
        
    try:
        import_mlit_stations(csv_file)
    finally:
        # 一時生成したサンプルファイルを削除
        if is_temp and os.path.exists(csv_file):
            try:
                os.remove(csv_file)
                logging.info(f"Cleaned up temporary sample CSV: {csv_file}")
            except Exception as e:
                logging.warning(f"Failed to delete temp file {csv_file}: {e}")
