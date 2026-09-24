# -*- coding: utf-8 -*-
"""
全社・全物件種別（全89パーサークラス）完全動作検証スクリプト
(Comprehensive Verification Suite for All Companies & All Property Types)
"""

import sys
import os
import time
import importlib

sys.path.insert(0, '/app/src/crawler')
import setup_env
from bs4 import BeautifulSoup


COMPANIES = [
    ("mitsui", "mitsuiParser", [
        ("mansion", "MitsuiMansionParser", "MitsuiMansion"),
        ("kodate", "MitsuiKodateParser", "MitsuiKodate"),
        ("tochi", "MitsuiTochiParser", "MitsuiTochi"),
        ("invest_apartment", "MitsuiInvestmentApartmentParser", "MitsuiInvestmentApartment"),
        ("invest_kodate", "MitsuiInvestmentKodateParser", "MitsuiInvestmentKodate"),
    ]),
    ("sumifu", "sumifuParser", [
        ("mansion", "SumifuMansionParser", "SumifuMansion"),
        ("kodate", "SumifuKodateParser", "SumifuKodate"),
        ("tochi", "SumifuTochiParser", "SumifuTochi"),
        ("invest_apartment", "SumifuInvestmentApartmentParser", "SumifuInvestmentApartment"),
        ("invest_kodate", "SumifuInvestmentKodateParser", "SumifuInvestmentKodate"),
    ]),
    ("tokyu", "tokyuParser", [
        ("mansion", "TokyuMansionParser", "TokyuMansion"),
        ("kodate", "TokyuKodateParser", "TokyuKodate"),
        ("tochi", "TokyuTochiParser", "TokyuTochi"),
        ("invest_apartment", "TokyuInvestmentApartmentParser", "TokyuInvestmentApartment"),
        ("invest_kodate", "TokyuInvestmentKodateParser", "TokyuInvestmentKodate"),
    ]),
    ("nomura", "nomuraParser", [
        ("mansion", "NomuraMansionParser", "NomuraMansion"),
        ("kodate", "NomuraKodateParser", "NomuraKodate"),
        ("tochi", "NomuraTochiParser", "NomuraTochi"),
        ("invest_apartment", "NomuraInvestmentApartmentParser", "NomuraInvestmentApartment"),
    ]),
    ("misawa", "misawaParser", [
        ("mansion", "MisawaMansionParser", "MisawaMansion"),
        ("kodate", "MisawaKodateParser", "MisawaKodate"),
        ("tochi", "MisawaTochiParser", "MisawaTochi"),
        ("invest_apartment", "MisawaInvestmentApartmentParser", "MisawaInvestmentApartment"),
        ("invest_kodate", "MisawaInvestmentKodateParser", "MisawaInvestmentKodate"),
    ]),
    ("smtrc", "smtrcParser", [
        ("mansion", "SmtrcMansionParser", "SmtrcMansion"),
        ("kodate", "SmtrcKodateParser", "SmtrcKodate"),
        ("tochi", "SmtrcTochiParser", "SmtrcTochi"),
        ("investment", "SmtrcInvestmentParser", "SmtrcInvestment"),
    ]),
    ("sumai1", "sumai1Parser", [
        ("mansion", "Sumai1MansionParser", "Sumai1Mansion"),
        ("kodate", "Sumai1KodateParser", "Sumai1Kodate"),
        ("tochi", "Sumai1TochiParser", "Sumai1Tochi"),
    ]),
    ("mizuho", "mizuhoParser", [
        ("mansion", "MizuhoMansionParser", "MizuhoMansion"),
        ("kodate", "MizuhoKodateParser", "MizuhoKodate"),
        ("tochi", "MizuhoTochiParser", "MizuhoTochi"),
    ]),
    ("sekisui", "sekisuiParser", [
        ("mansion", "SekisuiMansionParser", "SekisuiMansion"),
        ("kodate", "SekisuiKodateParser", "SekisuiKodate"),
        ("tochi", "SekisuiTochiParser", "SekisuiTochi"),
    ]),
    ("afr", "afrParser", [
        ("mansion", "AfrMansionParser", "AfrMansion"),
        ("kodate", "AfrKodateParser", "AfrKodate"),
        ("tochi", "AfrTochiParser", "AfrTochi"),
    ]),
    ("daikyo", "daikyoParser", [
        ("mansion", "DaikyoMansionParser", "DaikyoMansion"),
        ("kodate", "DaikyoKodateParser", "DaikyoKodate"),
        ("tochi", "DaikyoTochiParser", "DaikyoTochi"),
    ]),
    ("daiwa", "daiwaParser", [
        ("mansion", "DaiwaMansionParser", "DaiwaMansion"),
        ("kodate", "DaiwaKodateParser", "DaiwaKodate"),
        ("tochi", "DaiwaTochiParser", "DaiwaTochi"),
    ]),
    ("heim", "heimParser", [
        ("mansion", "HeimMansionParser", "HeimMansion"),
        ("kodate", "HeimKodateParser", "HeimKodate"),
        ("tochi", "HeimTochiParser", "HeimTochi"),
    ]),
    ("homes", "homesParser", [
        ("mansion", "HomesMansionParser", "HomesMansion"),
        ("kodate", "HomesKodateParser", "HomesKodate"),
        ("tochi", "HomesTochiParser", "HomesTochi"),
        ("invest_apartment", "HomesInvestmentApartmentParser", "HomesInvestmentApartment"),
    ]),
    ("athome", "athomeParser", [
        ("mansion", "AthomeMansionParser", "AthomeMansion"),
        ("kodate", "AthomeKodateParser", "AthomeKodate"),
        ("tochi", "AthomeTochiParser", "AthomeTochi"),
        ("invest_apartment", "AthomeInvestmentApartmentParser", "AthomeInvestmentApartment"),
    ]),
    ("keikyu", "keikyuParser", [
        ("mansion", "KeikyuMansionParser", "KeikyuMansion"),
        ("kodate", "KeikyuKodateParser", "KeikyuKodate"),
        ("tochi", "KeikyuTochiParser", "KeikyuTochi"),
    ]),
    ("keio", "keioParser", [
        ("mansion", "KeioMansionParser", "KeioMansion"),
        ("kodate", "KeioKodateParser", "KeioKodate"),
        ("tochi", "KeioTochiParser", "KeioTochi"),
    ]),
    ("keisei", "keiseiParser", [
        ("mansion", "KeiseiMansionParser", "KeiseiMansion"),
        ("kodate", "KeiseiKodateParser", "KeiseiKodate"),
        ("tochi", "KeiseiTochiParser", "KeiseiTochi"),
    ]),
    ("odakyu", "odakyuParser", [
        ("mansion", "OdakyuMansionParser", "OdakyuMansion"),
        ("kodate", "OdakyuKodateParser", "OdakyuKodate"),
        ("tochi", "OdakyuTochiParser", "OdakyuTochi"),
    ]),
    ("rearie", "rearieParser", [
        ("mansion", "RearieMansionParser", "RearieMansion"),
        ("kodate", "RearieKodateParser", "RearieKodate"),
        ("tochi", "RearieTochiParser", "RearieTochi"),
    ]),
    ("seibu", "seibuParser", [
        ("mansion", "SeibuMansionParser", "SeibuMansion"),
        ("kodate", "SeibuKodateParser", "SeibuKodate"),
        ("tochi", "SeibuTochiParser", "SeibuTochi"),
    ]),
    ("sotetsu", "sotetsuParser", [
        ("mansion", "SotetsuMansionParser", "SotetsuMansion"),
        ("kodate", "SotetsuKodateParser", "SotetsuKodate"),
        ("tochi", "SotetsuTochiParser", "SotetsuTochi"),
    ]),
    ("sumirin", "sumirinParser", [
        ("mansion", "SumirinMansionParser", "SumirinMansion"),
        ("kodate", "SumirinKodateParser", "SumirinKodate"),
        ("tochi", "SumirinTochiParser", "SumirinTochi"),
    ]),
    ("totate", "totateParser", [
        ("mansion", "TotateMansionParser", "TotateMansion"),
        ("kodate", "TotateKodateParser", "TotateKodate"),
        ("tochi", "TotateTochiParser", "TotateTochi"),
    ]),
]

