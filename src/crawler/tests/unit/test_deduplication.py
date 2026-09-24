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


def test_calculate_property_similarity_get_real_property_exception_logs_warning():
    """get_real_property で apps.get_model が例外を投げた場合 WARNING でログ出力してNoneを返すことを検証"""
    from unittest.mock import MagicMock, patch
    eval_a = MagicMock()
    eval_a.company = "unknown_company"
    eval_a.property_type = "mansion"
    eval_a.id = 999
    eval_b = MagicMock()
    eval_b.company = "unknown_company"
    eval_b.property_type = "mansion"
    eval_b.id = 998

    with patch("django.apps.apps.get_model", side_effect=Exception("Model not found")):
        with patch("package.utils.deduplication.logger.warning") as mock_warn:
            result = calculate_property_similarity(eval_a, eval_b)
            assert result == 0.0
            assert mock_warn.call_count >= 1
            log_msg = mock_warn.call_args[0][0]
            assert "Failed to load real property data" in log_msg


def test_get_root_parent_resolves_chains_and_handles_cycles():
    """get_root_parent が多段チェーンをルート親に解決し、循環参照でも無限ループしないことを検証"""
    from unittest.mock import MagicMock
    from package.utils.deduplication import get_root_parent

    # 1. 親なしノード
    node_a = MagicMock()
    node_a.id = 10
    node_a.duplicate_of_id = None
    node_a.duplicate_of = None
    assert get_root_parent(node_a) == node_a

    # 2. 2段チェーン: B -> A
    node_b = MagicMock()
    node_b.id = 20
    node_b.duplicate_of_id = 10
    node_b.duplicate_of = node_a
    assert get_root_parent(node_b) == node_a

    # 3. 3段チェーン: C -> B -> A
    node_c = MagicMock()
    node_c.id = 30
    node_c.duplicate_of_id = 20
    node_c.duplicate_of = node_b
    assert get_root_parent(node_c) == node_a

    # 4. 循環参照 (A -> B -> A) でも最小IDのノードに安全着地すること
    node_a.duplicate_of_id = 20
    node_a.duplicate_of = node_b
    assert get_root_parent(node_a).id == 10
    assert get_root_parent(node_b).id == 10


@pytest.mark.django_db
def test_parent_selection_strictly_earliest_registration_order():
    """登録日時順（IDが小さい方）が常に親になり、循環参照や逆転参照が発生しないことをDB連携で検証"""
    from package.models.mitsui import MitsuiMansion

    # 1. 物件1 (過去登録・ID小)
    m1 = MitsuiMansion.objects.create(
        propertyName="重複テストマンション",
        pageUrl="http://example.com/prop/order1",
        price=60000000,
        address="東京都渋谷区神南1-1-1",
        senyuMenseki=80.0,
        chikunengetsuStr="2021年5月",
    )
    eval1 = PropertyEvaluation.objects.create(
        company="mitsui",
        property_type="mansion",
        property_id=m1.id,
        property_url=m1.pageUrl,
        analysis_status="completed",
    )

    # 2. 物件2 (新規登録・ID大)
    m2 = MitsuiMansion.objects.create(
        propertyName="重複テストマンション別館",
        pageUrl="http://example.com/prop/order2",
        price=60000000,
        address="東京都渋谷区神南1-1-1",
        senyuMenseki=80.0,
        chikunengetsuStr="2021年5月",
    )
    eval2 = PropertyEvaluation.objects.create(
        company="mitsui",
        property_type="mansion",
        property_id=m2.id,
        property_url=m2.pageUrl,
        analysis_status="pending",
    )

    # eval1.id < eval2.id であることを確認
    assert eval1.id < eval2.id

    # 【検証1】eval2（ID大・後から登録）から探した場合、eval1（ID小・先に登録）が親になること
    parent_for_eval2 = find_duplicate_property(eval2)
    assert parent_for_eval2 is not None
    assert parent_for_eval2.id == eval1.id
    assert parent_for_eval2.id < eval2.id

    # 【検証2】eval1（ID小・先に登録）から探した場合、eval2（ID大）は絶対に親にならないこと（Noneを返却）
    # これにより相互循環参照（eval1.duplicate_of = eval2 かつ eval2.duplicate_of = eval1）が完全防止される
    parent_for_eval1 = find_duplicate_property(eval1)
    assert parent_for_eval1 is None

    # 【検証3】多段チェーンの平坦化 (eval3 -> eval2 -> eval1 とならず eval3 -> eval1 となること)
    eval2.duplicate_of = eval1
    eval2.save()

    m3 = MitsuiMansion.objects.create(
        propertyName="重複テストマンション 3号",
        pageUrl="http://example.com/prop/order3",
        price=60000000,
        address="東京都渋谷区神南1-1-1",
        senyuMenseki=80.0,
        chikunengetsuStr="2021年5月",
    )
    eval3 = PropertyEvaluation.objects.create(
        company="mitsui",
        property_type="mansion",
        property_id=m3.id,
        property_url=m3.pageUrl,
        analysis_status="pending",
    )

    parent_for_eval3 = find_duplicate_property(eval3)
    assert parent_for_eval3 is not None
    # eval2 ではなくルート親である eval1 が直接返却されること
    assert parent_for_eval3.id == eval1.id

    # クリーンアップ
    eval3.delete()
    eval2.delete()
    eval1.delete()
    m3.delete()
    m2.delete()
    m1.delete()


