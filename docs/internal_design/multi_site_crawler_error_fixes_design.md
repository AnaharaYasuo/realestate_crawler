# 内部設計書: 複数サイトクローラー異常・DB切断・プロセス回収の堅牢化 (Issue #461)

## 1. 概要
Cloud Run 上で稼働するクローラーパイプラインにおいて、実ログ解析により判明した以下の複数サイト起因の例外・エラーを解消し、パイプラインの完走率およびデータ整合性を向上させる。

1. **プロセス回収時のタプル展開不整合解消 (`run_all_crawlers.py`)**:
   - `active_processes` に `(proc, company, ptype, time.time(), start_dt)` の5要素が格納されているのに対し、`cleanup_active_process()` で4要素展開していた不整合を修正 (`*_` による可変長展開)。
2. **収益非賃貸/自己利用物件の安全スキップ (`SmtrcInvestmentParser`, `MizuhoInvestmentParser`)**:
   - 利回り (`grossYield`) および賃料 (`annualRent`) が共に存在しない自己利用・オフィス物件に対し、抽出エラーと判定せず `SkipPropertyException` を送出してスキップする。
3. **Odakyu パーサーのクリーンアップ順序是正 (`odakyuParser.py`)**:
   - 基底クラス `_parsePropertyDetailPage` における `clean_parsed_item` の早期呼び出しを除去し、子パーサーによる固有フィールド抽出完了後にトップレベルでクリーンアップを実行。
4. **長時間クロールにおける DB 接続切断 (MySQL 2006) への自動再接続 (`url_matcher.py`, `api.py`)**:
   - `UrlMatcher.find_match_in_queryset` および `api.py` の `_save_property_and_price_history` において、`2006 Server has gone away` を検知した場合に `close_old_connections()` を実行して自動リトライする。
5. **非物件・記事 URL の早期除外 (`tokyuParser.py`, `sumifuParser.py`, `baseParser.py`)**:
   - 一覧ページから抽出された URL に対して `_is_non_property_href` フィルタを適用し、賃貸ページや宣伝記事のクローリングを未然に防止。
6. **Mizuho WAF 回避時の sitemap 自動フォールバック (`mizuho_bypass.py`)**:
   - Playwright バイパスで 0 件または例外が発生した際、公式 XML サイトマップによる詳細 URL 取得へ自動フォールバック。

## 2. 変更対象ファイル
- `src/crawler/scripts/ops/run_all_crawlers.py`
- `src/crawler/package/parser/smtrcParser.py`
- `src/crawler/package/parser/odakyuParser.py`
- `src/crawler/package/parser/mizuhoParser.py`
- `src/crawler/package/parser/tokyuParser.py`
- `src/crawler/package/parser/sumifuParser.py`
- `src/crawler/package/parser/baseParser.py`
- `src/crawler/package/utils/mizuho_bypass.py`
- `src/crawler/package/utils/url_matcher.py`
- `src/crawler/package/api/api.py`
- `src/crawler/tests/unit/test_smtrc_parser.py`
