# -*- coding: utf-8 -*-
"""
過去データ移行における価格単位（万円→円）および階数属性欠落の補正スクリプト (Issue #235)

対象:
- real_estate DB 内の 7 テーブル
  - sumifu_mansion, sumifu_kodate, sumifu_tochi
  - mitsui_mansion, mitsui_kodate, mitsui_tochi
  - tokyu_mansion
"""
import os
import argparse
import logging
import MySQLdb

TABLE_MAPPINGS = [
    ('sumifu_mansion_lst', 'sumifu_mansion'),
    ('sumifu_kodate_lst', 'sumifu_kodate'),
    ('sumifu_tochi_lst', 'sumifu_tochi'),
    ('mitsui_mansion_lst', 'mitsui_mansion'),
    ('mitsui_kodate_lst', 'mitsui_kodate'),
    ('mitsui_tochi_lst', 'mitsui_tochi'),
    ('tokyu_mansion_lst', 'tokyu_mansion'),
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def get_db_connection():
    return MySQLdb.connect(
        host=os.getenv('DB_HOST', 'db'),
        user=os.getenv('MYSQL_USER', 'root'),
        passwd=os.getenv('MYSQL_ROOT_PASSWORD', 'rootpassword'),
        port=int(os.getenv('DB_PORT', '3306')),
        charset='utf8mb4'
    )

KAISU_STR_CLAUSE = (
    "c.kaisuStr = CASE WHEN (c.kaisuStr IS NULL OR c.kaisuStr = '') "
    "AND l.kaisu IS NOT NULL THEN l.kaisu ELSE c.kaisuStr END"
)

DEFAULT_SQL_OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "Temp",
    "cloud_sql_correction.sql"
)

UPDATE_REAL_ESTATE_PREFIX = "UPDATE real_estate."

def _get_mansion_set_clauses(current_t: str) -> list:
    if 'sumifu' in current_t:
        return [
            "c.kaisu = COALESCE(NULLIF(l.floorType_kai, 0), c.kaisu)",
            "c.kaisuKouzou = CASE WHEN (c.kaisuKouzou IS NULL OR c.kaisuKouzou = '') AND l.floorType IS NOT NULL THEN l.floorType ELSE c.kaisuKouzou END",
        ]
    if 'mitsui' in current_t:
        return [
            KAISU_STR_CLAUSE,
        ]
    if 'tokyu' in current_t:
        return [
            "c.kaisu = COALESCE(NULLIF(l.floorType_kai, 0), CASE WHEN l.kaisu REGEXP '\d+' THEN CAST(REGEXP_SUBSTR(l.kaisu, '\d+') AS SIGNED) ELSE c.kaisu END)",
            KAISU_STR_CLAUSE,
            "c.tatemonoKaisu = CASE WHEN (c.tatemonoKaisu IS NULL OR c.tatemonoKaisu = '') AND l.floorType_chijo > 0 THEN CAST(l.floorType_chijo AS CHAR) ELSE c.tatemonoKaisu END",
        ]
    return []

def _get_kodate_set_clauses(current_t: str) -> list:
    if 'sumifu' in current_t:
        return [
            "c.kaisu = CASE WHEN c.kaisu IS NULL AND l.kaisu REGEXP '\d+' THEN CAST(REGEXP_SUBSTR(l.kaisu, '\d+') AS SIGNED) ELSE c.kaisu END",
        ]
    if 'mitsui' in current_t:
        return [
            KAISU_STR_CLAUSE,
            "c.kenpeiStr = CASE WHEN (c.kenpeiStr IS NULL OR c.kenpeiStr = '') AND l.kenpei IS NOT NULL THEN CONCAT(l.kenpei, '%') ELSE c.kenpeiStr END",
            "c.yousekiStr = CASE WHEN (c.yousekiStr IS NULL OR c.yousekiStr = '') AND l.youseki IS NOT NULL THEN CONCAT(l.youseki, '%') ELSE c.yousekiStr END",
        ]
    return []

def _get_tochi_set_clauses(current_t: str) -> list:
    if 'mitsui' in current_t:
        return [
            "c.kenpeiStr = CASE WHEN (c.kenpeiStr IS NULL OR c.kenpeiStr = '') AND l.kenpei IS NOT NULL THEN CONCAT(l.kenpei, '%') ELSE c.kenpeiStr END",
            "c.yousekiStr = CASE WHEN (c.yousekiStr IS NULL OR c.yousekiStr = '') AND l.youseki IS NOT NULL THEN CONCAT(l.youseki, '%') ELSE c.yousekiStr END",
        ]
    return []

def _get_attribute_set_clauses(current_t: str) -> list:
    if 'mansion' in current_t:
        return _get_mansion_set_clauses(current_t)
    if 'kodate' in current_t:
        return _get_kodate_set_clauses(current_t)
    if 'tochi' in current_t:
        return _get_tochi_set_clauses(current_t)
    return []

