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

## 2. エラーハンドリング・テスト観点
1. **クローラーが終了コード 1 で異常終了した場合**:
   - `_run_crawler_step` が例外で落ちず、`_run_post_crawl_pipeline` に遷移すること。
2. **ML学習（Step 3）が失敗した場合**:
   - バルク価格推定（Step 4）とお宝物件通知（Step 5）がスキップされずに正常実行されること。
3. **Slack API エラー時**:
   - Slack通知の失敗が進捗や推論バッチを停止させないこと。
