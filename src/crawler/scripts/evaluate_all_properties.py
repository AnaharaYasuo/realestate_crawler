# -*- coding: utf-8 -*-
import os
import sys
import logging

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

from package.ml.predict import predict_first_stage, predict_second_stage
from package.ml.investment_evaluator import evaluate_investment_property

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

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
    logging.info("Starting batch property estimation and investment evaluation...")
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
                        
                        # 2. 一次予測・二次予測の実行
                        pred1 = predict_first_stage(item)
                        # ダミースコア（4.0, 3.5）を基準に二次予測を実行
                        pred2 = predict_second_stage(item, 4.0, 3.5)
                        
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
                        # (機械学習モデルの適用限界外である3億円以上の超高額物件や、パースミスによる異常データを除外)
                        if 100.0 <= asking_price_man < 30000.0 and pred2 > 0 and is_valid_area:
                            err = (asking_price_man - float(pred2)) / float(pred2)
                            errors.append(err)
                        
                except Exception as e:
                    logging.error(f"Failed to evaluate property {url}: {e}")
                    
    logging.info(f"Batch evaluation finished. Processed={total_processed}, Evaluated (Investment)={total_evaluated}")
    
    # 統計的妥当性評価（正規分布適合度）の算出
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

if __name__ == "__main__":
    main()