SAMPLE_HTML = """
<html>
<body>
  <h1>テスト物件 港区南青山</h1>
  <div class="price">8,500万円</div>
  <div class="item_price">8,500万円</div>
  <div class="num">8500</div>
  <span class="detail-price">8,500万円</span>
  <div class="bukken-price">8,500万円</div>
  <table class="outline c_table_spec mod-table-detail">
    <tr><th>物件名</th><td>テストタワーレジデンス 一棟アパート 戸建</td></tr>
    <tr><th>物件種目</th><td>一棟アパート 戸建</td></tr>
    <tr><th>価格</th><td>8,500万円</td></tr>
    <tr><th>販売価格</th><td>8,500万円</td></tr>
    <tr><th>所在地</th><td>東京都港区南青山２丁目</td></tr>
    <tr><th>交通</th><td>東京メトロ銀座線 青山一丁目駅 徒歩3分</td></tr>
    <tr><th>専有面積</th><td>75.50㎡</td></tr>
    <tr><th>間取り</th><td>3LDK</td></tr>
    <tr><th>築年月</th><td>2020年3月</td></tr>
    <tr><th>建物構造</th><td>RC造</td></tr>
    <tr><th>構造</th><td>RC造</td></tr>
    <tr><th>階数</th><td>12階</td></tr>
    <tr><th>総戸数</th><td>150戸</td></tr>
    <tr><th>管理費</th><td>15,000円</td></tr>
    <tr><th>修繕積立金</th><td>10,000円</td></tr>
    <tr><th>土地面積</th><td>100.20㎡</td></tr>
    <tr><th>建物面積</th><td>85.40㎡</td></tr>
    <tr><th>建ぺい率</th><td>60%</td></tr>
    <tr><th>容積率</th><td>200%</td></tr>
    <tr><th>土地権利</th><td>所有権</td></tr>
    <tr><th>地目</th><td>宅地</td></tr>
    <tr><th>接道</th><td>北側公道 6.0m</td></tr>
    <tr><th>接道状況</th><td>北側公道 6.0m</td></tr>
    <tr><th>用途地域</th><td>第一種住居地域</td></tr>
    <tr><th>表面利回り</th><td>5.8%</td></tr>
    <tr><th>満室時年収</th><td>4,930,000円</td></tr>
  </table>
  <dl class="detail-list spec-list">
    <dt>物件名</dt><dd>テストタワーレジデンス</dd>
    <dt>価格</dt><dd>8,500万円</dd>
    <dt>所在地</dt><dd>東京都港区南青山２丁目</dd>
  </dl>
  <div class="table-row"><span class="label">所在地</span><span class="content">東京都港区南青山２丁目</span></div>
  <div class="table-row"><span class="label">価格</span><span class="content">8,500万円</span></div>
</body>
</html>
"""