def _build_table_statements(legacy_t: str, current_t: str) -> list:
    stmts = [
        "-- ========================================================",
        f"-- Correcting {current_t} from {legacy_t}",
        "-- ========================================================",
        f"""{UPDATE_REAL_ESTATE_PREFIX}{current_t} c
INNER JOIN real_estate_legacy.{legacy_t} l ON c.pageUrl = l.pageUrl COLLATE utf8mb4_unicode_ci
SET c.price = CAST(l.price AS SIGNED) * 10000
WHERE c.price < 100000 AND c.price > 0 AND l.price > 0;
"""
    ]
    set_clauses = _get_attribute_set_clauses(current_t)
    if set_clauses:
        set_str = ",\n    ".join(set_clauses)
        stmts.append(f"""{UPDATE_REAL_ESTATE_PREFIX}{current_t} c
INNER JOIN real_estate_legacy.{legacy_t} l ON c.pageUrl = l.pageUrl COLLATE utf8mb4_unicode_ci
SET 
    {set_str};
""")
    return stmts

def generate_update_sql_statements():
    """Cloud SQL等で一括実行可能な補正SQL文のリストを生成する"""
    statements = [
        "SET NAMES utf8mb4;",
        "SET SQL_SAFE_UPDATES = 0;\n"
    ]
    for legacy_t, current_t in TABLE_MAPPINGS:
        statements.extend(_build_table_statements(legacy_t, current_t))
    statements.append("SET SQL_SAFE_UPDATES = 1;\n")
    return "\n".join(statements)

def _correct_table(cur, legacy_t: str, current_t: str, is_execute: bool) -> int:
    cur.execute(f"""
        SELECT COUNT(*) as cnt
        FROM real_estate.{current_t} c
        INNER JOIN real_estate_legacy.{legacy_t} l ON c.pageUrl = l.pageUrl COLLATE utf8mb4_unicode_ci
        WHERE c.price < 100000 AND c.price > 0 AND l.price > 0
    """)
    price_cnt = cur.fetchone()['cnt']
    logging.info(f"  [{current_t}] Prices needing x10000 correction: {price_cnt}")

    if not is_execute:
        return 0

    updated_count = 0
    if price_cnt > 0:
        cur.execute(f"""
            {UPDATE_REAL_ESTATE_PREFIX}{current_t} c
            INNER JOIN real_estate_legacy.{legacy_t} l ON c.pageUrl = l.pageUrl COLLATE utf8mb4_unicode_ci
            SET c.price = CAST(l.price AS SIGNED) * 10000
            WHERE c.price < 100000 AND c.price > 0 AND l.price > 0
        """)
        logging.info(f"  [{current_t}] Updated {cur.rowcount} prices to Yen units.")
        updated_count = cur.rowcount

    set_clauses = _get_attribute_set_clauses(current_t)
    if set_clauses:
        set_str = ",\n    ".join(set_clauses)
        cur.execute(f"""
            {UPDATE_REAL_ESTATE_PREFIX}{current_t} c
            INNER JOIN real_estate_legacy.{legacy_t} l ON c.pageUrl = l.pageUrl COLLATE utf8mb4_unicode_ci
            SET 
                {set_str}
        """)
    return updated_count

def main():
    parser = argparse.ArgumentParser(description="Fix migrated legacy property prices and attributes.")
    parser.add_argument("--execute", action="store_true", help="Execute the update on the database.")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run: show what would be updated without committing.")
    parser.add_argument("--generate-sql", action="store_true", help="Output SQL script to Temp/cloud_sql_correction.sql.")
    args = parser.parse_args()

    if args.generate_sql:
        sql_content = generate_update_sql_statements()
        os.makedirs(os.path.dirname(DEFAULT_SQL_OUTPUT), exist_ok=True)
        with open(DEFAULT_SQL_OUTPUT, "w", encoding="utf-8") as f:
            f.write(sql_content)
        logging.info(f"Generated correction SQL to: {DEFAULT_SQL_OUTPUT}")
        if not args.execute and not args.dry_run:
            return

    if not args.execute and not args.dry_run:
        logging.info("Please specify --execute or --dry-run (or --generate-sql).")
        return

    conn = get_db_connection()
    cur = conn.cursor(MySQLdb.cursors.DictCursor)
    logging.info(f"Mode: {'EXECUTE' if args.execute else 'DRY-RUN'}")

    total_price_updated = 0
    for legacy_t, current_t in TABLE_MAPPINGS:
        logging.info(f"Auditing {current_t}...")
        total_price_updated += _correct_table(cur, legacy_t, current_t, args.execute)

    if args.execute:
        conn.commit()
        logging.info(f"COMMIT completed! Total price records corrected: {total_price_updated}")
    else:
        logging.info("DRY-RUN completed. No changes were committed.")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
