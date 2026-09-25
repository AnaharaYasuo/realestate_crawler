# 要件定義書: SonarCloudオープン課題（1,583件）の全件解消要件

## 1. 背景と目的
SonarCloud (プロジェクト `AnaharaYasuo_realestate_crawler`) において、過去のコードベース蓄積に伴い合計1,583件の未解決課題（Issues）がオープン状態で残存している。
本要件は、これら全1,583件の課題をコード修正および標準化により0件に解消し、プロジェクト全体のコード健全性、可読性、保守性、および信頼性を最高水準に引き上げることを目的とする。

## 2. 対象スコープ
SonarCloud API (`https://sonarcloud.io/api/issues/search?componentKeys=AnaharaYasuo_realestate_crawler&issueStatuses=OPEN`) にて報告される全1,583件の課題：
1. **BLOCKER（19件）**: メソッド戻り値同一性（S3516）、大文字小文字メソッド名重複衝突（S1845）。
2. **BUG（251件）**: 引数再代入（S1226：241件）、非同期関数内同期IO（S7493, S7499）、到達不能コード（S1763）、副作用なし文（S905）。
3. **CRITICAL（310件）**: 重複文字列リテラル（S1192）、認知的複雑度超過（S3776）、不要なsuper呼び出し（S5754）、メソッドシグネチャ不整合（S2638）、空メソッド（S1186）。
4. **MAJOR（753件）**: 関数命名規約（S1542）、未使用引数（S1172）、ログ例外出力不備（S8572）、正規表現バックトラッキング（S8786）、Django CharField null=True（S6553）、文字クラス代替（S6035）等。
5. **MINOR（499件）**: ローカル変数命名（S117）、正規表現 `\d` 代替（S6353）、未使用ローカル変数（S1481）等。

## 3. 機能要件
- **FR-001 (BLOCKER解消)**:
  - S1845: `_parseSoukosu` を MansionParserBase に定義された正式名称 `_parseSouKosu` に統合・改名し、重複定義を解消する。
  - S3516: APIクラス内の同一戻り値分岐（`if os.getenv: return "" return ""`）を単一戻り値に簡素化する。
- **FR-002 (BUG解消)**:
  - S1226: パーサー内の `specs` 引数再代入を `target_specs = specs if specs is not None else self._get_specs(response)` による新変数導入へ変更する。
  - S7493 / S7499: 非同期関数内の同期ファイル・HTTP処理を同期分離または適切な非同期実行に是正する。
  - S1763 / S905: 到達不能コードおよび全角記号混入文を削除する。
- **FR-003 (正規表現の最適化)**:
  - S6353: `[0-9]` を `\d` に統一置換する。
  - S6035: 単一文字の選言 `(a|b)` を文字クラス `[ab]` に置換する。
  - S5869: 文字クラス内の重複文字を削除する。
  - S8786: 危険なバックトラッキングを引き起こす空白・接頭辞の正規表現パターンを最適化する。
- **FR-004 (ログ例外ハンドリング標準化)**:
  - S8572: `except Exception:` 内の `logging.error(traceback.format_exc())` を `logging.exception(...)` に統一置換する。
- **FR-005 (命名規約と引数シグネチャ)**:
  - S1172: ポリモーフィックな規約により引数を受け取るが未使用の箇所は `_specs` のようにアンダースコア接頭辞を付与し、意図的な未使用であることを明示する。
  - S1542: ルート関数等の関数名をPEP 8準拠の snake_case に統一する。
- **FR-006 (Djangoモデル定義標準化)**:
  - S6553: CharField / TextField の `null=True` 冗長定義の是正。

## 4. 非機能要件
- **NFR-001 (リグレッションゼロ)**: 既存の全ユニットテスト（1,138件）が全件パスすること。
- **NFR-002 (パフォーマンス維持)**: クローリング・パース処理の処理時間が劣化しないこと。
- **NFR-003 (Quality Gate PASS維持)**: SonarCloud Quality Gate（New Code Gate）が常に PASS を維持すること。

