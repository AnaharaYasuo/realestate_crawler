"""
三井ヘッダー行ゴミおよび健美家用語解説上書きレコードの UPDATE 復旧スクリプト (Issue #917)
レコードの削除 (DELETE) は一切行わず、既存レコードを保持したまま UPDATE によりデータを正常化・復旧します。
本番DBへのローカル直接更新は assert_production_db_safety により確実に遮断されます。
"""
import argparse
import asyncio
import logging
import re
import sys

import setup_env  # noqa: F401
from django.apps import apps
from django.db import transaction
from django.db.models import Q
from package.models.mitsui import MitsuiMansion, MitsuiTochi
from package.models.nomura import NomuraKodate
from package.utils.db_safety import assert_production_db_safety
from scripts.maintenance.recrawl_anomalies import recrawl_anomalies_async

logger = logging.getLogger(__name__)

# 健美家 東京都50市区町村スラッグマッピング
KENBIYA_TOKYO_CITIES = {
    "adachi-ku": "足立区",
    "akiruno-shi": "あきる野市",
    "akishima-shi": "昭島市",
    "arakawa-ku": "荒川区",
    "bunkyo-ku": "文京区",
    "chiyoda-ku": "千代田区",
    "chofu-shi": "調布市",
    "chuo-ku": "中央区",
    "edogawa-ku": "江戸川区",
    "etc": "",
    "fuchu-shi": "府中市",
    "fussa-shi": "福生市",
    "hachioji-shi": "八王子市",
    "hamura-shi": "羽村市",
    "higashikurume-shi": "東久留米市",
    "higashimurayama-shi": "東村山市",
    "higashiyamato-shi": "東大和市",
    "hino-shi": "日野市",
    "inagi-shi": "稲城市",
    "itabashi-ku": "板橋区",
    "katsushika-ku": "葛飾区",
    "kita-ku": "北区",
    "kiyose-shi": "清瀬市",
    "kodaira-shi": "小平市",
    "koganei-shi": "小金井市",
    "kokubunji-shi": "国分寺市",
    "komae-shi": "狛江市",
    "koto-ku": "江東区",
    "kunitachi-shi": "国立市",
    "machida-shi": "町田市",
    "meguro-ku": "目黒区",
    "minato-ku": "港区",
    "mitaka-shi": "三鷹市",
    "musashimurayama-shi": "武蔵村山市",
    "musashino-shi": "武蔵野市",
    "nakano-ku": "中野区",
    "nerima-ku": "練馬区",
    "nishitokyo-shi": "西東京市",
    "ome-shi": "青梅市",
    "ota-ku": "大田区",
    "setagaya-ku": "世田谷区",
    "shibuya-ku": "渋谷区",
    "shinagawa-ku": "品川区",
    "shinjuku-ku": "新宿区",
    "suginami-ku": "杉並区",
    "sumida-ku": "墨田区",
    "tachikawa-shi": "立川市",
    "taito-ku": "台東区",
    "tama-shi": "多摩市",
    "toshima-ku": "豊島区",
}

# 三井ラベル文字列クリア対象辞書
MITSUI_LABEL_CLEAR_FIELDS = {
    "priceStr": {"価格", "販売価格", "物件価格", "価格（非課税）", "価格(非課税)"},
    "address": {"所在地", "住所", "物件所在地"},
    "madori": {"間取り", "間取"},
    "senyuMensekiStr": {"専有面積"},
    "tochiMensekiStr": {"土地面積"},
    "hikiwatashi": {"引渡時期", "引渡し", "引渡"},
    "genkyo": {"現況"},
    "tochikenri": {"土地権利", "権利"},
    "torihiki": {"取引態様"},
    "biko": {"備考"},
    "kaisuStr": {"階数 / 階建", "階数", "所在階"},
    "balconyMensekiStr": {"バルコニー", "バルコニー面積"},
    "soukosuStr": {"総戸数"},
    "kanriKeitai": {"管理形態"},
    "kanriKaisya": {"管理会社"},
    "kanrihiStr": {"管理費等", "管理費"},
    "syuzenTsumitateStr": {"修繕積立金"},
    "tyusyajo": {"駐車場"},
    "sonotaHiyouStr": {"その他費用"},
    "bunjoKaisya": {"分譲会社"},
    "sekouKaisya": {"施工会社"},
}

MADORI_REGEX = re.compile(r"([1-9]\d{0,1}[SLDKR]+(?:\+[1-9]?[SLDKR]+)?)", re.IGNORECASE)


def extract_kenbiya_address_from_url(url: str) -> tuple[str, str, str]:
    """健美家URLから都道府県・市区町村・結合住所を抽出"""
    m = re.search(r"/s/([^/]+)/([^/]+)/", url or "")
    if not m:
        return ("", "", "")
    pref_slug, city_slug = m.group(1), m.group(2)
    pref = "東京都" if pref_slug == "tokyo" else ""
    city = KENBIYA_TOKYO_CITIES.get(city_slug, "")
    full_address = f"{pref}{city}" if (pref and city) else pref
    return (pref, city, full_address)


