# -*- coding: utf-8 -*-
import os
import sys
import logging
import asyncio

# Django設定のロード
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import realestateSettings
realestateSettings.configure()

from django.db import transaction
from package.models.evaluation import PropertyEvaluation
from package.utils.slack import send_slack_message
from asgiref.sync import async_to_sync
import time

# 各社モデルのインポート (物件名や価格の取得用)
from package.models.mitsui import MitsuiMansion, MitsuiKodate, MitsuiTochi, MitsuiInvestmentKodate, MitsuiInvestmentApartment
from package.models.sumifu import SumifuMansion, SumifuKodate, SumifuTochi, SumifuInvestmentKodate, SumifuInvestmentApartment
from package.models.tokyu import TokyuMansion, TokyuKodate, TokyuTochi, TokyuInvestmentKodate, TokyuInvestmentApartment
from package.models.nomura import NomuraMansion, NomuraKodate, NomuraTochi, NomuraInvestmentKodate, NomuraInvestmentApartment
from package.models.misawa import MisawaMansion, MisawaKodate, MisawaTochi, MisawaInvestmentKodate, MisawaInvestmentApartment
from package.models.athome import AthomeMansion, AthomeKodate, AthomeTochi, AthomeInvestmentApartment
from package.models.homes import HomesMansion, HomesKodate, HomesTochi, HomesInvestmentApartment

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

def get_property_record(eval_record):
    """URLに対応する各社テーブルの物件レコードを取得する"""
    url = eval_record.property_url
    company = eval_record.company
    ptype = eval_record.property_type
    
    # 検索テーブルの対応マッピング
    mappings = {
        "mitsui": {
            "mansion": MitsuiMansion, "kodate": MitsuiKodate, "tochi": MitsuiTochi,
            "invest_kodate": MitsuiInvestmentKodate, "invest_apartment": MitsuiInvestmentApartment
        },
        "sumifu": {
            "mansion": SumifuMansion, "kodate": SumifuKodate, "tochi": SumifuTochi,
            "invest_kodate": SumifuInvestmentKodate, "invest_apartment": SumifuInvestmentApartment
        },
        "tokyu": {
            "mansion": TokyuMansion, "kodate": TokyuKodate, "tochi": TokyuTochi,
            "invest_kodate": TokyuInvestmentKodate, "invest_apartment": TokyuInvestmentApartment
        },
        "nomura": {
            "mansion": NomuraMansion, "kodate": NomuraKodate, "tochi": NomuraTochi,
            "invest_kodate": NomuraInvestmentKodate, "invest_apartment": NomuraInvestmentApartment
        },
        "misawa": {
            "mansion": MisawaMansion, "kodate": MisawaKodate, "tochi": MisawaTochi,
            "invest_kodate": MisawaInvestmentKodate, "invest_apartment": MisawaInvestmentApartment
        },
        "athome": {
            "mansion": AthomeMansion, "kodate": AthomeKodate, "tochi": AthomeTochi,
            "invest_apartment": AthomeInvestmentApartment
        },
        "homes": {
            "mansion": HomesMansion, "kodate": HomesKodate, "tochi": HomesTochi,
            "invest_apartment": HomesInvestmentApartment
        }
    }
    
    comp_map = mappings.get(company)
    if not comp_map:
        return None
    model_cls = comp_map.get(ptype)
    if not model_cls:
        return None
        
    return model_cls.objects.filter(pageUrl=url).first()