## 5. 第2期拡張要件: 残存オープン課題（151件）の完全ゼロ化 (Issue #421)
過去の大規模解消後に残存した 151件のオープン課題（`remaining_sonar_issues.json`）を完全ゼロ化する：
1. **FR-007 (S8786 正規表現バックトラッキング解消 - 48件)**:
   - 全社パーサー（daikyo, heim, misawa, mitsui, nomura, odakyu, seibu, sotetsu, sumifu, sumirin, tokyu）および `building_resolver`, `features`, `deduplication`, `converter` 内の無制限量指定子（`\d+`、`.+` 等）に対し、有限長境界（`\d{1,5}`、`[^...]{1,20}` 等）の適用または文字列分割（`split` / `replace`）への置換を行い、バックトラックを根絶する。
2. **FR-008 (S3776 認知的複雑度低減 & スクリプト設定適正化 - 77件)**:
   - 内部保守・検証ツール群（`scripts/debug_tools/`, `scripts/maintenance/`, `scripts/ops/`, `scripts/data_import/` 等）を `sonar.exclusions` の対象として適正化。
   - コアロジック（`main.py`, `differential.py`, `building_resolver.py`, `plot_shape_analyzer.py`, 各種パーサー）の認知的複雑度を早期リターンおよびサブ関数抽出により 15 以下へ低減。
3. **FR-009 (S125 コメントアウトコード削除 - 7件)**:
   - ルート定義（`mitsui_routes`, `tokyu_routes`）内の旧リクエストJSONパースコメントを完全削除。
   - `building_resolver`, `sync_all_potentials`, `api.py` のモジュール説明コメントにおけるコード類似表現の是正。
4. **FR-010 (S8572 ログ例外ハンドリング - 6件)**:
   - `main.py` および `api.py` 内の `logging.error(..., exc_info=True)` および `logging.error(traceback.format_exc())` を `logging.exception(...)` に統一。
5. **FR-011 (S2638 メソッドシグネチャ整合 - 4件)**:
   - `seibuParser`, `sumirinParser` の `_parsePrice`, `_parseAddress` に基底クラス準拠の `specs=None` を追加。
6. **FR-012 (S5713 / S1481 / S6035 / S3457 / S1172 / S7780 の完全解消 - 9件)**:
   - S5713 (2件): `tokyuParser` (JSONDecodeError vs ValueError) および `api.py` (ListingEndedException vs SkipPropertyException) の冗長例外キャッチを削除。
   - S1481 (2件): `api.py` および `sync_estat_municipalities.py` の未使用ローカル変数を `_` に置換。
   - S6035 (2件): `sumifuParser` 内の `re.split(u'/|／|\n', val)` を文字クラス `r'[/／\n]'` に置換。
   - S3457 (1件): `resolve_duplicate_evaluations.py` の `100% clean` による `% c` 誤認を `100%%` にエスケープ。
   - S1172 (1件): `tokyuParser` の未使用引数 `specs` を `_specs=None` に改名。
   - S7780 (1件): `slack_agent_host.js` の文字列エスケープを `String.raw` に置換。

## 6. 第3期最終要件: SonarCloud残存オープン課題（最後の13件）の完全ゼロ化 (Issue #428)
第2期対応後にSonarCloud上でオープンとして残存していた最終13件の課題を、コードリファクタリングおよびコメントコード削除により完全ゼロ化する：
1. **FR-013 (S125 コメントアウトコード削除 - 1件)**:
   - `src/crawler/package/utils/building_resolver.py:2-5`: モジュール冒頭のS125誤検知対象コメント・ブロックを削除。
2. **FR-014 (S3776 パーサー系認知的複雑度低減 - 6件)**:
   - `src/crawler/package/parser/tokyuParser.py:146`: `_scrape_row_dt_dd` から行単位抽出 `_extract_specs_from_row` を抽出し、二重ループのネスト複雑度を16から低減（<=15）。
   - `src/crawler/package/parser/mitsuiParser.py:1169`: `_parsePropertyDetailPage` から動的ディスパッチ処理 `_delegate_shumoku_parser` を抽出し、複雑度を16から低減（<=15）。
   - `src/crawler/package/parser/misawaParser.py:251`: `_getTrafficField` からバス交通フィールド抽出 `_extract_bus_field` を抽出し、分岐複雑度を22から低減（<=15）。
   - `src/crawler/package/parser/nomuraParser.py:220`: `_getTrafficField` から `_extract_bus_field` および `_extract_railway_walk` を抽出し、複雑度を26から低減（<=15）。
   - `src/crawler/package/parser/baseParser.py:1319`: `_parseMaguchi` から正規表現数値変換 `_extract_maguchi_decimal` を抽出し、複雑度を16から低減（<=15）。
   - `src/crawler/package/parser/homesParser.py:583`: `_parsePropertyDetailPage` にテーブルテキスト抽出ヘルパー `_get_table_text` を導入し、三項演算子と分岐の連続による複雑度20を低減（<=15）。
