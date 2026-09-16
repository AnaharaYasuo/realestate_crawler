# -*- coding: utf-8 -*-
import os
import sys
import logging
import warnings
import requests
warnings.filterwarnings("ignore")

# Django設定の初期化
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import realestateSettings
realestateSettings.configure()

from django.db import transaction
from package.models.mitsui import MitsuiMansion, MitsuiKodate, MitsuiTochi, MitsuiInvestmentKodate, MitsuiInvestmentApartment
from package.models.sumifu import SumifuMansion, SumifuKodate, SumifuTochi, SumifuInvestmentKodate, SumifuInvestmentApartment
from package.models.tokyu import TokyuMansion, TokyuKodate, TokyuTochi, TokyuInvestmentKodate, TokyuInvestmentApartment
from package.models.nomura import NomuraMansion, NomuraKodate, NomuraTochi, NomuraInvestmentKodate, NomuraInvestmentApartment
from package.models.misawa import MisawaMansion, MisawaKodate, MisawaTochi, MisawaInvestmentKodate, MisawaInvestmentApartment
from package.models.athome import AthomeMansion, AthomeKodate, AthomeTochi, AthomeInvestmentApartment
from package.models.homes import HomesMansion, HomesKodate, HomesTochi, HomesInvestmentApartment
from package.models.evaluation import PropertyEvaluation

from package.ml.investment_evaluator import evaluate_investment_property

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

def get_api_base_url():
    """価格推定APIのベースURLを解決する"""
    url = os.getenv("EVALUATION_API_URL", "")
    if url:
        if not url.endswith("/"):
            url += "/"
        return url
        
    if os.getenv("IS_CLOUD", ""):
        return "https://us-central1-sumifu.cloudfunctions.net/api/evaluation/predict/"
    return "http://localhost:8000/api/evaluation/predict/"

def _serialize_property(item, ptype):
    """DjangoモデルオブジェクトからAPI送信用のシリアライズ辞書を作成"""
    data = {
        "price": getattr(item, "price", None),
        "address": getattr(item, "address", ""),
        "station1": getattr(item, "station1", ""),
        "railwayWalkMinute1": getattr(item, "railwayWalkMinute1", None),
        "kouzou": getattr(item, "kouzou", ""),
        "yousekiStr": getattr(item, "yousekiStr", "") or str(getattr(item, "youseki", "")) or "",
        "kenpeiStr": getattr(item, "kenpeiStr", "") or str(getattr(item, "kenpei", "")) or "",
        "tochikenri": getattr(item, "tochikenri", ""),
        "biko": getattr(item, "biko", "")
    }
    
    # 築年月のシリアライズ (Date -> Str)
    chikunengetsu = getattr(item, "chikunengetsu", None)
    if chikunengetsu:
        if hasattr(chikunengetsu, "strftime"):
            data["chikunengetsuStr"] = chikunengetsu.strftime("%Y-%m-%d")
        else:
            data["chikunengetsuStr"] = str(chikunengetsu)
    else:
        data["chikunengetsuStr"] = getattr(item, "chikunengetsuStr", "")
        
    # 物件種別ごとの固有フィールド
    if ptype == "mansion":
        data["senyuMenseki"] = float(item.senyuMenseki) if getattr(item, "senyuMenseki", None) is not None else None
        data["kanrihi"] = getattr(item, "kanrihi", None)
        data["syuzenTsumitate"] = getattr(item, "syuzenTsumitate", None)
    elif ptype == "kodate":
        data["tatemonoMenseki"] = float(item.tatemonoMenseki) if getattr(item, "tatemonoMenseki", None) is not None else None
        data["tochiMenseki"] = float(item.tochiMenseki) if getattr(item, "tochiMenseki", None) is not None else None
        data["maguchi"] = float(item.maguchi) if getattr(item, "maguchi", None) is not None else None
        data["roadWidth"] = float(item.roadWidth) if getattr(item, "roadWidth", None) is not None else None
        data["setsudou"] = getattr(item, "setsudou", "")
    elif ptype == "apartment":
        data["tatemonoMenseki"] = float(item.tatemonoMenseki) if getattr(item, "tatemonoMenseki", None) is not None else None
        data["tochiMenseki"] = float(item.tochiMenseki) if getattr(item, "tochiMenseki", None) is not None else None
        data["maguchi"] = float(item.maguchi) if getattr(item, "maguchi", None) is not None else None
        data["roadWidth"] = float(item.roadWidth) if getattr(item, "roadWidth", None) is not None else None
        data["setsudou"] = getattr(item, "setsudou", "")
        data["grossYield"] = float(item.grossYield) if getattr(item, "grossYield", None) is not None else None
        data["annualRent"] = getattr(item, "annualRent", None)
    elif ptype == "tochi":
        data["tochiMenseki"] = float(item.tochiMenseki) if getattr(item, "tochiMenseki", None) is not None else None
        data["maguchi"] = float(item.maguchi) if getattr(item, "maguchi", None) is not None else None
        data["roadWidth"] = float(item.roadWidth) if getattr(item, "roadWidth", None) is not None else None
        data["setsudou"] = getattr(item, "setsudou", "")
        
    return data