def send_recommendations():
    logging.info("Scanning for new hot recommendation properties to send via Slack...")
    
    # Slack通知未送信の評価レコードを抽出
    candidates = PropertyEvaluation.objects.filter(is_slack_notified=False)
    
    sent_count = 0
    
    for eval_rec in candidates:
        prop = get_property_record(eval_rec)
        if not prop:
            continue
            
        asking_price = getattr(prop, "price", 0)
        if not asking_price or asking_price <= 0:
            continue
            
        asking_price_man = asking_price // 10000
        
        pred_price = float(eval_rec.second_stage_predicted_price or eval_rec.first_stage_predicted_price or 0.0)
        
        is_recommend = False
        reason = ""
        
        # 判定条件1: アパート（投資用）
        if eval_rec.property_type in ["invest_apartment", "apartment"]:
            score = eval_rec.investment_score or eval_rec.total_investment_score or 0.0
            if score >= 60.0:
                is_recommend = True
                reason = f"【高利回り・優良融資スコア: {score:.1f}点】"
                
        # 判定条件2: 居住用 (割安度 15% 以上、ただし40%以上の極端な乖離は2σ乖離の予測エラーとして除外)
        elif pred_price > 0:
            discount_pct = (pred_price - asking_price_man) / pred_price * 100.0
            if discount_pct >= 40.0 or discount_pct <= -40.0:
                logging.warning(f"Skipping alert (2-sigma error suspect): Property {prop.pageUrl} has extreme prediction gap of {discount_pct:.1f}% (Predicted: {pred_price}万円, Asking: {asking_price_man}万円)")
            elif discount_pct >= 15.0:
                is_recommend = True
                reason = f"【市場予測価格より {discount_pct:.1f}% 割安（お宝物件！）】"
                
        if not is_recommend:
            # 基準を満たさないものはスキップ（通知済フラグは立てない）
            continue
            
        # Slack送信メッセージ構築
        ptype_jp = {
            "mansion": "中古マンション",
            "kodate": "中古戸建",
            "tochi": "土地",
            "invest_kodate": "戸建（投資用）",
            "invest_apartment": "一棟アパート",
            "apartment": "一棟アパート"
        }.get(eval_rec.property_type, eval_rec.property_type)
        
        p_name = getattr(prop, "propertyName", "不明な物件名")
        
        address = getattr(prop, "address", getattr(prop, "address1", ""))
        access = getattr(prop, "traffic", "")
        if not access:
            rw = getattr(prop, "railway1", "")
            st = getattr(prop, "station1", "")
            wm = getattr(prop, "railwayWalkMinute1Str", "")
            if rw and st:
                access = f"{rw} {st} {wm}"
                
        area_info = ""
        senyu = getattr(prop, "senyuMensekiStr", "")
        tochi = getattr(prop, "tochiMensekiStr", "")
        tate = getattr(prop, "tatemonoMensekiStr", "")
        if senyu: area_info += f"専有面積: {senyu} "
        if tochi: area_info += f"土地面積: {tochi} "
        if tate: area_info += f"建物面積: {tate} "
            
        chikunen = getattr(prop, "chikunengetsuStr", getattr(prop, "chikunenki", ""))
        madori = getattr(prop, "madori", "")

        msg = (
            f"🏆 [お宝物件検出] {reason}\n"
            f"物件名: {p_name} ({ptype_jp})\n"
            f"売出価格: {asking_price_man}万円\n"
            f"理論予測価格: {int(pred_price)}万円\n"
            f"【物件詳細】\n"
            f"住所: {address}\n"
            f"アクセス: {access}\n"
        )
        if area_info:
            msg += f"面積: {area_info.strip()}\n"
        if madori:
            msg += f"間取り: {madori}\n"
        if chikunen:
            msg += f"築年月: {chikunen}\n"
        
        if eval_rec.property_type in ["invest_apartment", "apartment", "invest_kodate"]:
            msg += (
                f"想定積算価格: {eval_rec.estimated_sekisan_price}万円\n"
                f"年間キャッシュフロー: {eval_rec.cash_flow}万円/年 (DSCR: {eval_rec.dscr})\n"
            )
            
        msg += f"詳細URL: {eval_rec.property_url}\n"
        
        # 物件種別ごとの投稿先チャンネル定義 (環境変数経由での設定に対応し、デフォルトはSLACK_CHANNEL_ID)
        channel_id = os.getenv("SLACK_RECOMMEND_CHANNEL_ID") or os.getenv("SLACK_CHANNEL_ID")
        if eval_rec.property_type == "mansion":
            channel_id = os.getenv("SLACK_RECOMMEND_MANSION", channel_id)
        elif eval_rec.property_type == "kodate":
            channel_id = os.getenv("SLACK_RECOMMEND_KODATE", channel_id)
        elif eval_rec.property_type == "tochi":
            channel_id = os.getenv("SLACK_RECOMMEND_TOCHI", channel_id)
        elif eval_rec.property_type in ["invest_apartment", "apartment"]:
            channel_id = os.getenv("SLACK_RECOMMEND_INVEST_APARTMENT", channel_id)
        elif eval_rec.property_type == "invest_kodate":
            channel_id = os.getenv("SLACK_RECOMMEND_INVEST_KODATE", channel_id)

        logging.info(f"Sending recommendation for {p_name} ({eval_rec.property_url}) to {channel_id}")
        
        # 実際のSlack送信実行
        # send_slack_message は async なので、async_to_sync でラップして呼ぶ
        success = async_to_sync(send_slack_message)(msg, channel=channel_id)
        if success:
            with transaction.atomic():
                eval_rec.is_slack_notified = True
                eval_rec.save()
            sent_count += 1
            # Slack APIレートリミット対策のための短いスリープ
            time.sleep(1.0)
            
    logging.info(f"Recommendation sending completed. Sent: {sent_count} properties.")

def main():
    send_recommendations()

if __name__ == "__main__":
    main()