def test_similarity_score_helpers():
    """類似度計算ヘルパーのゼロ値・非類似およびポジティブ境界スコアを検証"""
    from unittest.mock import MagicMock, patch
    from package.utils.deduplication import (
        _calculate_address_score,
        _calculate_area_score,
        _calculate_price_score,
        _calculate_date_score,
    )

    prop1 = MagicMock()
    prop2 = MagicMock()

    # 1. 住所が空または全く異なる場合、0.0 であること
    prop1.address = ""
    prop2.address = ""
    assert _calculate_address_score(prop1, prop2) == 0.0

    prop1.address = "東京都新宿区西新宿1-1-1"
    prop2.address = "北海道札幌市中央区大通西1-1"
    assert _calculate_address_score(prop1, prop2) == 0.0

    # 2. 面積が0または乖離が大きい場合、0.0 であること
    prop1.tatemonoMenseki = 0
    prop1.senyuMenseki = 0
    prop2.tatemonoMenseki = 50.0
    prop2.senyuMenseki = 0
    assert _calculate_area_score(prop1, prop2) == 0.0

    prop1.tatemonoMenseki = 100.0
    prop2.tatemonoMenseki = 50.0
    assert _calculate_area_score(prop1, prop2) == 0.0

    # 3. 価格が0または乖離が大きい場合、0.0 であること
    prop1.price = 0
    prop2.price = 50000000
    assert _calculate_price_score(prop1, prop2) == 0.0

    prop1.price = 100000000
    prop2.price = 50000000
    assert _calculate_price_score(prop1, prop2) == 0.0

    # 4. 築年月が異なる場合、0.0 であること
    prop1.chikunengetsu = None
    prop1.chikunengetsuStr = "2020年3月"
    prop2.chikunengetsu = None
    prop2.chikunengetsuStr = "2000年1月"
    assert _calculate_date_score(prop1, prop2) == 0.0

    # 5. 各ヘルパーの正の採点帯・境界値の個別検証
    prop1.tatemonoMenseki = 100.0
    prop2.tatemonoMenseki = 99.0
    assert _calculate_area_score(prop1, prop2) == pytest.approx(0.3)
    prop2.tatemonoMenseki = 97.0
    assert _calculate_area_score(prop1, prop2) == pytest.approx(0.2)
    prop2.tatemonoMenseki = 93.0
    assert _calculate_area_score(prop1, prop2) == pytest.approx(0.1)

    prop1.price = 100_000_000
    prop2.price = 99_000_000
    assert _calculate_price_score(prop1, prop2) == pytest.approx(0.2)
    prop2.price = 97_000_000
    assert _calculate_price_score(prop1, prop2) == pytest.approx(0.15)
    prop2.price = 93_000_000
    assert _calculate_price_score(prop1, prop2) == pytest.approx(0.1)
    prop2.price = 85_000_000
    assert _calculate_price_score(prop1, prop2) == pytest.approx(0.05)

    prop1.address = prop2.address = "東京都新宿区西新宿1-1-1"
    assert _calculate_address_score(prop1, prop2) == pytest.approx(0.5)
    prop1.address, prop2.address = "A", "B"
    with patch("package.utils.deduplication.SequenceMatcher") as matcher:
        matcher.return_value.ratio.return_value = 0.85
        assert _calculate_address_score(prop1, prop2) == pytest.approx(0.35)
        matcher.return_value.ratio.return_value = 0.7
        assert _calculate_address_score(prop1, prop2) == pytest.approx(0.2)

    prop1.chikunengetsu = None
    prop1.chikunengetsuStr = "2020年3月"
    prop2.chikunengetsu = None
    prop2.chikunengetsuStr = "2020年3月"
    assert _calculate_date_score(prop1, prop2) == pytest.approx(0.1)