def get_all_property_queries():
    """全物件種別のクエリセット辞書を返す"""
    return {
        "mansion": [
            MitsuiMansion.objects.all(),
            SumifuMansion.objects.all(),
            TokyuMansion.objects.all(),
            NomuraMansion.objects.all(),
            MisawaMansion.objects.all(),
            AthomeMansion.objects.all(),
            HomesMansion.objects.all()
        ],
        "kodate": [
            MitsuiKodate.objects.all(),
            SumifuKodate.objects.all(),
            TokyuKodate.objects.all(),
            NomuraKodate.objects.all(),
            MisawaKodate.objects.all(),
            AthomeKodate.objects.all(),
            HomesKodate.objects.all(),
            MitsuiInvestmentKodate.objects.all(),
            SumifuInvestmentKodate.objects.all(),
            TokyuInvestmentKodate.objects.all(),
            NomuraInvestmentKodate.objects.all(),
            MisawaInvestmentKodate.objects.all()
        ],
        "apartment": [
            MitsuiInvestmentApartment.objects.all(),
            SumifuInvestmentApartment.objects.all(),
            TokyuInvestmentApartment.objects.all(),
            NomuraInvestmentApartment.objects.all(),
            MisawaInvestmentApartment.objects.all(),
            AthomeInvestmentApartment.objects.all(),
            HomesInvestmentApartment.objects.all()
        ],
        "tochi": [
            MitsuiTochi.objects.all(),
            SumifuTochi.objects.all(),
            TokyuTochi.objects.all(),
            NomuraTochi.objects.all(),
            MisawaTochi.objects.all(),
            AthomeTochi.objects.all(),
            HomesTochi.objects.all()
        ]
    }

