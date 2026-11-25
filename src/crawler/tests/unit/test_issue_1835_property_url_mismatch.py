# -*- coding: utf-8 -*-
"""
Issue #1835: お宝物件通知での別テーブル同一property_id誤結合および
PropertyEvaluation.property_type の粗いカテゴリ名上書きバグの回帰テスト
"""
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from package.models.athome import AthomeInvestmentApartment
from package.models.evaluation import PropertyEvaluation
from package.models.kenbiya import KenbiyaInvestmentApartment, KenbiyaInvestmentBuilding
from package.utils.data_validator import tag_property_integrity
from scripts.ops.run_ttl_expired_recrawl import (
    TtlTarget,
    _FetchedOutcomeItem,
    _apply_eval_entry_mutation,
)
from scripts.ops.send_recommendations import (
    _dispatch_single_recommendation,
    batch_resolve_properties,
    get_property_record,
)


@pytest.mark.django_db
def test_batch_and_single_resolve_picks_matching_building_over_same_id_apartment():
    """
    KenbiyaInvestmentApartment と KenbiyaInvestmentBuilding に同一連番 id が存在し、
    PropertyEvaluation.property_type='apartment' であっても、
    property_url が pp3 (KenbiyaInvestmentBuilding) なら正しく Building 側を解決すること。
    """
    apt = KenbiyaInvestmentApartment.objects.create(
        id=1473,
        pageUrl="https://www.kenbiya.com/pp2/s/tokyo/adachi-ku/re_48430606cb/",
        propertyName="東京都足立区 1棟アパート",
        address="東京都足立区北加平町",
        price=99900000,
    )
    bldg = KenbiyaInvestmentBuilding.objects.create(
        id=1473,
        pageUrl="https://www.kenbiya.com/pp3/s/tokyo/shinjuku-ku/re_4814675p1h/",
        propertyName="アーバンハイツ",
        address="東京都新宿区舟町15番地54",
        price=258000000,
    )
    ev = PropertyEvaluation.objects.create(
        company="kenbiya",
        property_type="apartment",
        property_id=bldg.id,
        property_url=bldg.pageUrl,
        is_published=True,
        is_slack_notified=False,
        is_first_stage_passed=True,
        first_stage_predicted_price=40103,
    )

    resolved = batch_resolve_properties([ev])
    assert ev.property_url in resolved
    assert isinstance(resolved[ev.property_url], KenbiyaInvestmentBuilding)
    assert resolved[ev.property_url].pageUrl == bldg.pageUrl
    assert resolved[ev.property_url].propertyName == "アーバンハイツ"

    single = get_property_record(ev)
    assert single is not None
    assert isinstance(single, KenbiyaInvestmentBuilding)
    assert single.pageUrl == bldg.pageUrl
    assert single.pageUrl != apt.pageUrl


@pytest.mark.django_db
def test_property_id_fallback_rejects_mismatched_url_object():
    """
    対象URLのレコードが存在せず、別テーブルに同一 id の別物件のみが存在する場合、
    property_id フォールバックで別物件を絶対に誤結合しないこと。
    """
    KenbiyaInvestmentApartment.objects.create(
        id=1473,
        pageUrl="https://www.kenbiya.com/pp2/s/tokyo/adachi-ku/re_48430606cb/",
        propertyName="東京都足立区 1棟アパート",
        address="東京都足立区北加平町",
        price=99900000,
    )
    ev = PropertyEvaluation.objects.create(
        company="kenbiya",
        property_type="apartment",
        property_id=1473,
        property_url="https://www.kenbiya.com/pp3/s/tokyo/shinjuku-ku/re_4814675p1h/",
        is_published=True,
        is_slack_notified=False,
        is_first_stage_passed=True,
        first_stage_predicted_price=40103,
    )

    resolved = batch_resolve_properties([ev])
    assert ev.property_url not in resolved

    single = get_property_record(ev)
    assert single is None