def normalize_mitsui_garbage_record(item) -> list[str]:
    """三井レコードでラベル名そのものが入っているカラムをクリアし、更新対象フィールド名を返却"""
    changed = []
    for field_name, bad_values in MITSUI_LABEL_CLEAR_FIELDS.items():
        if hasattr(item, field_name):
            val = getattr(item, field_name, None)
            if isinstance(val, str) and val.strip() in bad_values:
                setattr(item, field_name, "")
                changed.append(field_name)

    # 数値フィールドの補正 (price は NOT NULL のため 0 を維持し、None にしない)
    if "senyuMensekiStr" in changed and hasattr(item, "senyuMenseki") and item.senyuMenseki == 0:
        item.senyuMenseki = None
        changed.append("senyuMenseki")
    if "address" in changed:
        if hasattr(item, "address1") and item.address1 in {"所在地", "住所"}:
            item.address1 = ""
            changed.append("address1")
        if hasattr(item, "address2") and item.address2 in {"所在地", "住所"}:
            item.address2 = ""
            changed.append("address2")
        if hasattr(item, "address3") and item.address3 in {"所在地", "住所"}:
            item.address3 = ""
            changed.append("address3")

    return list(set(changed))


def extract_nomura_madori(property_name: str, biko: str) -> str:
    """物件名や備考から間取りを正規表現抽出"""
    text = f"{property_name or ''} {biko or ''}"
    match = MADORI_REGEX.search(text)
    return match.group(1).upper() if match else ""


def restore_kenbiya_records(dry_run: bool = True, batch_size: int = 500) -> dict[str, int]:
    """健美家の用語解説上書きレコードを URL から住所復元＆用語解説文クリアで UPDATE"""
    results = {}
    kenbiya_models = [m for m in apps.get_models() if "kenbiya" in m.__name__.lower()]

    for model in kenbiya_models:
        model_name = model.__name__
        fields = {f.name for f in model._meta.fields}
        if "address" not in fields or "pageUrl" not in fields:
            continue

        qs = model.objects.filter(address__icontains="を表示")
        total_count = qs.count()
        results[model_name] = total_count

        if dry_run or total_count == 0:
            logger.info(f"[DRY-RUN] {model_name}: {total_count} 件の住所復旧・用語解説クリア UPDATE 対象")
            continue

        logger.info(f"[EXECUTE] {model_name}: {total_count} 件を UPDATE 復旧中...")
        updated_count = 0
        batch = []

        update_field_names = {"address"}
        if "address1" in fields:
            update_field_names.add("address1")
        if "address2" in fields:
            update_field_names.add("address2")
        if "propertyName" in fields:
            update_field_names.add("propertyName")
        if "priceStr" in fields:
            update_field_names.add("priceStr")

        for item in qs.iterator(chunk_size=batch_size):
            pref, city, full = extract_kenbiya_address_from_url(item.pageUrl)
            if full:
                item.address = full
                if "address1" in fields:
                    item.address1 = pref
                if "address2" in fields:
                    item.address2 = city
            else:
                item.address = ""

            # 用語解説文のクリア
            if "propertyName" in fields and "を表示" in (item.propertyName or ""):
                item.propertyName = ""
            if "priceStr" in fields and "を表示" in (item.priceStr or ""):
                item.priceStr = ""

            batch.append(item)
            if len(batch) >= batch_size:
                with transaction.atomic():
                    model.objects.bulk_update(batch, list(update_field_names))
                updated_count += len(batch)
                batch = []

        if batch:
            with transaction.atomic():
                model.objects.bulk_update(batch, list(update_field_names))
            updated_count += len(batch)

        logger.info(f"[EXECUTE] {model_name}: 完了 ({updated_count} 件 UPDATE)")

    return results


def restore_mitsui_records(dry_run: bool = True, batch_size: int = 500) -> dict[str, int]:
    """三井のヘッダー文字列誤登録レコードをラベルクリア＆数値正常化で UPDATE"""
    results = {}
    for model in [MitsuiMansion, MitsuiTochi]:
        model_name = model.__name__
        q_filter = Q(priceStr__in=["価格", "販売価格", "物件価格", "価格（非課税）", "価格(非課税)"]) | Q(
            address__in=["所在地", "住所", "物件所在地"]
        )
        qs = model.objects.filter(q_filter)
        total_count = qs.count()
        results[model_name] = total_count

        if dry_run or total_count == 0:
            logger.info(f"[DRY-RUN] {model_name}: {total_count} 件のラベル文字クリア UPDATE 対象")
            continue

        logger.info(f"[EXECUTE] {model_name}: {total_count} 件を UPDATE 正常化中...")
        updated_count = 0
        batch = []
        all_changed_fields = set()

        for item in qs.iterator(chunk_size=batch_size):
            changed = normalize_mitsui_garbage_record(item)
            all_changed_fields.update(changed)
            batch.append(item)

            if len(batch) >= batch_size:
                with transaction.atomic():
                    model.objects.bulk_update(batch, list(all_changed_fields))
                updated_count += len(batch)
                batch = []

        if batch:
            with transaction.atomic():
                model.objects.bulk_update(batch, list(all_changed_fields))
            updated_count += len(batch)

        logger.info(f"[EXECUTE] {model_name}: 完了 ({updated_count} 件 UPDATE)")

    return results


