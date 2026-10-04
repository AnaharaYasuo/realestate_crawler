from unittest.mock import MagicMock
from package.models.base import PropertyBaseModel
from package.models.sumifu import SumifuKodate
from package.models.evaluation import PropertyEvaluation
from scripts.ops.run_bulk_ml_evaluation import _process_eval_chunk


def test_property_base_model_page_url_unique_constraint():
    """PropertyBaseModel の pageUrl に unique=True が定義されていることの検証"""
    field = PropertyBaseModel._meta.get_field("pageUrl")
    assert field.unique is True, "pageUrl field on PropertyBaseModel must have unique=True"


def test_subclass_page_url_unique_constraint():
    """具象クラス（例: SumifuKodate）の pageUrl に unique=True が継承されていることの検証"""
    field = SumifuKodate._meta.get_field("pageUrl")
    assert field.unique is True, "pageUrl field on SumifuKodate must have unique=True"


def test_process_eval_chunk_deduplication(monkeypatch):
    """_process_eval_chunk においてチャンク内重複URLが適切に排除され bulk_create されることの検証"""
    created_batches = []

    def mock_bulk_create(records, batch_size=500, ignore_conflicts=False):
        created_batches.append((list(records), ignore_conflicts))
        return records

    monkeypatch.setattr(PropertyEvaluation.objects, "bulk_create", mock_bulk_create)

    def _make_dummy_item(url, item_id, price):
        item = MagicMock()
        item.pageUrl = url
        item.id = item_id
        item.price = price
        item.propertyName = "テスト戸建"
        item.address = "東京都世田谷区"
        item.traffic = "徒歩5分"
        item.biko = ""
        item.tochikenri = "所有権"
        item.genkyo = "空家"
        item.torihiki = "媒介"
        item.setsubi = ""
        item.chikunengetsu = None
        item.chikunengetsuStr = "2020年1月"
        item.kaisuStr = "2階建"
        item.total_floors = 2
        item.chidai = None
        item.chidaiStr = ""
        return item

    item1 = _make_dummy_item("https://www.stepon.co.jp/kodate/detail_16682026/", 1, 50000000)
    item2 = _make_dummy_item("https://www.stepon.co.jp/kodate/detail_16682026/", 2, 50000000)  # 同一URL
    item3 = _make_dummy_item("https://www.stepon.co.jp/kodate/detail_99999999/", 3, 60000000)  # 別URL

    chunk = [item1, item2, item3]
    predicted_prices = [5200.0, 5200.0, 6500.0]
    existing_eval_map = {}

    _p_cnt, _d_cnt = _process_eval_chunk(
        chunk=chunk,
        predicted_prices=predicted_prices,
        existing_eval_map=existing_eval_map,
        company="sumifu",
        property_type="kodate",
        batch_size=500,
    )

    assert len(created_batches) == 1
    batch_records, ignore_conflicts = created_batches[0]
    assert ignore_conflicts is True, "bulk_create must use ignore_conflicts=True"
    # 重複URLが排除され、2件のみ create 対象になっていること
    assert len(batch_records) == 2
    urls = [r.property_url for r in batch_records]
    assert urls == [
        "https://www.stepon.co.jp/kodate/detail_16682026/",
        "https://www.stepon.co.jp/kodate/detail_99999999/",
    ]
