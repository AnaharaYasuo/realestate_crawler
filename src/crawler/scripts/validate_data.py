# -*- coding: utf-8 -*-
import os
import sys
import logging
import datetime
import json
from asgiref.sync import async_to_sync

# Django設定のロード
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import realestateSettings
realestateSettings.configure()

from django.db import transaction
from package.models.evaluation import PropertyEvaluation
from package.utils.slack import send_slack_message

# 各社モデルのインポート
from package.models.mitsui import MitsuiMansion, MitsuiKodate, MitsuiTochi, MitsuiInvestmentKodate, MitsuiInvestmentApartment
from package.models.sumifu import SumifuMansion, SumifuKodate, SumifuTochi, SumifuInvestmentKodate, SumifuInvestmentApartment
from package.models.tokyu import TokyuMansion, TokyuKodate, TokyuTochi, TokyuInvestmentKodate, TokyuInvestmentApartment
from package.models.nomura import NomuraMansion, NomuraKodate, NomuraTochi, NomuraInvestmentKodate, NomuraInvestmentApartment
from package.models.misawa import MisawaMansion, MisawaKodate, MisawaTochi, MisawaInvestmentKodate, MisawaInvestmentApartment
from package.models.athome import AthomeMansion, AthomeKodate, AthomeTochi, AthomeInvestmentApartment
from package.models.homes import HomesMansion, HomesKodate, HomesTochi, HomesInvestmentApartment

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

def get_all_models_flat():
    """全物件種別のモデルクラスとその判定タグのリストを返す"""
    return [
        (MitsuiMansion, "mitsui", "mansion"), (MitsuiKodate, "mitsui", "kodate"), (MitsuiTochi, "mitsui", "tochi"),
        (MitsuiInvestmentKodate, "mitsui", "invest_kodate"), (MitsuiInvestmentApartment, "mitsui", "apartment"),
        
        (SumifuMansion, "sumifu", "mansion"), (SumifuKodate, "sumifu", "kodate"), (SumifuTochi, "sumifu", "tochi"),
        (SumifuInvestmentKodate, "sumifu", "invest_kodate"), (SumifuInvestmentApartment, "sumifu", "apartment"),
        
        (TokyuMansion, "tokyu", "mansion"), (TokyuKodate, "tokyu", "kodate"), (TokyuTochi, "tokyu", "tochi"),
        (TokyuInvestmentKodate, "tokyu", "invest_kodate"), (TokyuInvestmentApartment, "tokyu", "apartment"),
        
        (NomuraMansion, "nomura", "mansion"), (NomuraKodate, "nomura", "kodate"), (NomuraTochi, "nomura", "tochi"),
        (NomuraInvestmentKodate, "nomura", "invest_kodate"), (NomuraInvestmentApartment, "nomura", "apartment"),
        
        (MisawaMansion, "misawa", "mansion"), (MisawaKodate, "misawa", "kodate"), (MisawaTochi, "misawa", "tochi"),
        (MisawaInvestmentKodate, "misawa", "invest_kodate"), (MisawaInvestmentApartment, "misawa", "apartment"),
        
        (AthomeMansion, "athome", "mansion"), (AthomeKodate, "athome", "kodate"), (AthomeTochi, "athome", "tochi"),
        (AthomeInvestmentApartment, "athome", "apartment"),
        
        (HomesMansion, "homes", "mansion"), (HomesKodate, "homes", "kodate"), (HomesTochi, "homes", "tochi"),
        (HomesInvestmentApartment, "homes", "apartment"),
    ]

