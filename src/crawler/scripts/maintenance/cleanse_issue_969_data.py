import argparse
import logging
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
import realestateSettings

realestateSettings.configure()
from django.db import connection, transaction

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_cleansing(dry_run: bool = False):
    logger.info("Starting relocation and cleansing of misclassified properties (dry_run=%s)...", dry_run)

    with connection.cursor() as cur:
        # 一時テーブルを用いて対象IDを一度だけ確定し、一貫性を保証
        cur.execute(
            """
            CREATE TEMPORARY TABLE IF NOT EXISTS tmp_misclassified_homes_invest (
                id INT PRIMARY KEY,
                pageUrl VARCHAR(500)
            );
            """
        )
        cur.execute("TRUNCATE TABLE tmp_misclassified_homes_invest;")

        cur.execute(
            """
            INSERT INTO tmp_misclassified_homes_invest (id, pageUrl)
            SELECT id, pageUrl
            FROM homes_investment_apartment
            WHERE propertyType = 'Mansion'
               OR tatemonoMensekiStr LIKE '%専有%'
               OR tatemonoMensekiStr LIKE '%バルコニー%';
            """
        )
        cur.execute("SELECT COUNT(*) FROM tmp_misclassified_homes_invest;")
        target_count = cur.fetchone()[0]
        logger.info("Found %d misclassified records in temporary table.", target_count)

        if target_count == 0:
            logger.info("No records to relocate.")
            return

        if dry_run:
            logger.info("[DRY RUN] Would insert %d records into homes_mansion, update property_evaluation, and delete from homes_investment_apartment.", target_count)
            return

        with transaction.atomic():
            # 1. homes_mansion へ未登録のものを INSERT 移送
            insert_query = """
            INSERT INTO homes_mansion (
                propertyName, pageUrl, inputDate, inputDateTime, updateDateTime, priceStr, price,
                address, traffic, chidaiStr, chidai,
                transfer1, railway1, station1, railwayWalkMinute1Str, railwayWalkMinute1,
                busStation1, busWalkMinute1Str, busWalkMinute1,
                transfer2, railway2, station2, railwayWalkMinute2Str, railwayWalkMinute2,
                busStation2, busWalkMinute2Str, busWalkMinute2,
                transfer3, railway3, station3, railwayWalkMinute3Str, railwayWalkMinute3,
                busStation3, busWalkMinute3Str, busWalkMinute3,
                transfer4, railway4, station4, railwayWalkMinute4Str, railwayWalkMinute4,
                busStation4, busWalkMinute4Str, busWalkMinute4,
                transfer5, railway5, station5, railwayWalkMinute5Str, railwayWalkMinute5,
                busStation5, busWalkMinute5Str, busWalkMinute5,
                railwayCount, busUse1, busUse2, busUse3, busUse4, busUse5,
                hikiwatashi, genkyo, tochikenri, biko,
                madori, senyuMensekiStr, senyuMenseki,
                kaisuStr, chikunengetsuStr, chikunengetsu, balconyMensekiStr,
                saikou, soukosuStr, soukosu, kanriKeitai, kanriKaisya,
                kanrihiStr, kanrihi, syuzenTsumitateStr, syuzenTsumitate, tyusyajo, kouzou
            )
            SELECT
                h.propertyName, h.pageUrl, h.inputDate, h.inputDateTime, h.updateDateTime, h.priceStr, h.price,
                h.address, h.traffic, h.chidaiStr, h.chidai,
                h.transfer1, h.railway1, h.station1, h.railwayWalkMinute1Str, h.railwayWalkMinute1,
                h.busStation1, h.busWalkMinute1Str, h.busWalkMinute1,
                h.transfer2, h.railway2, h.station2, h.railwayWalkMinute2Str, h.railwayWalkMinute2,
                h.busStation2, h.busWalkMinute2Str, h.busWalkMinute2,
                h.transfer3, h.railway3, h.station3, h.railwayWalkMinute3Str, h.railwayWalkMinute3,
                h.busStation3, h.busWalkMinute3Str, h.busWalkMinute3,
                h.transfer4, h.railway4, h.station4, h.railwayWalkMinute4Str, h.railwayWalkMinute4,
                h.busStation4, h.busWalkMinute4Str, h.busWalkMinute4,
                h.transfer5, h.railway5, h.station5, h.railwayWalkMinute5Str, h.railwayWalkMinute5,
                h.busStation5, h.busWalkMinute5Str, h.busWalkMinute5,
                h.railwayCount, h.busUse1, h.busUse2, h.busUse3, h.busUse4, h.busUse5,
                h.hikiwatashi, h.genkyo, h.tochikenri, h.biko,
                '' AS madori,
                COALESCE(h.tatemonoMensekiStr, '') AS senyuMensekiStr,
                h.tatemonoMenseki AS senyuMenseki,
                COALESCE(h.kaisuStr, '') AS kaisuStr,
                COALESCE(h.chikunengetsuStr, '') AS chikunengetsuStr,
                NULL AS chikunengetsu,
                '' AS balconyMensekiStr,
                '' AS saikou,
                COALESCE(h.soukosuStr, '') AS soukosuStr,
                h.soukosu,
                '' AS kanriKeitai,
                '' AS kanriKaisya,
                '' AS kanrihiStr,
                NULL AS kanrihi,
                '' AS syuzenTsumitateStr,
                NULL AS syuzenTsumitate,
                '' AS tyusyajo,
                COALESCE(h.kouzou, '') AS kouzou
            FROM homes_investment_apartment h
            JOIN tmp_misclassified_homes_invest t ON h.id = t.id
            LEFT JOIN homes_mansion m ON h.pageUrl = m.pageUrl
            WHERE m.id IS NULL;
            """
            cur.execute(insert_query)
            logger.info("Inserted %d records into homes_mansion.", cur.rowcount)

            # 2. property_evaluation の紐付け更新
            update_pe_query = """
            UPDATE property_evaluation pe
            JOIN tmp_misclassified_homes_invest t ON pe.property_url = t.pageUrl AND pe.company = 'homes'
            JOIN homes_mansion m ON pe.property_url = m.pageUrl
            SET pe.property_id = m.id,
                pe.property_type = 'mansion',
                pe.needs_recrawl = 1,
                pe.data_quality_issue = 'migrated_misclassified_unit_mansion',
                pe.first_stage_predicted_price = NULL,
                pe.second_stage_predicted_price = NULL,
                pe.is_first_stage_passed = 0;
            """
            cur.execute(update_pe_query)
            logger.info("Updated %d property_evaluation records to point to homes_mansion with needs_recrawl=1.", cur.rowcount)

            # 3. homes_investment_apartment から旧レコードを削除
            delete_query = """
            DELETE h
            FROM homes_investment_apartment h
            JOIN tmp_misclassified_homes_invest t ON h.id = t.id;
            """
            cur.execute(delete_query)
            logger.info("Deleted %d old records from homes_investment_apartment.", cur.rowcount)

        # 4. 価格0以下の破綻データに対する needs_recrawl フラグ設定（住友等）
        for table, ptype in [('sumifu_mansion', 'mansion'), ('sumifu_kodate', 'kodate'), ('sumifu_tochi', 'tochi')]:
            cur.execute(
                f"""
                UPDATE property_evaluation pe
                JOIN {table} s ON pe.property_id = s.id AND pe.company = 'sumifu' AND pe.property_type = '{ptype}'
                SET pe.needs_recrawl = 1, pe.data_quality_issue = 'invalid_price_zero'
                WHERE s.price <= 0;
                """
            )
            logger.info("Marked %s 0 price records as needs_recrawl: %d", table, cur.rowcount)

    logger.info("Cleansing and migration completed successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanse and migrate misclassified properties")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without modifying database")
    args = parser.parse_args()
    run_cleansing(dry_run=args.dry_run)