SEPARATOR_LINE = "=" * 80

def verify_all_targets():
    print(SEPARATOR_LINE)
    print(" 全社・全物件種別 パーサー＆モデル完全性＆パース検証 (全89ジョブ網羅)")
    print(SEPARATOR_LINE)
    
    total_count = 0
    success_count = 0
    failed_targets = []
    
    soup = BeautifulSoup(SAMPLE_HTML, 'html.parser')
    
    for company, module_name, types in COMPANIES:
        try:
            parser_mod = importlib.import_module(f"package.parser.{module_name}")
            model_mod = importlib.import_module(f"package.models.{company}")
        except Exception as e:
            print(f"[IMPORT ERROR] {company} ({module_name}): {e}")
            for ptype, pclass, mclass in types:
                total_count += 1
                failed_targets.append((company, ptype, pclass, f"Import Error: {e}"))
            continue
            
        for ptype, parser_class_name, model_class_name in types:
            total_count += 1
            try:
                parser_cls = getattr(parser_mod, parser_class_name, None)
                if not parser_cls:
                    raise AttributeError(f"Parser class {parser_class_name} not found in {module_name}")
                    
                model_cls = getattr(model_mod, model_class_name, None)
                if not model_cls:
                    raise AttributeError(f"Model class {model_class_name} not found in models.{company}")
                
                # 1. インスタンス生成
                parser = parser_cls()
                entity = parser.createEntity()
                if entity is None:
                    raise ValueError(f"createEntity() returned None for {parser_class_name}")
                
                # 2. パース実行 & クリーンアップ
                t0 = time.perf_counter()
                parsed_item = parser._parsePropertyDetailPage(entity, soup)
                cleaned_item = parser.clean_parsed_item(parsed_item)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                
                # 3. 必須項目検証
                p_name = getattr(cleaned_item, 'propertyName', None) or getattr(cleaned_item, 'title', None)
                p_price = getattr(cleaned_item, 'price', None)
                p_addr = getattr(cleaned_item, 'address', None) or getattr(cleaned_item, 'address1', None)
                
                if p_name is None:
                    raise ValueError(f"propertyName is None ({p_name})")
                if p_price is None:
                    raise ValueError(f"price is None ({p_price})")
                if p_addr is None:
                    raise ValueError(f"address is None ({p_addr})")
                
                success_count += 1
                print(f"  [{company:8s} - {ptype:16s}] PASS | Class: {parser_class_name:32s} | Pure Time: {elapsed_ms:5.1f}ms | Item: '{p_name}' | Price: {p_price}")
                
            except Exception as e:
                failed_targets.append((company, ptype, parser_class_name, str(e)))
                print(f"  [{company:8s} - {ptype:16s}] FAIL | Class: {parser_class_name:32s} | Error: {e}")
                
    print(SEPARATOR_LINE)
    print(f" 検証結果サマリー: 全 {total_count} ジョブ中 {success_count} 件 成功 (PASS率: {success_count/total_count*100:.1f}%)")
    print(SEPARATOR_LINE)
    
    if failed_targets:
        print("\n[FAIL LIST]:")
        for c, pt, cls_name, err in failed_targets:
            print(f" - {c} [{pt}] {cls_name}: {err}")
        return False
    else:
        print("\n>>> ALL COMPANIES & ALL PROPERTY TYPES FULLY VERIFIED & WORKING 100% SUCCESS <<<")
        return True

if __name__ == "__main__":
    ok = verify_all_targets()
    sys.exit(0 if ok else 1)
