# -*- coding: utf-8 -*-
"""
全国メッシュ・駅別家賃相場クローラー＆キャップレート収集基盤の単体・動的検証テスト (Issue #1354)
"""
from __future__ import annotations

import datetime
from decimal import Decimal
import time
from unittest.mock import MagicMock, patch

from django.db import models
import pytest
import requests

from package.ml.features import (
    _cap_rate_cache,
    _init_global_caches,
    _rent_market_cache,
    query_cap_rate_benchmark,
    query_rent_market_potential,
    reset_reference_caches,
)
from package.models.evaluation import RentMarketPotential
from package.models.sumifu import SumifuInvestmentApartment, SumifuInvestmentKodate
from package.rag_ingest.market_crawler import GcsArchiveStorage, MarketDataCrawler, parse_embedded_raw_meta
from package.rag_ingest.market_data_parsers import (
    _classify_reit_sector,
    extract_portal_sublinks,
    parse_athome_rent_page,
    parse_homes_rent_table,
    parse_homes_toushi_page,
    parse_japan_reit_rimawari,
    parse_suumo_rent_table,
)
from package.rag_ingest.rent_mesh_extractor import KenbiyaBlockedException
from scripts.data_import.sync_rent_and_cap_rate_potentials import (
    reingest_from_gcs_raw_archive,
    sync_estat_rent_baselines,
    sync_internal_db_rent_and_yield_potentials,
    sync_jrei_cap_rate_benchmarks,
    sync_rent_and_cap_rate_potentials,
    _crawl_suumo_for_prefecture,
    bulk_upsert_cap_rate_records,
    bulk_upsert_rent_records,
)

pytestmark = pytest.mark.django_db

SAMPLE_SUUMO_HTML = """
<html><head><title>【SUUMO】東京都千代田区の賃貸マンション家賃相場</title></head>
<body><table>
  <tr><th>間取り</th><th>家賃相場</th></tr>
  <tr><td>ワンルーム</td><td>13.9 万円</td><td></td><td>物件を探す</td></tr>
  <tr><td>1K</td><td>14.3 万円</td><td></td><td>物件を探す</td></tr>
  <tr><td>1LDK</td><td>22.1 万円</td><td></td><td>物件を探す</td></tr>
  <tr><td>2K</td><td>-</td><td></td><td>物件を探す</td></tr>
  <tr><td>2LDK</td><td>31.5 万円</td><td></td><td>物件を探す</td></tr>
  <tr><td>3LDK</td><td>45.0 万円</td><td></td><td>物件を探す</td></tr>
</table></body></html>
"""

SAMPLE_ATHOME_HTML = """
<html><head><title>【アットホーム】千代田区の家賃相場</title></head>
<body>
  <div class="souba-box">
    <dl><dt>すべて</dt><dd>18.64 万円</dd></dl>
    <dl><dt>ワンルーム</dt><dd>13.98 万円</dd></dl>
    <dl><dt>1K</dt><dd>14.10 万円</dd></dl>
    <dl><dt>1LDK</dt><dd>22.98 万円</dd></dl>
    <dl><dt>3K</dt><dd>-</dd></dl>
    <dl><dt>4LDK以上</dt><dd>62.9 万円</dd></dl>
  </div>
</body></html>
"""

SAMPLE_HOMES_RENT_HTML = """
<html><head><title>【ホームズ】千代田区の家賃相場</title></head>
<body><table>
  <tr><th>間取り</th><th>家賃相場</th><th>該当物件</th></tr>
  <tr><td>ワンルーム</td><td>15.50 万円 0 円</td><td>物件一覧を見る</td></tr>
  <tr><td>1K</td><td>14.65 万円 0 円</td><td>物件一覧を見る</td></tr>
  <tr><td>1LDK</td><td>24.62 万円 0 円</td><td>物件一覧を見る</td></tr>
  <tr><td>2K</td><td>-</td><td>物件一覧を見る</td></tr>
</table></body></html>
"""

