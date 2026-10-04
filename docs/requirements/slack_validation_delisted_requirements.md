# Slack進捗通知の分離、公開終了物件のDB保持、価格推定前データ検証の厳格化およびAuto-Healフラグ連携 要件定義書 (Issue #665)

## 1. 背景と課題

1. **Slackアラートチャンネルのノイズ（アラート疲弊）**:
   - `run_bulk_ml_evaluation.py` や `send_recommendations.py` 等のバッチ処理において、処理中の進捗通知や正常終了メトリクスが `send_crawling_summary_alert` を介して `#property_alert`（または `alerts-*`）へ送信されていた。
   - `is_alert_channel()` の判定により `logger.error` として記録され、運用上重大な障害通知を見逃す要因となっていた。
2. **価格推定前のデータ検証の甘さ**:
   - 既存の `validate_data.py` は「価格100万未満」「面積5㎡未満」のみを大雑把に検知するのみであり、㎡単価の桁外れ、築年数の異常値（1900年以前や未来年）、種別ごとの重要スペック欠損（マンションの所在階や専有面積、戸建の敷地・建物面積、投資物件の利回り）がすり抜けて機械学習推論に投入されていた。
3. **公開終了（掲載終了・404）物件の追跡欠如**:
   - クローリング後に掲載終了した物件がDB上で判別できず、無駄な再クローリングやML推論、さらには不要なエラーアラートが発生していた。
4. **Auto-Heal（自律修復）との連携不全**:
   - データ不正・欠損が発生した際、パーサー修正を行わずに即時再クローリングしても同一のエラーが再発する。問題データをDB上でフラグ管理し、Auto-Healによるパーサー改修タスクへ引き渡し、改修完了後に的確に再クローリングするエコシステムが必要。

---

## 2. 目的とスコープ

1. **Slack通知ルーティングの適正化**:
   - 通常の作業進捗・バッチサマリーはすべて `#dev-agent`（`send_dev_report`）に集約する。
   - `#property_alert` および `alerts-*` は真の重大障害（パイプライン強制停止・未回復システムエラー）のみに限定する。
2. **公開終了ステータスの永続化**:
   - `PropertyEvaluation` モデルに `is_published`（公開中フラグ）および `delisted_at`（掲載終了日時）を追加。
   - 404 / 掲載終了文言を検知した物件は速やかに非公開化し、リトライ・ML推論・お宝通知から除外する。
3. **多段階データ検証（Strict Data Validation）の導入**:
   - 価格、面積、㎡単価、築年数、種別ごとの必須スペックを網羅的に検証。
   - 不正物件は `needs_recrawl=True`, `data_quality_issue` に理由を記録し、当回のML推論を安全スキップ。
4. **Auto-Heal 連携基盤の確立**:
   - `needs_recrawl=True` かつ `is_published=True` の物件情報を Auto-Heal が集約し、パーサー改修対象を自動特定可能にする。

---

## 3. 機能要件

### FR-001: PropertyEvaluation モデルの拡張
- `is_published`: `BooleanField(default=True, db_index=True, verbose_name="公開中フラグ")`
- `delisted_at`: `DateTimeField(null=True, blank=True, verbose_name="掲載終了検知日時")`
- `needs_recrawl`: `BooleanField(default=False, db_index=True, verbose_name="再クローリング対象フラグ")`
- `data_quality_issue`: `TextField(blank=True, default="", verbose_name="データ不正・欠損理由")`

### FR-002: Slack通知ルーティング分離
- `run_bulk_ml_evaluation.py`: 進捗通知および完了サマリーの送信先を `send_dev_report`（`#dev-agent`）へ変更。
- `send_recommendations.py`: 推薦配信サマリーの送信先を `send_dev_report`（`#dev-agent`）へ変更。
- `validate_data.py`: データ監視サマリーを `#dev-agent` へ集約。

### FR-003: 生存確認 & 公開終了トラッキング
- `validate_data.py` の前段で `verify_url_active(url)` を実行（または判定）。
- 404 / 掲載終了を検知した場合:
  - `is_published = False`
  - `delisted_at = now()`
  - `needs_recrawl = False`
  - アラートは送信せず、スキップカウントとしてログ・メトリクスに計上。

### FR-004: 厳格データバリデーション
`validate_data.py` において以下のルールで検査：
1. **価格**: `0 < price_man < 100` または `price_man > 200,000`（20億円超）
2. **面積**: `area < 5.0` または `area > 5000.0`
3. **㎡単価**: `price / area` が 1,000円/㎡未満、または 1,500万円/㎡超
4. **築年数**: 西暦1900年未満、または未来3年超
5. **種別必須スペック欠損**:
   - マンション: 専有面積または所在階が未設定
   - 戸建て: 土地面積または建物面積が未設定
   - 土地: 土地面積が未設定
   - 投資物件: 表面利回りが 0% または 100% 超
6. **判定結果の反映**:
   - 異常ありの場合: `eval_rec.needs_recrawl = True`, `eval_rec.data_quality_issue = reasons`, `eval_rec.first_stage_predicted_price = 0`, `eval_rec.is_slack_notified = True`（通知除外ガード）。

### FR-005: ML推論・推薦からの公開終了除外
- `run_bulk_ml_evaluation.py`: `is_published=False` の物件は評価対象から除外。
- `send_recommendations.py`: `is_published=False` の物件は推薦対象から除外。

---

## 4. 非機能要件
- **NFR-001**: 外部HTTPリクエスト（生存確認）は有限タイムアウト（最大5秒）を遵守。
- **NFR-002**: バリデーション処理によるパイプライン遅延を最小化（インメモリ判定を主軸とし、DB更新はbulk処理を活用）。
- **NFR-003**: 既存テストの完全通過（後方互換性担保）。