def main():
    import asyncio
    from package.utils.slack import send_crawling_summary_alert

    def post_slack(msg):
        try:
            asyncio.run(send_crawling_summary_alert(msg))
        except Exception as se:
            logging.error(f"Failed to post Slack status: {se}")

    logging.info("Starting batch property estimation and investment evaluation via API...")
    post_slack("🚀 【価格推定開始】 データベースに登録されている全物件の一括価格推定と投資評価を開始します。(API版)")
    
    api_base_url = get_api_base_url()
    logging.info(f"Using API Base URL: {api_base_url}")
    
    queries = get_all_property_queries()
    
    total_processed = 0
    total_evaluated = 0
    errors = []
    
    for ptype, q_list in queries.items():
        logging.info(f"Processing property type: {ptype}...")
        for qs in q_list:
            model_class = qs.model
            model_name = model_class.__name__.lower()
            company_code = "unknown"
            for code in ["mitsui", "sumifu", "tokyu", "nomura", "misawa", "athome", "homes"]:
                if model_name.startswith(code):
                    company_code = code
                    break
            logging.info(f"  Estimating for table: {model_class.__name__} (Total records: {qs.count()})")
            
            for item in qs:
                if not item.price or item.price <= 0:
                    continue
                
                url = getattr(item, "pageUrl", "")
                if not url:
                    continue
                
                try:
                    with transaction.atomic():
                      # 1. 評価レコードの取得または新規作成
                      defaults = {
                          "company": company_code,
                          "property_type": ptype,
                          "property_id": item.id
                      }
                      eval_record, created = PropertyEvaluation.objects.get_or_create(
                          property_url=url,
                          defaults=defaults
                      )
                      
                      # すでに予測価格が入っている場合は推定スキップ
                      if not created and eval_record.first_stage_predicted_price is not None:
                          logging.info(f"Skipping already estimated property: {url}")
                          continue
                      
                      # 2. シリアライズとAPIリクエスト送信
                      serialized_data = _serialize_property(item, ptype)
                      payload = {
                          "property_data": serialized_data,
                          "interior_score": 4.0,  # 基準値
                          "layout_score": 3.5     # 基準値
                      }
                      
                      api_url = f"{api_base_url}{ptype}"
                      response = requests.post(api_url, json=payload, timeout=30)
                      
                      if response.status_code == 200:
                          res_data = response.json()
                          pred1 = res_data["first_stage_predicted_price"]
                          pred2 = res_data["second_stage_predicted_price"]
                      else:
                          logging.error(f"API estimation failed for {url}: status={response.status_code}, response={response.text}")
                          continue
                      
                      eval_record.first_stage_predicted_price = pred1
                      eval_record.second_stage_predicted_price = pred2
                      
                      # 3. アパート（投資用）の場合は追加で投資収支評価を実行
                      if ptype == "apartment":
                          eval_record = evaluate_investment_property(item, eval_record)
                          total_evaluated += 1
                      
                      eval_record.save()
                      total_processed += 1
                      
                      # 4. 推定乖離率のインメモリ集計 (価格単位の整合性を取って万円単位で計算)
                      asking_price_man = float(item.price) / 10000.0
                      
                      # 面積が0や極小のものは、パースミスと判断してモデル評価統計から除外する
                      area = 10.0
                      if hasattr(item, "senyuMenseki") and item.senyuMenseki is not None:
                          area = float(item.senyuMenseki)
                      elif hasattr(item, "tatemonoMenseki") and item.tatemonoMenseki is not None:
                          area = float(item.tatemonoMenseki)
                      elif hasattr(item, "tochiMenseki") and item.tochiMenseki is not None:
                          area = float(item.tochiMenseki)
                          
                      is_valid_area = (area >= 10.0)
                      
                      # 100万円以上、かつ3億円未満の正常価格帯のみを統計対象とする
                      if 100.0 <= asking_price_man < 30000.0 and pred2 > 0 and is_valid_area:
                          err = (asking_price_man - float(pred2)) / float(pred2)
                          errors.append(err)
                          
                except Exception as e:
                    logging.error(f"Failed to evaluate property {url}: {e}")
            post_slack(f"📊 【価格推定進捗】 物件種別: {ptype} の推定が完了しました。現在累計 {total_processed} 件を処理済みです。")
                    
    logging.info(f"Batch evaluation finished. Processed={total_processed}, Evaluated (Investment)={total_evaluated}")
    
    # 統計的妥当性評価（正規分布適合度）の算出
    mean_err = 0.0
    status_str = "データ不足のため判定不能"
    n = 0
    if errors:
        import numpy as np
        arr = np.array(errors)
        n = len(arr)
        mean_err = float(np.mean(arr))
        std_err = float(np.std(arr))
        
        # 歪度 (Skewness) と 尖度 (Kurtosis) の算出
        if n >= 3 and std_err > 0:
            skewness = float(np.sum((arr - mean_err) ** 3) / n / (std_err ** 3))
            kurtosis = float(np.sum((arr - mean_err) ** 4) / n / (std_err ** 4) - 3.0)
        else:
            skewness = 0.0
            kurtosis = 0.0
            
        is_normal = (abs(mean_err) <= 0.05) and (abs(skewness) <= 1.0) and (abs(kurtosis) <= 2.0)
        status_str = "適合 (良好)" if is_normal else "不適合 (偏り・異常値あり)"
        
        logging.info("=========================================")
        logging.info("【価格推定モデルの統計妥当性レポート】")
        logging.info(f"評価物件数: {n} 件")
        logging.info(f"平均乖離率 (Mean Error): {mean_err * 100:.2f}% (基準値: ±5.0%以内)")
        logging.info(f"乖離標準偏差 (StdDev): {std_err * 100:.2f}%")
        logging.info(f"歪度 (Skewness): {skewness:.3f} (基準値: ±1.0以内)")
        logging.info(f"尖度 (Kurtosis): {kurtosis:.3f} (基準値: ±2.0以内)")
        logging.info(f"正規分布適合判定: {status_str}")
        logging.info("=========================================")

    # Slackへ完了レポートを送信
    report_msg = (
        f"✅ 【価格推定完了】 一括価格推定および投資シミュレーション評価処理が完了しました。\n\n"
        f"📋 **処理概要**:\n"
        f"  - 処理物件数: {total_processed} 件\n"
        f"  - 投資評価件数: {total_evaluated} 件\n"
        f"  - 適合評価対象数: {n} 件\n"
        f"  - 平均乖離率: {mean_err * 100:.2f}%\n"
        f"  - 正規分布適合判定: *{status_str}*"
    )
    post_slack(report_msg)

if __name__ == "__main__":
    main()
