# -*- coding: utf-8 -*-
import sys
import os
import django
import json
import logging
from datetime import datetime, timedelta

# Django初期化設定
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import realestateSettings
realestateSettings.configure()

from package.models.evaluation import PropertyEvaluation
from package.models.mitsui import MitsuiMansion, MitsuiKodate, MitsuiTochi, MitsuiInvestmentKodate, MitsuiInvestmentApartment
from package.models.sumifu import SumifuMansion, SumifuKodate, SumifuTochi, SumifuInvestmentKodate, SumifuInvestmentApartment
from package.models.tokyu import TokyuMansion, TokyuKodate, TokyuTochi, TokyuInvestmentKodate, TokyuInvestmentApartment
from package.models.nomura import NomuraMansion, NomuraKodate, NomuraTochi, NomuraInvestmentKodate, NomuraInvestmentApartment
from package.models.misawa import MisawaMansion, MisawaKodate, MisawaTochi, MisawaInvestmentKodate, MisawaInvestmentApartment
from package.models.athome import AthomeMansion, AthomeKodate, AthomeTochi, AthomeInvestmentApartment
from package.models.homes import HomesMansion, HomesKodate, HomesTochi, HomesInvestmentApartment
import django.utils.timezone as timezone

MODEL_MAP = {
    ("mitsui", "mansion"): MitsuiMansion, ("mitsui", "kodate"): MitsuiKodate, ("mitsui", "tochi"): MitsuiTochi,
    ("mitsui", "investment_kodate"): MitsuiInvestmentKodate, ("mitsui", "apartment"): MitsuiInvestmentApartment,
    ("sumifu", "mansion"): SumifuMansion, ("sumifu", "kodate"): SumifuKodate, ("sumifu", "tochi"): SumifuTochi,
    ("sumifu", "investment_kodate"): SumifuInvestmentKodate, ("sumifu", "apartment"): SumifuInvestmentApartment,
    ("tokyu", "mansion"): TokyuMansion, ("tokyu", "kodate"): TokyuKodate, ("tokyu", "tochi"): TokyuTochi,
    ("tokyu", "investment_kodate"): TokyuInvestmentKodate, ("tokyu", "apartment"): TokyuInvestmentApartment,
    ("nomura", "mansion"): NomuraMansion, ("nomura", "kodate"): NomuraKodate, ("nomura", "tochi"): NomuraTochi,
    ("nomura", "investment_kodate"): NomuraInvestmentKodate, ("nomura", "apartment"): NomuraInvestmentApartment,
    ("misawa", "mansion"): MisawaMansion, ("misawa", "kodate"): MisawaKodate, ("misawa", "tochi"): MisawaTochi,
    ("misawa", "investment_kodate"): MisawaInvestmentKodate, ("misawa", "apartment"): MisawaInvestmentApartment,
    ("athome", "mansion"): AthomeMansion, ("athome", "kodate"): AthomeKodate, ("athome", "tochi"): AthomeTochi,
    ("athome", "apartment"): AthomeInvestmentApartment,
    ("homes", "mansion"): HomesMansion, ("homes", "kodate"): HomesKodate, ("homes", "tochi"): HomesTochi,
    ("homes", "apartment"): HomesInvestmentApartment,
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def scan_anomalies_and_generate_instructions():
    """
    データ不整合（価格極小、面積極小、一棟面積不足、間口0m警告など）がある物件や、
    直近でエラーが検出された物件のURLをDBからスキャンし、
    AIエージェント向けの自己修復指示書 (auto_heal_instruction.json) を出力します。
    """
    logging.info("Scanning for scraping anomalies and errors to build AI self-healing instructions...")
    
    # AI自己修復の対象となる物件候補
    heal_targets = []
    
    # 1. DBからクレンジングされた異常物件（評価額が0にリセットされたもの）をスキャン
    # 直近3日間に登録・更新されたもので、価格・面積に問題があるか、間口0m警告がある物件
    three_days_ago = timezone.now() - timedelta(days=3)
    eval_anomalies = PropertyEvaluation.objects.filter(
        analyzed_at__gte=three_days_ago
    )
    
    for ev in eval_anomalies:
        model = MODEL_MAP.get((ev.company, ev.property_type))
        if not model:
            continue
        try:
            prop = model.objects.get(id=ev.property_id)
        except model.DoesNotExist:
            continue
            
        reason = ""
        # 異常判定の再現
        if prop.price and prop.price < 1000000: # 100万円未満
            reason = f"価格異常極小: {prop.priceStr} ({prop.price}円)"
        elif getattr(prop, 'tatemonoMenseki', 0) and prop.tatemonoMenseki < 5.0:
            reason = f"建物面積異常極小: {prop.tatemonoMenseki}㎡"
        elif getattr(prop, 'tochiMenseki', 0) and prop.tochiMenseki < 5.0:
            reason = f"土地面積異常極小: {prop.tochiMenseki}㎡"
        elif hasattr(prop, 'maguchi') and prop.maguchi == 0 and prop.setsudou:
            # 接道はあるのに間口が0m（パース漏れの疑い）
            reason = f"間口パース漏れ警告 (接道: '{prop.setsudou}')"
            
        if reason:
            target = {
                "url": prop.pageUrl,
                "company": ev.company,
                "property_type": ev.property_type,
                "propertyName": prop.propertyName,
                "price": float(prop.price) if prop.price else 0,
                "reason": reason,
                "detected_at": ev.analyzed_at.strftime('%Y-%m-%d %H:%M:%S') if ev.analyzed_at else None
            }
            if target not in heal_targets:
                heal_targets.append(target)
                
    # 2. 直近のHTMLエラーファイル（monitor_error_pagesで検出されるようなパースエラーファイル）からも補完可能
    # 今回はDBから検知したものを主とする
    
    if not heal_targets:
        logging.info("No scraping anomalies found for AI healing.")
        # 指示書ファイルがあれば削除する
        inst_path = "/app/Temp/auto_heal_instruction.json"
        if os.path.exists(inst_path):
            os.remove(inst_path)
            logging.info("Removed stale auto_heal_instruction.json")
        return
        
    # 重複排除と指示書の出力
    instruction = {
        "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "targets": heal_targets,
        "action_required": "Please inspect the target URLs, analyze why their data parsed incorrectly (e.g. price/area too small or frontage 0m despite setsudou exists), fix the corresponding parser inside package/parser/, run verification tests, and commit/push/merge changes to master."
    }
    
    os.makedirs("/app/Temp", exist_ok=True)
    inst_path = "/app/Temp/auto_heal_instruction.json"
    with open(inst_path, "w", encoding="utf-8") as f:
        json.dump(instruction, f, ensure_ascii=False, indent=2)
        
    logging.info(f"Successfully generated AI self-healing instruction at {inst_path} with {len(heal_targets)} targets.")

if __name__ == "__main__":
    scan_anomalies_and_generate_instructions()
