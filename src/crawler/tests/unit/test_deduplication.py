# -*- coding: utf-8 -*-
import pytest
from package.models.evaluation import PropertyEvaluation
from package.utils.deduplication import normalize_address, calculate_property_similarity, find_duplicate_property

def test_normalize_address():
    # 1. 全角数字の変換
    assert normalize_address("東京都新宿区西新宿２丁目８−１") == "東京都新宿区西新宿2-8-1"
    
    # 2. 漢数字の変換
    assert normalize_address("東京都千代田区永田町一丁目七番一号") == "東京都千代田区永田町1-7-1"
    
    # 3. スペースや番地ハイフン変換の表記揺れ
    assert normalize_address("東京都 港区 赤坂 9丁目 7番 1号") == "東京都港区赤坂9-7-1"
    assert normalize_address("東京都港区赤坂9-7-1-101") == "東京都港区赤坂9-7-1-101"

@pytest.mark.django_db
def test_property_similarity_and_deduplication():
    # テスト用の評価レコードと物件レコードを擬似的に作成して検証する
    # DB連携テストのため django_db を使用
    
    from package.models.mitsui import MitsuiMansion
    
    # 1. 物件Aを作成 (代表物件)
    m_a = MitsuiMansion.objects.create(
        propertyName="テストマンションA棟",
        pageUrl="http://example.com/prop/a",
        price=50000000, # 5000万円
        address="東京都新宿区西新宿1-1-1",
        saikou="南",
        madori="3LDK",
        senyuMenseki=70.0,
        chikunengetsuStr="2020年3月",
        saikouKadobeya="南"
    )
    
    eval_a = PropertyEvaluation.objects.create(
        company="mitsui",
        property_type="mansion",
        property_id=m_a.id,
        property_url=m_a.pageUrl,
        analysis_status="completed",
        total_investment_score=None,
        investment_score=75.0,
        is_slack_notified=False
    )
    
    # 2. 物件Bを作成 (住所の表記揺れと微細な価格・面積の誤差がある重複物件)
    m_b = MitsuiMansion.objects.create(
        propertyName="テストマンション A棟 (別名)",
        pageUrl="http://example.com/prop/b",
        price=50500000, # 5050万円 (1%の誤差)
        address="東京都新宿区西新宿一丁目一番一号", # 表記揺れ
        saikou="南",
        madori="3LDK",
        senyuMenseki=70.2, # 微細な誤差
        chikunengetsuStr="2020年3月",
        saikouKadobeya="南"
    )
    
    eval_b = PropertyEvaluation.objects.create(
        company="mitsui",
        property_type="mansion",
        property_id=m_b.id,
        property_url=m_b.pageUrl,
        analysis_status="pending",
        total_investment_score=None,
        investment_score=75.0,
        is_slack_notified=False
    )
    
    # 類似度の計算
    similarity = calculate_property_similarity(eval_a, eval_b)
    print(f"Calculated similarity between A and B: {similarity}")
    # 住所一致 (+0.5), 面積一致 (+0.3), 価格誤差1% (+0.2), 築年月一致 (+0.1)
    # 総合スコアは 0.85 以上になるべき
    assert similarity >= 0.85
    
    # 重複検出関数の検証
    parent = find_duplicate_property(eval_b)
    assert parent is not None
    assert parent.id == eval_a.id
    
    # クリーンアップ
    eval_a.delete()
    eval_b.delete()
    m_a.delete()
    m_b.delete()
