# ruff: noqa: E402
import os
import sys
import asyncio
from pathlib import Path
import django

# Django初期化
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
import realestateSettings
realestateSettings.configure()
django.setup()

from package.api.mitsui import ParseMitsuiMansionDetailFuncAsync
from package.models.mitsui import MitsuiMansion
from package.models.evaluation import PropertyPriceHistory
from package.api.differential import ListItem, filter_differential_items


async def run_verification():
    print("=" * 60)
    print("【実クロール & 差分・価格履歴動作検証開始】")
    print("=" * 60)

    # 1. 最新の公開中実物件URLを一覧ページから動的取得
    import urllib.parse
    import aiohttp
    from bs4 import BeautifulSoup
    list_url = "https://www.rehouse.co.jp/buy/mansion/prefecture/13/city/13101/"
    test_url = None
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    }
    print(f"1. 公開中アクティブ物件を動的取得中: {list_url}")
    async with aiohttp.ClientSession(headers=headers) as s:
        async with s.get(list_url) as resp:
            if resp.status == 200:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "/buy/mansion/bkdetail/" in href:
                        test_url = urllib.parse.urljoin("https://www.rehouse.co.jp", href)
                        break
    if not test_url:
        existing_sample = MitsuiMansion.objects.filter(pageUrl__contains="/buy/mansion/").order_by("-id").first()
        test_url = existing_sample.pageUrl if existing_sample else "https://www.rehouse.co.jp/buy/mansion/bkdetail/F21X2A03/"

    print(f"   検証対象URL決定: {test_url}")

    # 2. 実クロール実行（ParseMitsuiMansionDetailFuncAsync）
    print("\n2. 実クロール実行中 (HTTPフェッチ & パース & DB保存)...")
    detail_api = ParseMitsuiMansionDetailFuncAsync()
    detail_api.url = test_url

    saved_item = await detail_api._run(test_url)

    assert saved_item is not None, f"実クロール失敗: {test_url} から物件情報をパースできませんでした。"
    print(f"   [SUCCESS] 実クロール成功! 物件名: {saved_item.propertyName}, 価格: {saved_item.price}円")

    # DBレコードの確認
    db_record = MitsuiMansion.objects.filter(pageUrl=test_url).order_by("-id").first()
    assert db_record is not None, f"DBレコードが見つかりません: {test_url}"
    assert db_record.updateDateTime is not None, "updateDateTime が設定されていません!"
    orig_id = db_record.id
    orig_price = db_record.price
    orig_update_dt = db_record.updateDateTime
    print(f"   [DB検証] ID: {orig_id}, inputDateTime: {db_record.inputDateTime}, updateDateTime: {orig_update_dt}")

    # 3. 差分クロール判定の検証 (filter_differential_items)
    print("\n3. 差分クロール判定 (スキップ動作) の検証...")
    items = [ListItem(url=test_url, price=orig_price)]
    to_fetch, skipped = await filter_differential_items(
        items=items,
        model_class=MitsuiMansion,
        ttl_days=7,
        force_full=False,
        enabled=True,
    )
    print(f"   判定結果: to_fetch={len(to_fetch)}件, skipped={len(skipped)}件")
    assert len(to_fetch) == 0, f"差分クロールでスキップされるべきURLがフェッチ対象になっています: {to_fetch}"
    assert len(skipped) == 1, "同一価格・TTL以内の物件がスキップされていません!"
    print("   [SUCCESS] 同一価格・直近更新物件の不要フェッチスキップ（差分クロール）正常動作!")

    # 4. 価格改定時の1物件1レコードマスタ更新 & 価格履歴記録の検証
    print("\n4. 価格改定シミュレーション (マスタ更新 & PropertyPriceHistory自動記録)...")
    # DBの価格を一時的に書き換えて「価格改定が発生した」状態を作成
    dummy_old_price = (orig_price - 2000000) if (orig_price and orig_price > 2000000) else 50000000
    MitsuiMansion.objects.filter(id=orig_id).update(price=dummy_old_price)
    
    # 差分判定でフェッチ対象になることを確認
    to_fetch_revised, _ = await filter_differential_items(
        items=items,
        model_class=MitsuiMansion,
        ttl_days=7,
        force_full=False,
        enabled=True,
    )
    assert len(to_fetch_revised) == 1, "価格改定された物件が差分フェッチ対象になっていません!"
    print("   [SUCCESS] 価格変動検知 ➔ 差分フェッチ対象として正常抽出!")

    # 再度クロール実行（Detailパース & 保存）
    await detail_api._run(test_url)

    # 事後検証
    db_record_after = MitsuiMansion.objects.filter(id=orig_id).first()
    assert db_record_after is not None, "既存レコードが削除されています!"
    assert db_record_after.id == orig_id, "主キー（ID）が変更されています（新規挿入されてしまっている）!"
    assert db_record_after.price == orig_price, f"価格が最新値に更新されていません: {db_record_after.price} != {orig_price}"
    assert db_record_after.updateDateTime >= orig_update_dt, "updateDateTime が更新されていません!"
    print(f"   [マスタ更新検証] ID不変: {db_record_after.id}, 価格更新: {dummy_old_price} -> {db_record_after.price}, updateDateTime更新済")

    # PropertyPriceHistory の検証
    price_hist_after = PropertyPriceHistory.objects.filter(property_url=test_url).order_by("-recorded_at").first()
    assert price_hist_after is not None, "PropertyPriceHistory に価格履歴が作成されていません!"
    assert price_hist_after.old_price == dummy_old_price, f"old_price 不一致: {price_hist_after.old_price} != {dummy_old_price}"
    assert price_hist_after.new_price == orig_price, f"new_price 不一致: {price_hist_after.new_price} != {orig_price}"
    print(f"   [価格履歴検証] PropertyPriceHistory 記録成功! 改定履歴: {price_hist_after.old_price} -> {price_hist_after.new_price} (差分: {price_hist_after.price_diff:+d})")

    # 重複URLが作られていないことの確認
    dup_count = MitsuiMansion.objects.filter(pageUrl=test_url).count()
    assert dup_count == 1, f"重複レコードが作成されています! 件数: {dup_count}"
    print(f"   [重複防止検証] DB上のレコード件数: {dup_count}件（1物件1レコードを完全に維持）")

    print("\n" + "=" * 60)
    print("★★★ 【全検証成功】実クロール・差分スキップ・マスタ上書き・価格履歴記録が100%正常動作 ★★★")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_verification())