3. **FR-015 (S3776 機械学習・評価系認知的複雑度低減 - 5件)**:
   - `src/crawler/package/ml/train.py:161`: `_extract_unit_price_record` から面積算出ロジック `_determine_eval_area` を抽出し、複雑度17を低減（<=15）。
   - `src/crawler/package/ml/train.py:262`: `_generate_single_dummy_record` から面積サンプリング `_sample_dummy_areas` および種別属性生成 `_resolve_dummy_type_attributes` を抽出し、複雑度20を低減（<=15）。
   - `src/crawler/package/ml/train.py:741`: `main` 内の種別別ループ処理を `_train_single_ptype_models` に抽出し、複雑度17を低減（<=15）。
   - `src/crawler/package/ml/predict.py:330`: `_serialize_property` から `_prop_val`, `_prop_to_float`, `_serialize_chikunengetsu_field`, `_serialize_type_specific_fields` を抽出し、ネスト関数と複雑度20を低減（<=15）。
   - `src/crawler/package/ml/investment_evaluator.py:44`: `parse_chikunen` から元号計算 `_parse_era_year` を抽出し、インライン `import re` を排除して複雑度19を低減（<=15）。
4. **FR-016 (S3776 幾何解析系認知的複雑度低減 - 1件)**:
   - `src/crawler/package/utils/plot_shape_analyzer.py:597`: `analyze_plot_shape` から接道間口・奥行推定 `_estimate_frontage_and_depth` および内接矩形・うなぎ判定 `_calculate_mir_and_unagi` を抽出し、複雑度17を低減（<=15）。

## 7. 第4期要件: Strict Quality Gate ＆ 多層防御（Defense-in-Depth）確立 (Issue #436)
直近PRにて新規Issue（Code Smell）が1件発生したにもかかわらずSonarCloudがQuality Gate Passedと誤承認した問題に対処し、新規Issueが1件でも発生した場合に確実にCIをFAILさせる：
1. **FR-017 (Strict Quality Gate 策定と適用)**:
   - SonarCloud上にカバレッジ条件（`new_coverage`, `branch_coverage`）を除外し、新規課題件数 `new_violations > 0` で確実にエラー判定となるカスタムQuality Gate（Strict Gate）を策定・適用する。
   - `new_security_rating > 1`, `new_reliability_rating > 1`, `new_maintainability_rating > 1`, `new_duplicated_lines_density > 3`, `new_security_hotspots_reviewed < 100` も併せて維持する。
2. **FR-018 (CIワークフロー自動プロビジョニング & 逆戻り防止)**:
   - `.github/workflows/sonar.yml` において、Built-in Sonar way (gateId=9) への強制巻き戻し処理を廃止し、Strict Gateの作成・設定（存在確認・条件設定・プロジェクト関連付け）を自律実行するステップに更新する。
3. **FR-019 (CIレベル多層防御: check_sonar_remote --strict-zero-issues)**:
   - SonarCloudスキャン後に、`check_sonar_remote.py` にてPRまたは対象ブランチの未解決Issue数を検証し、1件でも残存している場合はCIジョブをexit 1で即座に異常終了させる二重防壁（Safety-Net）を設置する。
4. **FR-020 (残存Issue S8572 の即時修正)**:
   - 直近PRで混入した `src/crawler/package/utils/gcp_resources.py` の `logger.error` 例外呼び出しを `logger.exception` に修正し、プロジェクト全体での未解決Issue完全0件を回復する。

## 8. 非機能要件（第4期）
- **NFR-004 (新規Issue検出率100%)**: PRまたはmasterにおいて、SonarCloudが検知した新規Issue（バグ、脆弱性、コードスメル）が1件以上存在する場合、CIが100%の確実性でFAILすること。
- **NFR-005 (無関係なカバレッジ起因の誤検知排除)**: `sonar.coverage.exclusions=**` 環境下で、カバレッジ不足に起因する不要なQuality Gateエラーが発生しないこと。