SAMPLE_HOMES_TOUSHI_DETAIL_HTML = """
<html><head><title>【ホームズ】東京都千代田区の賃貸需要はこちら 見える賃貸経営</title></head>
<body>
  <section>
    <h2>東京都千代田区 の空室率</h2>
    <p>住宅全般 (持ち家など含む) 12.6 % 5,300 ( 全空家 ) / 42,210 ( 全住宅 )</p>
    <p>賃貸用住宅 15.2 % 3,810 ( 賃貸住宅空家 ) / 25,090 ( 借家 )</p>
  </section>
  <section>
    <h2>東京都千代田区 の利回り</h2>
    <p>利回り 前月比 +0.3 % 4.8 % 出典： LIFULL HOME'S 不動産投資</p>
  </section>
  <section>
    <h3>東京都千代田区 の 希望する住戸の広さ</h3>
    <table>
      <tr><th>専有面積</th><th>検索回数 | 掲載物件</th></tr>
      <tr><td>20㎡～</td><td>25.0 % 15.0 %</td></tr>
      <tr><td>25㎡～</td><td>20.0 % 18.0 %</td></tr>
    </table>
  </section>
</body></html>
"""

SAMPLE_JAPAN_REIT_HTML = """
<html><head><title>JAPAN-REIT.COM 利回り一覧</title></head>
<body>
  <table>
    <tr><th>REIT平均分配金利回り （％）</th><th>REIT時価総額合計</th></tr>
    <tr><td>5.65% (+0.05)</td><td>14,366,392</td></tr>
  </table>
  <table>
    <tr>
      <th>証券 コード</th><th>投資法人</th><th>投資口 価格(円)</th><th>前日比</th>
      <th>分配金 利回り (%)</th><th>1口NAV (円)</th><th>NAV 倍率</th>
      <th>時価総額 (百万円)</th><th>出来高</th><th>決算期</th><th>運用資産</th>
    </tr>
    <tr>
      <td>8951</td><td>日本ビルファンド投資法人</td><td>118,800</td><td>-1.82%</td>
      <td>4.21</td><td>123,347</td><td>0.96</td><td>1,047,222</td><td>37,912</td><td>6/12</td><td>オフィス</td>
    </tr>
    <tr>
      <td>3269</td><td>アドバンス・レジデンス投資法人</td><td>142,000</td><td>+0.21%</td>
      <td>4.05</td><td>155,000</td><td>0.92</td><td>420,000</td><td>8,000</td><td>1/7</td><td>住宅</td>
    </tr>
    <tr>
      <td>8953</td><td>日本都市ファンド投資法人</td><td>105,900</td><td>-1.30%</td>
      <td>5.71</td><td>131,423</td><td>0.81</td><td>761,718</td><td>15,988</td><td>2/8</td><td>商業施設</td>
    </tr>
  </table>
</body></html>
"""


