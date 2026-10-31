# パイプライン耐障害性向上＆ML価格推定・お宝物件通知進捗Slack通知 内部設計書

## 1. 詳細モジュール設計

### 1.1 `src/crawler/scripts/ops/run_pipeline.py`
* **関数の変更**:
  - `run_command(cmd, desc, timeout=None, ignore_errors=False) -> bool`:
    - `ignore_errors=True` の場合、非ゼロ終了コードや例外発生時に `RuntimeError` を再送出せず、`logger.error` を記録して `False` を返す。
  - `_run_crawler_step(is_task_array, is_coordinator, task_index, task_count, ops_dir, skip_portals) -> tuple[bool, bool]`:
    - 戻り値を `(should_continue, crawl_success)` とする。
    - クローリング実行（`run_all_crawlers.py`）を `ignore_errors=True` または try-except で実行。
    - エラー発生時は `crawl_success = False` としつつ、Coordinator または単一実行なら `should_continue = True` を返して後続パイプラインを呼出可能とする。
    - 分散タスク待機（`wait_for_all_tasks`）でタイムアウトや失敗があっても、集約レポート送信後に後続処理へ進む。
  - `_run_post_crawl_pipeline(crawler_dir, ops_dir, maintenance_dir, debug_tools_dir, skip_portals) -> dict[str, bool]`:
    - ステップごとに `run_command` を安全に呼び出し、各ステップの実行結果（成否）をディクショナリで追跡。
    - Step 2: データ検証
    - Step 2.5: Auto-Heal 指示書
    - Step 3: ML再学習（エラーでも Step 4 をブロックしない）
    - Step 4: バルク価格推定
    - Step 5: お宝物件通知
    - Step 6: 日次予測診断

### 1.2 `src/crawler/scripts/ops/run_bulk_ml_evaluation.py`
* **Slack通知ヘルパーの追加**:
  - `from package.utils.slack import send_crawling_summary_alert`
  - 非同期関数 `_send_slack(msg: str)` を定義し、`asyncio.run(send_crawling_summary_alert(msg))` を安全に実行（例外は握り潰してログ出力し、処理そのものは止めない）。
* **進捗追跡**:
  - `start_time = time.time()`
  - 処理開始前:
    `_send_slack(f"🚀 【バルク価格推定開始】 未評価物件の一括価格予測を開始します (対象: {len(models)} モデル, 並行数: {concurrency})...")`
  - 各モデル完了時:
    ```python
    evaluated_count += cnt
    skipped_count += skp
    if cnt > 0:
        _send_slack(f"📊 【価格推定進捗】 {m.__name__}: 評価 {cnt} 件 (スキップ {skp} 件) | 累計 {evaluated_count} 件完了")
    ```
  - 完了時:
    ```python
    duration_str = format_duration(int(time.time() - start_time))
    finish_msg = (
        f"✅ 【バルク価格推定完了】\n"
        f"評価件数: {evaluated_count} 件\n"
        f"スキップ件数: {skipped_count} 件\n"
        f"所要時間: {duration_str}"
    )
    if failed_models:
        finish_msg += f"\n⚠️ 評価失敗モデル: {', '.join(failed_models)}"
    _send_slack(finish_msg)
    ```

### 1.3 `src/crawler/scripts/ops/send_recommendations.py`
* **Slack通知ヘルパーの活用**:
  - `from package.utils.slack import send_crawling_summary_alert`
  - `_send_status(msg: str)` を追加。
* **進捗通知ロジック**:
  - 開始時:
    `_send_status("🔍 【お宝物件スクリーニング開始】 割安・高利回り物件の抽出を開始します...")`
  - 候補抽出後:
    ```python
    if not matched_candidates:
        _send_status("ℹ️ 【お宝物件通知】 現在配信基準を満たす新規お宝物件はありませんでした (0件)。")
        return
    _send_status(f"🎯 【お宝物件検出】 {len(matched_candidates)} 件の候補物件を検出しました。上位 {len(top_candidates)} 件を配信します。")
    ```
  - 配信完了後:
    `_send_status(f"✅ 【お宝物件配信完了】 計 {sent_count}/{len(top_candidates)} 件のお宝物件カードを配信完了しました。")`

### 1.4 `src/crawler/scripts/maintenance/validate_data.py`
* **動的実行パス解決 (`setup_env`)**:
  - スクリプトが独立プロセスとして `python validate_data.py` で直接呼び出された場合でも `setup_env.py` を確実にロードできるよう、`__file__` から親ディレクトリ階層を遡り、`setup_env.py` の存在するディレクトリ（`src/crawler/`）を `sys.path` に動的追加した上で `import setup_env` を実行する。
  - `PYTHONPATH` 環境変数の有無やカレントディレクトリに依存しない実行保証を確立する。

## 2. エラーハンドリング・テスト観点
1. **クローラーが終了コード 1 で異常終了した場合**:
   - `_run_crawler_step` が例外で落ちず、`_run_post_crawl_pipeline` に遷移すること。
2. **ML学習（Step 3）が失敗した場合**:
   - バルク価格推定（Step 4）とお宝物件通知（Step 5）がスキップされずに正常実行されること。
3. **Slack API エラー時**:
   - Slack通知の失敗が進捗や推論バッチを停止させないこと。