def validate_data():
    logging.info("Starting automated scraping validation and data integrity checks...")
    
    anomalies = []
    cleaned_count = 0
    
    models = get_all_models_flat()
    
    for model_cls, company, ptype in models:
        qs = model_cls.objects.all()
        for item in qs:
            url = getattr(item, "pageUrl", "")
            if not url:
                continue
                
            price = getattr(item, "price", 0) or 0
            price_man = float(price) / 10000.0
            
            # 面積の動的抽出
            area = 0.0
            if hasattr(item, "senyuMenseki") and item.senyuMenseki is not None:
                area = float(item.senyuMenseki)
            elif hasattr(item, "tatemonoMenseki") and item.tatemonoMenseki is not None:
                area = float(item.tatemonoMenseki)
            elif hasattr(item, "tochiMenseki") and item.tochiMenseki is not None:
                area = float(item.tochiMenseki)
                
            # 間口の抽出
            maguchi = float(getattr(item, "maguchi", 1.0) or 1.0) # デフォルトで1.0（エラー対象にしない）
            if ptype in ["tochi", "kodate", "invest_kodate"]:
                maguchi = float(getattr(item, "maguchi", 0.0) or 0.0)
            
            # 不正データ判定
            has_error = False
            reasons = []
            
            # 1. 価格の異常値（100万円未満）
            if price_man <= 0 or price_man < 100.0:
                has_error = True
                reasons.append(f"価格異常 ({price_man:.1f}万円)")
                
            # 2. 面積の異常値（5㎡未満）
            if area <= 5.0:
                has_error = True
                reasons.append(f"面積異常 ({area:.1f}㎡)")
                
            # 3. 一棟物件であるのに面積が極端に狭い（1室用パーサーへの誤マッピング疑い）
            if ptype == "apartment" and area < 15.0:
                has_error = True
                reasons.append(f"一棟面積過小疑い ({area:.1f}㎡)")
                
            # 4. 土地/戸建において間口が0m（接道パース失敗による75%減価疑い）
            if ptype in ["tochi", "kodate", "invest_kodate"] and maguchi <= 0.0:
                # 警告として記録するが、強制排除はせず警告にとどめる
                reasons.append(f"間口0m警告 (無道路地ペナルティ対象)")
                # 強制排除フラグは立てない (has_error = False)
            
            if reasons and (has_error or "間口0m警告" in reasons[0]):
                p_name = getattr(item, "propertyName", "不明な物件名")
                anomalies.append({
                    "url": url,
                    "company": company,
                    "property_type": ptype,
                    "name": p_name,
                    "reasons": reasons,
                    "is_critical": has_error
                })
                
                # クレンジング処理 (予測結果の無効化ガード)
                if has_error:
                    eval_rec = PropertyEvaluation.objects.filter(property_url=url).first()
                    if eval_rec:
                        with transaction.atomic():
                            # 予測価格を0にリセットし、Slackアラート対象から永久に排除
                            eval_rec.first_stage_predicted_price = 0
                            eval_rec.second_stage_predicted_price = 0
                            eval_rec.is_slack_notified = True # スキップ扱いにする
                            eval_rec.save()
                        cleaned_count += 1
                        
    logging.info(f"Scan finished. Found {len(anomalies)} anomalies. Auto-cleaned: {cleaned_count} evaluations.")
    
    # 2. HTMLパースエラー（monitor_error_pages.py）のレポート読み込み
    html_errors_count = 0
    html_errors_list = []
    
    try:
        import subprocess
        logging.info("Running monitor_error_pages.py as a subprocess...")
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitor_error_pages.py")
        subprocess.run([sys.executable, script_path], check=True)
        
        # 本日の日付のJSONファイルを読み込む
        today_str = datetime.date.today().strftime("%Y%m%d")
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        report_path = os.path.join(project_root, "logs", f"error_report_{today_str}.json")
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                rep = json.load(f)
                html_errors_count = rep.get("recent_errors_24h", 0)
                html_errors_list = rep.get("recent_details", [])
    except Exception as e:
        logging.error(f"Failed to integrate monitor_error_pages: {e}")
        
    # チャンネルごとのメッセージバッファ
    buffers = {
        "mansion": [],
        "kodate": [],
        "tochi": [],
        "apartment": [],
        "invest_kodate": [],
        "general": []
    }
    
    # 1. HTMLパースエラーの振り分け
    for err in html_errors_list:
        comp_type = err.get("company_type", "")
        ptype = "general"
        if "mansion" in comp_type:
            ptype = "mansion"
        elif "kodate" in comp_type:
            if "investment" in comp_type or "invest" in comp_type:
                ptype = "invest_kodate"
            else:
                ptype = "kodate"
        elif "tochi" in comp_type:
            ptype = "tochi"
        elif "apartment" in comp_type:
            ptype = "apartment"
            
        buffers[ptype].append(f"  - 🚨 [HTML Error] [{err['company_type']}] Reason: {err['reason']} | URL: {err['url']}")
        
    # 2. データアノマリーの振り分け
    for a in anomalies:
        ptype = a["property_type"]
        if ptype in ["invest_apartment", "apartment"]:
            key = "apartment"
        elif ptype == "invest_kodate":
            key = "invest_kodate"
        elif ptype in ["mansion", "kodate", "tochi"]:
            key = ptype
        else:
            key = "general"
            
        severity = "❌ [Critical]" if a["is_critical"] else "💡 [Warning]"
        reasons_list = a["reasons"]
        reasons_str = ", ".join(reasons_list) if isinstance(reasons_list, list) else str(reasons_list)
        buffers[key].append(f"  - {severity} [{a['company']}/{ptype}] {reasons_str} | {a['name']} | URL: {a['url']}")
        
    # 各バッファを対応するアラートチャンネルに送信
    sent_any = False
    for key, items in buffers.items():
        if not items:
            continue
            
        msg = f"⚠️ 【不動産クローラー データ監視アラート - {key.upper()}】\n\n"
        msg += f"🚨 **検出された異常/エラー: {len(items)} 件**\n"
        for item_str in items[:10]: # 最大10件を表示
            msg += item_str + "\n"
        if len(items) > 10:
            msg += f"  - (他 {len(items) - 10} 件のエラーがあります。)\n"
            
        msg += "\n※ 異常データは自動クレンジングまたはスキップ処理が適用されました。"
        
        # 投稿先アラートチャンネルの決定
        alert_channel = os.getenv("SLACK_ALERT_CHANNEL_ID", "property_alart")
        if key == "mansion":
            alert_channel = os.getenv("SLACK_ALERT_MANSION", "C0BJWUCTRNU") # alerts-mansion
        elif key == "kodate":
            alert_channel = os.getenv("SLACK_ALERT_KODATE", "C0BHZA5ASDT") # alerts-kodate
        elif key == "tochi":
            alert_channel = os.getenv("SLACK_ALERT_TOCHI", "C0BJ2JVGCLS") # alerts-tochi
        elif key == "apartment":
            alert_channel = os.getenv("SLACK_ALERT_INVEST_APARTMENT", "C0BJ6B4R3E0") # alerts-invest-apartment
        elif key == "invest_kodate":
            alert_channel = os.getenv("SLACK_ALERT_INVEST_KODATE", "C0BJ0KSJEDC") # alerts-invest-kodate
            
        logging.info(f"Sending {key} alert report to channel: {alert_channel}")
        async_to_sync(send_slack_message)(msg, channel=alert_channel)
        sent_any = True
        
    if not sent_any:
        logging.info("No scraping anomalies or HTML errors detected. Data integrity is clean.")

if __name__ == "__main__":
    # monitor_error_pagesのインポートパス解決のため、カレントディレクトリをscriptsに合わせる
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if scripts_dir not in sys.path:
        sys.path.append(scripts_dir)
    validate_data()