@pytest.mark.django_db
def test_property_id_fallback_still_resolves_same_url_with_tracking_query():
    """
    追跡クエリパラメータの差異のみであれば、property_id フォールバックで同一物件を正常解決できること。
    """
    apt = AthomeInvestmentApartment.objects.create(
        pageUrl="https://www.athome.co.jp/buy_other/1066689698/",
        propertyName="アットホーム一棟アパート",
        price=45000000,
    )
    ev = PropertyEvaluation.objects.create(
        company="athome",
        property_type="investmentapartment",
        property_id=apt.id,
        property_url="https://www.athome.co.jp/buy_other/1066689698/?BKLISTID=001LPC",
        is_published=True,
        is_slack_notified=False,
        is_first_stage_passed=True,
        first_stage_predicted_price=6000,
    )

    resolved = batch_resolve_properties([ev])
    assert ev.property_url in resolved
    assert resolved[ev.property_url].id == apt.id

    single = get_property_record(ev)
    assert single is not None
    assert single.id == apt.id


def test_dispatch_single_recommendation_blocks_url_mismatch():
    """
    通知直前の安全弁: eval_rec.property_url と prop.pageUrl が別物件の場合、
    Slack送信をブロックして False を返すこと。
    """
    ev = MagicMock(
        property_url="https://www.kenbiya.com/pp3/s/tokyo/shinjuku-ku/re_4814675p1h/",
        property_type="investmentbuilding",
    )
    prop = MagicMock(
        pageUrl="https://www.kenbiya.com/pp2/s/tokyo/adachi-ku/re_48430606cb/",
        propertyName="東京都足立区 1棟アパート",
    )

    with patch("scripts.ops.send_recommendations.send_slack_message") as mock_slack:
        sent = _dispatch_single_recommendation(ev, prop, "テスト理由")

    assert sent is False
    mock_slack.assert_not_called()


@pytest.mark.django_db
def test_tag_property_integrity_preserves_exact_model_property_type():
    """
    tag_property_integrity は PropertyTypeDetector の粗い 'apartment' を渡されても、
    実モデルクラス KenbiyaInvestmentBuilding に対応する 'investmentbuilding' を保存すること。
    """
    bldg = KenbiyaInvestmentBuilding.objects.create(
        pageUrl="https://www.kenbiya.com/pp3/s/tokyo/shinjuku-ku/re_4814675p1h/",
        propertyName="アーバンハイツ",
        address="東京都新宿区舟町15番地54",
        traffic="都営新宿線 曙橋駅 徒歩2分",
        price=258000000,
        tochiMenseki=Decimal("204.59"),
        tatemonoMenseki=Decimal("277.08"),
    )

    tag_property_integrity(bldg, "apartment", "kenbiya")

    ev = PropertyEvaluation.objects.get(property_url=bldg.pageUrl)
    assert ev.company == "kenbiya"
    assert ev.property_type == "investmentbuilding"
    assert ev.property_id == bldg.id


@pytest.mark.django_db
def test_ttl_recrawl_apply_eval_mutation_preserves_exact_model_property_type():
    """
    TTL再クロール (_apply_eval_entry_mutation) が KenbiyaInvestmentBuilding を保存する際、
    PropertyEvaluation.property_type を 'apartment' に劣化上書きせず 'investmentbuilding' を維持すること。
    """
    bldg = KenbiyaInvestmentBuilding.objects.create(
        pageUrl="https://www.kenbiya.com/pp3/s/tokyo/shinjuku-ku/re_4814675p1h/",
        propertyName="アーバンハイツ",
        address="東京都新宿区舟町15番地54",
        traffic="都営新宿線 曙橋駅 徒歩2分",
        price=258000000,
        tochiMenseki=Decimal("204.59"),
        tatemonoMenseki=Decimal("277.08"),
    )
    ev = PropertyEvaluation.objects.create(
        company="kenbiya",
        property_type="investmentbuilding",
        property_id=bldg.id,
        property_url=bldg.pageUrl,
        is_published=True,
    )
    target = TtlTarget(
        evaluation_id=ev.id,
        company="kenbiya",
        property_type="investmentbuilding",
        property_id=bldg.id,
        property_url=bldg.pageUrl,
    )
    entry = _FetchedOutcomeItem(kind="active", target=target, item=bldg)
    eval_updates: dict[int, PropertyEvaluation] = {}
    eval_creates: dict[str, PropertyEvaluation] = {}

    _apply_eval_entry_mutation(
        entry=entry,
        eval_rec=ev,
        now_ts=datetime(2026, 11, 25, 0, 0, tzinfo=UTC),
        cur_sha="deadbeef",
        eval_updates=eval_updates,
        eval_creates=eval_creates,
    )

    assert ev.property_type == "investmentbuilding"