class InMemoryStorageStub:
    """GCS ObjectStorageManager のインメモリ代替スタブ。"""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    def upload_bytes(self, data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
        self.blobs[key] = data
        return f"gs://stub-bucket/{key}"

    def list_files(self, prefix: str = "") -> list[str]:
        return sorted(k for k in self.blobs if k.startswith(prefix))

    def read_bytes(self, key: str) -> bytes:
        return self.blobs[key]


def test_parse_suumo_athome_and_homes_rent_tables_fast_and_accurate():
    """SUUMO・at home・LIFULL HOME'S 家賃相場パーサーの数値精度と純パース時間 (< 1,000ms) を検証"""
    t0 = time.perf_counter()
    suumo_rows = parse_suumo_rent_table(
        SAMPLE_SUUMO_HTML,
        prefecture="東京都",
        city="千代田区",
        station_name="東京",
        building_type="mansion",
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert elapsed_ms < 1000.0
    assert len(suumo_rows) == 5  # 2K '-' excluded
    by_layout = {r["layout_type"]: r for r in suumo_rows}
    assert by_layout["1R"]["monthly_rent_yen"] == 139_000
    assert by_layout["1R"]["building_type"] == "mansion"
    assert by_layout["1R"]["station_name"] == "東京"
    assert by_layout["1R"]["rent_per_sqm"] == round(139_000 / float(by_layout["1R"]["standard_area_sqm"]))
    assert by_layout["1LDK"]["monthly_rent_yen"] == 221_000
    assert by_layout["3LDK"]["monthly_rent_yen"] == 450_000

    t1 = time.perf_counter()
    athome_rows = parse_athome_rent_page(
        SAMPLE_ATHOME_HTML,
        prefecture="東京都",
        city="千代田区",
        building_type="all",
    )
    assert (time.perf_counter() - t1) * 1000.0 < 1000.0
    at_by_layout = {r["layout_type"]: r for r in athome_rows}
    assert at_by_layout["all"]["monthly_rent_yen"] == 186_400
    assert at_by_layout["1R"]["monthly_rent_yen"] == 139_800
    assert at_by_layout["4LDK+"]["monthly_rent_yen"] == 629_000
    assert "3K" not in at_by_layout

    t2 = time.perf_counter()
    homes_rows = parse_homes_rent_table(
        SAMPLE_HOMES_RENT_HTML,
        prefecture="東京都",
        city="千代田区",
    )
    assert (time.perf_counter() - t2) * 1000.0 < 1000.0
    hm_by_layout = {r["layout_type"]: r for r in homes_rows}
    assert hm_by_layout["1R"]["monthly_rent_yen"] == 155_000
    assert hm_by_layout["1K"]["monthly_rent_yen"] == 146_500
    assert hm_by_layout["1LDK"]["monthly_rent_yen"] == 246_200


def test_parse_homes_toushi_and_japan_reit_benchmarks():
    """HOME'S見える賃貸経営（空室率・利回り・需給）とJAPAN-REIT.COMパーサーの精度検証"""
    t0 = time.perf_counter()
    toushi_rows = parse_homes_toushi_page(
        SAMPLE_HOMES_TOUSHI_DETAIL_HTML,
        prefecture="東京都",
        city="千代田区",
    )
    assert (time.perf_counter() - t0) * 1000.0 < 1000.0
    assert len(toushi_rows) >= 1
    rec = toushi_rows[0]
    assert float(rec["expected_gross_yield"]) == pytest.approx(4.8, abs=0.01)
    assert float(rec["rental_vacancy_rate"]) == pytest.approx(15.2, abs=0.01)
    assert float(rec["total_vacancy_rate"]) == pytest.approx(12.6, abs=0.01)
    assert float(rec["demand_supply_score"]) > 1.0  # 検索回数 45% > 掲載物件 33%

    t1 = time.perf_counter()
    reit_rows = parse_japan_reit_rimawari(SAMPLE_JAPAN_REIT_HTML, jgb_10y_yield=1.10)
    assert (time.perf_counter() - t1) * 1000.0 < 1000.0
    by_asset = {r["asset_type"]: r for r in reit_rows}
    assert "mansion" in by_asset
    assert "commercial" in by_asset
    assert "all" in by_asset
    assert float(by_asset["mansion"]["expected_net_cap_rate"]) > 0
    assert int(by_asset["mansion"]["jgb_spread_bps"]) > 100


def test_kenbiya_guard_and_gcs_dual_archive_and_reingest():
    """健美家URLブロック・GCS原本テキスト＆構造化JSONL保存・GCS原本からのDB再構築を検証"""
    stub_storage = InMemoryStorageStub()
    crawler = MarketDataCrawler(storage_mgr=stub_storage, min_interval_sec=0.0)

    with pytest.raises(KenbiyaBlockedException):
        crawler.validate_url("https://www.kenbiya.com/pp13/")
    with pytest.raises(KenbiyaBlockedException):
        crawler.validate_url("https://sub.kenbiya.com./market/")

    res = crawler.archive_raw_and_curated_to_gcs(
        url="https://suumo.jp/chintai/soba/tokyo/sc_chiyoda/?ts=1",
        html_content=SAMPLE_SUUMO_HTML,
        source_id="suumo_soba",
        prefecture="東京都",
        city="千代田区",
        station="",
        extracted_count=5,
    )
    assert res["raw_key"].startswith("rag/raw/rent_mesh/source=suumo_soba/pref=東京都/")
    assert res["curated_key"].startswith("rag/curated/statistics/pref=東京都/")
    assert "rag/manifest/rent_mesh_sources.jsonl" in stub_storage.blobs

    inv = crawler.list_existing_gcs_statistics_inventory()
    assert inv["rent_mesh_raw_count"] == 1
    assert inv["statistics_curated_count"] == 1

    # GCS上の原本HTMLから構造化DBテーブルへ再構築できること
    reingest_stats = reingest_from_gcs_raw_archive(storage_mgr=stub_storage)
    assert reingest_stats["rent_records_upserted"] == 5
    db_rec = RentMarketPotential.objects.get(
        prefecture="東京都",
        city="千代田区",
        building_type="mansion",
        layout_type="1LDK",
        source="suumo_soba",
    )
    assert db_rec.monthly_rent_yen == 221_000
    assert db_rec.gcs_raw_key == res["raw_key"]


def test_sync_public_baselines_internal_db_and_memory_caches():
    """e-Stat・不動産投資家調査・自社DB集計の一括同期と O(1) インメモリ階層検索を検証"""
    # 自社DBに収益物件サンプルを投入
    SumifuInvestmentApartment.objects.create(
        propertyName="テスト一棟マンション神田",
        pageUrl="https://www.stepon.co.jp/pro/detail_test_1354_apt/",
        priceStr="1億2,000万円",
        price=120_000_000,
        address="東京都千代田区内神田1丁目",
        address1="東京都",
        address2="千代田区",
        station1="神田",
        railway1="JR山手線",
        railwayWalkMinute1=4,
        hikiwatashi="相談",
        genkyo="賃貸中",
        tochikenri="所有権",
        torihiki="仲介",
        grossYield=Decimal("5.40"),
        annualRent=6_480_000,
        monthlyRent=540_000,
        currentStatus="満室賃貸中",
        tochiMensekiStr="100.00㎡",
        tochiMenseki=Decimal("100.00"),
        tatemonoMensekiStr="150.00㎡",
        tatemonoMenseki=Decimal("150.00"),
        kouzou="鉄筋コンクリート造",
        chikunengetsuStr="2018年3月",
        chikunengetsu=datetime.date(2018, 3, 1),
        soukosuStr="6戸",
        soukosu=6,
        propertyType="Apartment",
    )
    SumifuInvestmentKodate.objects.create(
        propertyName="テスト賃貸戸建横浜",
        pageUrl="https://www.stepon.co.jp/pro/detail_test_1354_kod/",
        priceStr="2,500万円",
        price=25_000_000,
        address="神奈川県横浜市西区浅間町1丁目",
        address1="神奈川県",
        address2="横浜市西区",
        station1="横浜",
        railway1="JR東海道本線",
        railwayWalkMinute1=10,
        hikiwatashi="即時",
        genkyo="賃貸中",
        tochikenri="所有権",
        torihiki="仲介",
        grossYield=Decimal("7.20"),
        annualRent=1_800_000,
        monthlyRent=150_000,
        currentStatus="賃貸中",
        tochiMensekiStr="80.00㎡",
        tochiMenseki=Decimal("80.00"),
        tatemonoMensekiStr="75.00㎡",
        tatemonoMenseki=Decimal("75.00"),
        kouzou="木造",
        chikunengetsuStr="2010年5月",
        chikunengetsu=datetime.date(2010, 5, 1),
        propertyType="Kodate",
    )

    estat_cnt = sync_estat_rent_baselines()
    jrei_cnt = sync_jrei_cap_rate_benchmarks(jgb_10y_yield=1.15)
    internal_res = sync_internal_db_rent_and_yield_potentials()

    assert estat_cnt >= 47 * 3
    assert jrei_cnt >= 47 * 4
    assert internal_res["rent_records"] >= 2
    assert internal_res["cap_rate_records"] >= 2

    summary = sync_rent_and_cap_rate_potentials(enable_live_crawl=False)
    assert summary["total_rent_records"] >= estat_cnt
    assert summary["total_cap_rate_records"] >= jrei_cnt

    # インメモリキャッシュ初期化 & slots=True 非Djangoモデル検証
    reset_reference_caches()
    _init_global_caches(force_refresh=True)

    assert len(_rent_market_cache) > 0
    assert len(_cap_rate_cache) > 0
    for records in _rent_market_cache.values():
        for r in records:
            assert not isinstance(r, models.Model)
            assert hasattr(r, "__slots__")
    for records in _cap_rate_cache.values():
        for r in records:
            assert not isinstance(r, models.Model)
            assert hasattr(r, "__slots__")

    # 駅 -> 市区町村 -> 都道府県の階層フォールバック検証
    kanda_rent = query_rent_market_potential("東京都", "千代田区", station_name="神田駅", building_type="mansion")
    assert kanda_rent is not None
    assert kanda_rent[0] == 3600  # 540,000円 / 150㎡ = 3,600円/㎡

    pref_fallback_rent = query_rent_market_potential("北海道", "未登録郡テスト村", station_name="幻駅", building_type="apartment")
    assert pref_fallback_rent is not None
    assert pref_fallback_rent[0] > 500

    cap_tokyo = query_cap_rate_benchmark("東京都", "千代田区", station_name="神田", asset_type="apartment_rc")
    assert cap_tokyo is not None
    assert cap_tokyo.expected_gross_yield is not None and cap_tokyo.expected_gross_yield > 0
    assert cap_tokyo.standard_opex_ratio > 0


def test_dynamic_live_html_smoke_suumo_toushi_and_jreit():
    """現在公開中の実サイト生HTMLを取得し、純パース時間 < 1,000ms で非空の構造化レコードが取れることを検証"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    }

    r_suumo = requests.get("https://suumo.jp/chintai/soba/tokyo/sc_chiyoda/?ts=1", headers=headers, timeout=15)
    r_suumo.encoding = r_suumo.apparent_encoding or "utf-8"
    assert r_suumo.status_code == 200
    t0 = time.perf_counter()
    live_suumo = parse_suumo_rent_table(r_suumo.text, prefecture="東京都", city="千代田区", building_type="mansion")
    assert (time.perf_counter() - t0) * 1000.0 < 1000.0
    assert len(live_suumo) >= 3

    r_toushi = requests.get("https://toushi.homes.co.jp/owner/tokyo/city13101/", headers=headers, timeout=15)
    r_toushi.encoding = "utf-8"
    assert r_toushi.status_code == 200
    t1 = time.perf_counter()
    live_toushi = parse_homes_toushi_page(r_toushi.text, prefecture="東京都", city="千代田区")
    assert (time.perf_counter() - t1) * 1000.0 < 1000.0
    assert len(live_toushi) >= 1
    assert live_toushi[0]["rental_vacancy_rate"] is not None

    r_jreit = requests.get("https://www.japan-reit.com/list/rimawari/", headers=headers, timeout=15)
    r_jreit.encoding = r_jreit.apparent_encoding or "utf-8"
    assert r_jreit.status_code == 200
    t2 = time.perf_counter()
    live_jreit = parse_japan_reit_rimawari(r_jreit.text, jgb_10y_yield=1.15)
    assert (time.perf_counter() - t2) * 1000.0 < 1000.0
    assert len(live_jreit) >= 2


def test_suumo_hokkaido_slug_and_mysql_bulk_upsert_dialect():
    """SUUMO北海道専用スラッグ（hokkaido_）と MySQL ON DUPLICATE KEY UPDATE 方言分岐を検証"""
    stub_storage = InMemoryStorageStub()
    crawler = MarketDataCrawler(storage_mgr=stub_storage, min_interval_sec=0.0)
    fetched_urls: list[str] = []

    def fake_fetch(url: str, timeout: int = 20) -> str | None:
        fetched_urls.append(url)
        return SAMPLE_SUUMO_HTML

    with patch.object(crawler, "fetch_html", side_effect=fake_fetch):
        _crawl_suumo_for_prefecture(crawler, "北海道", "hokkaido", max_details=0)

    assert fetched_urls == ["https://suumo.jp/chintai/soba/hokkaido_/area/"]

    # MySQL vendor 時に unique_fields を渡さないこと（回帰防止）
    with (
        patch("scripts.data_import.sync_rent_and_cap_rate_potentials.connection") as mock_conn,
        patch("package.models.evaluation.RentMarketPotential.objects.bulk_create") as mock_rent_bulk,
        patch("package.models.evaluation.CapRateBenchmarkPotential.objects.bulk_create") as mock_cap_bulk,
    ):
        mock_conn.vendor = "mysql"
        bulk_upsert_rent_records([{
            "prefecture": "東京都",
            "city": "千代田区",
            "building_type": "mansion",
            "layout_type": "1R",
            "monthly_rent_yen": 140000,
            "standard_area_sqm": Decimal("22.00"),
            "rent_per_sqm": 6364,
            "source": "suumo_soba",
        }])
        bulk_upsert_cap_rate_records([{
            "prefecture": "東京都",
            "city": "千代田区",
            "asset_type": "mansion",
            "expected_net_cap_rate": Decimal("3.50"),
            "source": "jrei_survey",
        }])
        assert "unique_fields" not in mock_rent_bulk.call_args.kwargs
        assert "unique_fields" not in mock_cap_bulk.call_args.kwargs


def test_parsers_edge_cases_and_crawler_storage_and_rate_limit():
    """都道府県一覧テーブル・総合REIT分類・サブリンク抽出・GcsArchiveStorage・レート制限・メタデータ境界を検証"""
    # 1. 都道府県トップ一覧テーブル（詳細メトリクス無しの市区町村空室率一覧）
    pref_table_html = """
    <html><body><table>
      <tr><th>市区町村</th><th>空室率</th></tr>
      <tr><td>千代田区</td><td>14.5 %</td></tr>
      <tr><td>港区</td><td>11.2 %</td></tr>
    </table></body></html>
    """
    pref_rows = parse_homes_toushi_page(pref_table_html, prefecture="東京都")
    assert len(pref_rows) == 2
    assert pref_rows[0]["city"] == "千代田区"
    assert pref_rows[0]["rental_vacancy_rate"] == Decimal("14.50")

    # 2. 総合・ホテル系REIT銘柄の 'all' 分類 & サブリンク重複排除抽出
    assert _classify_reit_sector("ジャパン・ホテル・リート投資法人", "ホテル") == "all"
    links_html = """
    <html><body>
      <a href="/chintai/soba/tokyo/sc_chiyoda/">千代田区</a>
      <a href="/chintai/soba/tokyo/sc_chiyoda/">千代田区(重複)</a>
      <a href="/chintai/soba/tokyo/sc_minato/">港区</a>
      <a href="/other/link/">無関係</a>
    </body></html>
    """
    links = extract_portal_sublinks(links_html, "https://suumo.jp", r"/chintai/soba/tokyo/sc_[a-z]+/")
    assert links == [
        ("千代田区", "https://suumo.jp/chintai/soba/tokyo/sc_chiyoda/"),
        ("港区", "https://suumo.jp/chintai/soba/tokyo/sc_minato/"),
    ]

    # 3. parse_embedded_raw_meta の異常系・片側一致（AND vs OR 防衛）
    assert parse_embedded_raw_meta("") == {}
    assert parse_embedded_raw_meta("<!-- RENT_MESH_META: {\"a\": 1}") == {}
    assert parse_embedded_raw_meta("{\"a\": 1} -->") == {}
    assert parse_embedded_raw_meta("<!-- RENT_MESH_META: {broken json} -->") == {}
    assert parse_embedded_raw_meta('<!-- RENT_MESH_META: {"source_id": "suumo_soba"} -->\n<html></html>') == {
        "source_id": "suumo_soba"
    }

    # 4. GcsArchiveStorage のバケット解決・upload/list/read 契約検証
    fake_blob = MagicMock()
    fake_blob.download_as_bytes.return_value = b"raw-bytes"
    fake_listed = MagicMock()
    fake_listed.name = "rag/raw/rent_mesh/sample.html"
    fake_bucket = MagicMock()
    fake_bucket.blob.return_value = fake_blob
    fake_client = MagicMock()
    fake_client.bucket.return_value = fake_bucket
    fake_client.list_blobs.return_value = [fake_listed]

    with (
        patch("google.cloud.storage.Client", return_value=fake_client),
        patch.dict("os.environ", {"GCS_BUCKET_NAME": "", "STORAGE_BUCKET": ""}, clear=False),
    ):
        gcs = GcsArchiveStorage(bucket_name=None)
        assert gcs.bucket_name == "realestate-images-sumifu-prod"
        uri = gcs.upload_bytes(b"hello", "rag/test.txt", content_type="text/plain")
        assert uri == "gs://realestate-images-sumifu-prod/rag/test.txt"
        assert gcs.list_files("rag/") == ["rag/raw/rent_mesh/sample.html"]
        assert gcs.read_bytes("rag/raw/rent_mesh/sample.html") == b"raw-bytes"

    # 5. MarketDataCrawler の fetch_html・レート制限 sleep 分岐・manifest_key 返却検証
    stub_storage = InMemoryStorageStub()
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.apparent_encoding = "utf-8"
    mock_resp.text = "<html>ok</html>"
    mock_session.get.return_value = mock_resp

    crawler_zero = MarketDataCrawler(storage_mgr=stub_storage, min_interval_sec=0.0, session=mock_session)
    with patch("package.rag_ingest.market_crawler.time.sleep") as mock_sleep_zero:
        body = crawler_zero.fetch_html("https://suumo.jp/chintai/soba/tokyo/area/")
        assert body == "<html>ok</html>"
        mock_sleep_zero.assert_not_called()

    crawler_rl = MarketDataCrawler(storage_mgr=stub_storage, min_interval_sec=0.5, session=mock_session)
    crawler_rl._last_request_ts = 100.0
    with (
        patch("package.rag_ingest.market_crawler.time.monotonic", return_value=100.1),
        patch("package.rag_ingest.market_crawler.time.sleep") as mock_sleep_rl,
    ):
        body2 = crawler_rl.fetch_html("https://suumo.jp/chintai/soba/tokyo/area/")
        assert body2 == "<html>ok</html>"
        mock_sleep_rl.assert_called_once()
        assert mock_sleep_rl.call_args[0][0] > 0.0

    arc = crawler_zero.archive_raw_and_curated_to_gcs(
        url="https://suumo.jp/chintai/soba/tokyo/area/",
        html_content=SAMPLE_SUUMO_HTML,
        source_id="suumo_soba",
        prefecture="東京都",
    )
    assert arc["manifest_key"] == "rag/manifest/rent_mesh_sources.jsonl"