4. **メンテナンス・検証スクリプトの独立起動時**:
   - `validate_data.py` を任意のカレントディレクトリから単体プロセス実行した際に、`setup_env` の `ModuleNotFoundError` が発生せず正常に終了すること。


---

## 3. Issue #1160: Watchdogハング防止・バルク価格推定DB再接続・詳細二重保存排除・テスト強化設計

### 3.1 Watchdog 進捗ファイル一致・初期探索猶予保護・`atexit` デッドロック防止
* **ジョブ固有進捗ファイルの固定 (`CRAWLER_JOB_COMPANY` / `CRAWLER_JOB_TYPE`)**:
  - `main.py`（および `run_all_crawlers.py` の子プロセス起動時）において、CLI引数 `--company` / `--type` を環境変数 `CRAWLER_JOB_COMPANY` / `CRAWLER_JOB_TYPE` に設定する。
  - `ApiAsyncProcBase._touch_watchdog_progress()`、`differential._touch_differential_progress()`、および `_touch_active_progress_files()` は、環境変数 `CRAWLER_JOB_COMPANY` / `CRAWLER_JOB_TYPE` が存在する場合は最優先でそのファイル（`progress_{company}_{type}.touch`）のみを更新する。他プロセスの `.touch` ファイルを無差別に更新してはならない。
* **初回探索猶予 (`INITIAL_DISCOVERY_GRACE_SEC = 1800s`) の保護**:
  - `run_all_crawlers.py` は子プロセス起動前に初期 `.touch` ファイルを作成した上で `now_ts = time.time()` を記録し、`main.py` 起動直後の冗長な初期 `touch_crawler_progress()` によって `last_activity_time > start_time` が即座に成立して 1800秒の初期探索猶予が消失することを防ぐ。
* **中間ページ・詳細ワーカーの Heartbeat 強化 & 終了時 `atexit` デッドロック防止**:
  - `ParseMiddlePageAsyncBase._fetch_middle_page_response()` および `_detail_worker()` で進捗ファイルを更新する。
  - `_wait_for_active_fire_and_forget_threads()` でタイムアウトまたは停止フラグ検知時は、`STOP_FLAG_FILE` を生成して未開始 `Future` をキャンセルし、`_local_worker_executor.shutdown(wait=False, cancel_futures=True)` を呼び出すとともに、`main.py` の CLI 異常終了時は `atexit` の `ThreadPoolExecutor` 無限 `join()` を回避して確実にプロセスを終了させる。

### 3.2 バルク価格推定 (`bulk_evaluation`) ＆ `validate_data.py` の DB 切断耐性・名寄せ高速化
* **チャンクイテレーション時の DB 再接続 (`targets.py` / `validate_data.py`)**:
  - `_iter_target_items()` および `validate_data.py` のレコード走査を PK ベースチャンク（1,000件単位）で実行し、`OperationalError` (`2006`, `2013`, `9001`) 発生時は `close_old_connections()` 後に指数バックオフで最大3回リトライする。
* **名寄せ (`deduplication.py`) のバッチプリフェッチ＆スレッドセーフ化**:
  - `_REAL_PROPERTY_CACHE` を `threading.Lock` で保護し、候補レコードの実物件 (`_get_real_property`) をモデル別に `id__in` で一括プリフェッチすることで N+1 クエリと ProxySQL コネクション枯渇を防ぐ。

### 3.3 詳細ページ単一保存ライフサイクル (`api.py`) ＆ モデル `blank=True` 規約 (Gate 2)
* **`ParseDetailPageAsyncBase` の二重保存排除**:
  - `ParseDetailPageAsyncBase._treatPage()` 内で `_handle_saved_property()` により保存・ML評価が完了しているため、`ParseDetailPageAsyncBase` では親クラスのバッチ用 `_afterRunProc` による再度の `_save_item_with_retry()`（`full_clean()` + `save()` 二重実行）を行わない。
* **全具体モデルの `blank=True` 統一と Gate 2 ハーネス検証**:
  - `null=True` を持つ全フィールドおよび任意文字列フィールドに `blank=True` を付与し、`test_architecture_harness.py` (Gate 2) で機械的に検証する。

### 3.4 物件種別4層防衛・個別パーサーエッジケース対応
* **`rearieParser.py`**: トップページリダイレクト等で `h1` が空かつ主要スペックが取得できない場合は `ListingEndedException` を送出する。
* **`tokyuParser.py`**:
  - `TokyuMansionParser`: `/fudosan-toushi/` URL やタイトル内の `｜投資用物件` を検出した場合は `SkipPropertyException` で即座にスキップする。
  - `TokyuKodateParser`: `setsumen` / `douroHaba` には文字列メソッドではなく `Decimal | None` を返す `_parseSetsumen` / `_parseDouroHaba` を代入し、`接道方向／幅員` がない場合は `道路幅員` キーへフォールバックする。
* **`homesParser.py` / `InvestmentParserBase`**: `grossYield >= 1000`（`DecimalField(max_digits=5, decimal_places=2)` 上限超過）の異常値は `None` にクレンジングする。
* **`sumai1Parser.py`**: `Sumai1InvestmentParser` で `/buyers/tochi/`・`/buyers/kodate/`・`/buyers/mansion/` の実需URLを `SkipPropertyException` で拒否する。
* **`tohoParser.py`**: `h1` 内の `お気に入りに追加` プレフィックスを除去して `propertyName` を抽出する。
