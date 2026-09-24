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
    
    line_tokyu_toyoko = "東急東横線"
    sample_data = [
        ["JR東海道本線", "横浜", "420000"],
        [line_tokyu_toyoko, "横浜", "360000"],
        ["相鉄本線", "横浜", "230000"],
        ["京急本線", "横浜", "190000"],
        ["みなとみらい線", "みなとみらい", "25000"],
        ["みなとみらい線", "元町・中華街", "30000"],
        ["京急本線", "上大岡", "140000"],
        [line_tokyu_toyoko, "武蔵小杉", "180000"],
        ["JR南武線", "武蔵小杉", "130000"],
        ["東急田園都市線", "たまプラーザ", "80000"],
        [line_tokyu_toyoko, "日吉", "150000"],
        ["東急大井町線", "自由が丘", "55000"],
        [line_tokyu_toyoko, "自由が丘", "95000"],
        ["小田急小田原線", "町田", "290000"],
        ["JR横浜線", "町田", "110000"],
    ]
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["line_name", "station_name", "passenger_volume"]) # ヘッダー
        writer.writerows(sample_data)


def safe_path(path: str) -> str:
    """Return the canonical path when it is within the working or repository tree.

    Raises:
        ValueError: If the resolved path is outside both allowed trees.
    """
    resolved = os.path.realpath(path)
    base_dir = os.path.realpath(os.getcwd())
    if resolved != base_dir and not resolved.startswith(base_dir + os.sep):
        project_root = os.path.realpath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
        if resolved != project_root and not resolved.startswith(project_root + os.sep):
            raise ValueError(f"path {path!r} is outside the allowed directory")
    return resolved


def import_mlit_stations(csv_path):
    """Upsert station passenger volumes from an allowed MLIT CSV path.

    Returns:
        bool: ``False`` when the file is missing; otherwise ``True``.

    Raises:
        ValueError: If the resolved CSV path is outside the allowed trees.
    """
    clean_csv = safe_path(csv_path)
    if not os.path.exists(clean_csv):
        logging.error(f"CSV file not found: {clean_csv}")
        return False
        
    logging.info(f"Importing station data from MLIT CSV: {clean_csv}...")
    
    processed = 0
    created_count = 0
    
    with open(clean_csv, 'r', encoding='utf-8') as f:
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
            
            _, created = StationPotential.objects.update_or_create(
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
    
    csv_file = os.path.abspath(os.path.normpath(args.csv)) if args.csv else None
    temp_file = None
    
    if not csv_file:
        # 引数なしの場合はTempディレクトリにサンプルCSVを作ってそれを読み込む
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        temp_file = os.path.join(project_root, "src", "crawler", "scripts", "temp_mlit_stations_sample.csv")
        generate_sample_mlit_csv(temp_file)
        target_csv = temp_file
    else:
        target_csv = csv_file
        
    try:
        import_mlit_stations(target_csv)
    finally:
        # 一時生成したサンプルファイルを削除
        if temp_file:
            clean_temp = safe_path(temp_file)
            if os.path.exists(clean_temp):
                try:
                    os.remove(clean_temp)
                    logging.info(f"Cleaned up temporary sample CSV: {clean_temp}")
                except Exception as e:
                    logging.warning(f"Failed to delete temp file {clean_temp}: {e}")