def restore_nomura_kodate_records(
    dry_run: bool = True, batch_size: int = 500, recrawl_detail: bool = False, limit: int | None = None
) -> dict[str, int]:
    """野村戸建ての間取り未取得レコードを直接詳細巡回または物件名・備考から復旧"""
    qs = NomuraKodate.objects.filter(madori="")
    total_count = qs.count()
    results = {"NomuraKodate_missing_madori": total_count}

    if recrawl_detail:
        # ユーザー要求: 対象物件のURLがわかるため直接詳細ページを開き、公開終了なら公開終了としてDB保存
        logger.info(
            f"[RECRAWL-DETAIL] NomuraKodate: {total_count} 件のURLへ直接アクセスしてパースまたは公開終了反映 (DryRun={dry_run}, limit={limit})"
        )
        total_targets, stats = asyncio.run(
            recrawl_anomalies_async(
                model_name="NomuraKodate",
                field_empty="madori",
                limit=limit,
                dry_run=dry_run,
            )
        )
        results["NomuraKodate_recrawl_targets"] = total_targets
        for k, v in stats.items():
            results[f"NomuraKodate_recrawl_{k}"] = v
        return results

    if dry_run:
        extractable = 0
        for item in qs.iterator(chunk_size=batch_size):
            if extract_nomura_madori(item.propertyName, item.biko):
                extractable += 1
        results["NomuraKodate_extractable_madori"] = extractable
        logger.info(f"[DRY-RUN] NomuraKodate: {total_count} 件中 {extractable} 件が間取り補完 UPDATE 対象")
        return results

    logger.info("[EXECUTE] NomuraKodate: 間取り補完 UPDATE 中...")
    batch = []
    updated_count = 0
    for item in qs.iterator(chunk_size=batch_size):
        madori = extract_nomura_madori(item.propertyName, item.biko)
        if madori:
            item.madori = madori
            batch.append(item)
        if len(batch) >= batch_size:
            with transaction.atomic():
                NomuraKodate.objects.bulk_update(batch, ["madori"])
            updated_count += len(batch)
            batch = []

    if batch:
        with transaction.atomic():
            NomuraKodate.objects.bulk_update(batch, ["madori"])
        updated_count += len(batch)

    results["NomuraKodate_updated_madori"] = updated_count
    logger.info(f"[EXECUTE] NomuraKodate: 完了 ({updated_count} 件間取り UPDATE)")
    return results


def update_and_restore_records(
    dry_run: bool = True,
    target: str = "all",
    batch_size: int = 500,
    recrawl_detail: bool = False,
    limit: int | None = None,
) -> dict[str, int]:
    """全対象モデルのレコードを削除せず UPDATE により復旧・正常化"""
    if not dry_run:
        assert_production_db_safety("update_and_restore_records")

    summary = {}
    if target in ("all", "kenbiya"):
        summary.update(restore_kenbiya_records(dry_run=dry_run, batch_size=batch_size))
    if target in ("all", "mitsui"):
        summary.update(restore_mitsui_records(dry_run=dry_run, batch_size=batch_size))
    if target in ("all", "nomura"):
        summary.update(
            restore_nomura_kodate_records(
                dry_run=dry_run, batch_size=batch_size, recrawl_detail=recrawl_detail, limit=limit
            )
        )

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="三井ヘッダー行ゴミおよび健美家・野村レコードの UPDATE 復旧スクリプト (Issue #917)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="実UPDATEを実行する（指定しない場合はDry-runで確認のみ）",
    )
    parser.add_argument(
        "--target",
        choices=["all", "mitsui", "kenbiya", "nomura"],
        default="all",
        help="対象を指定 (all/mitsui/kenbiya/nomura)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="更新時のチャンクサイズ (デフォルト: 500)",
    )
    parser.add_argument(
        "--recrawl-detail",
        action="store_true",
        help="直接詳細ページを開いて最新化および公開終了反映を行う",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="直接詳細巡回の対象件数上限",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    mode_str = "実UPDATE実行モード (--execute)" if args.execute else "ドライラン (確認のみ)"
    logger.info(f"=== UPDATE復旧バッチ開始: {mode_str}, target={args.target}, recrawl_detail={args.recrawl_detail} ===")

    try:
        results = update_and_restore_records(
            dry_run=not args.execute,
            target=args.target,
            batch_size=args.batch_size,
            recrawl_detail=args.recrawl_detail,
            limit=args.limit,
        )
    except Exception:
        logger.exception("UPDATE復旧失敗")
        sys.exit(1)

    logger.info("=== UPDATE復旧 集計結果 ===")
    for name, cnt in results.items():
        logger.info(f"  {name}: {cnt} 件")

    if not args.execute:
        logger.info("※ 実UPDATEを行うには `--execute` オプションを付与して再実行してください。")


if __name__ == "__main__":
    main()
