# Slack進捗通知の分離、公開終了物件のDB保持、価格推定前データ検証の厳格化およびAuto-Healフラグ連携 内部設計書 (Issue #665)

## 1. データベース定義更新 (`package.models.evaluation.PropertyEvaluation`)

```python
class PropertyEvaluation(models.Model):
    # ... 既存フィールド ...

    # 公開ステータス管理
    is_published = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="公開中フラグ"
    )
    delisted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="掲載終了検知日時"
    )

    # Auto-Heal・再クローリング連携フラグ
    needs_recrawl = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="再クローリング対象フラグ"
    )
    data_quality_issue = models.TextField(
        blank=True,
        default="",
        verbose_name="データ不正・欠損理由"
    )
```

マイグレーションファイル: `src/crawler/package/migrations/0002_add_delisted_and_recrawl_flags.py`（または自動採番された連番）

---

## 2. バリデータモジュール設計 (`package.utils.data_validator`)

`validate_data.py` の判定ロジックを責務分離し、単体テスト可能・再利用可能にする。

```python
class PropertyDataValidator:
    """物件データの完全性・妥当性を厳格に検査するバリデータ"""

    @classmethod
    def validate_property(cls, item, property_type: str) -> tuple[bool, list[str]]:
        """
        物件インスタンスを検証し、(is_valid: bool, reasons: list[str]) を返却する。
        is_valid が False の場合は再クローリング対象 (needs_recrawl=True) となる。
        """
        reasons = []
        # 1. 価格チェック
        # 2. 面積チェック
        # 3. ㎡単価チェック
        # 4. 築年数チェック
        # 5. 種別ごとの必須スペックチェック
        return len(reasons) == 0, reasons
```

---

## 3. スクリプト改修詳細

### 3.1 `src/crawler/scripts/maintenance/validate_data.py`
1. 該当物件のURLに対して `is_published` をチェック。
2. 不正検出時、`eval_rec` を取得または作成し：
   - `eval_rec.needs_recrawl = True`
   - `eval_rec.data_quality_issue = "; ".join(reasons)`
   - `eval_rec.first_stage_predicted_price = 0`
   - `eval_rec.is_slack_notified = True`
3. 通知は `send_dev_report()`（`#dev-agent`）を使用し、`property_alert` への誤報を排除。

### 3.2 `src/crawler/scripts/ops/run_bulk_ml_evaluation.py`
1. `_notify_slack()` を `send_dev_report` 呼び出しに変更。
2. 評価対象クエリ（`get_uncalculated_properties` やチャンク取得）に `is_published=True` フィルターを適用（または除外マップで判定）。

### 3.3 `src/crawler/scripts/ops/send_recommendations.py`
1. 配信完了サマリーを `send_dev_report` に変更。
2. 推薦対象抽出クエリで `is_published=True` かつ `needs_recrawl=False` を保証。

### 3.4 単価上限引上げ・面積候補フォールバック・残留不整合レコード同期 (Issue #922)
1. `PropertyDataValidator._validate_unit_price`:
   - 平米単価上限を `15,000,000円/㎡` から `50,000,000円/㎡` へ引き上げ。都心超高額物件（虎ノ門等）の正常物件誤検知を解消。
2. `PropertyDataValidator._extract_and_validate_area`:
   - 専有面積、建物面積、土地面積の候補走査時、先頭候補が `<=5.0` の場合でも直ちに終了せず、後続に `>5.0` の候補（例: 一棟アパートで建物面積1㎡・土地面積91.77㎡）があれば有効な数値を優先採用。全候補が `<=5.0` の場合のみ面積異常とする。
3. `resolve_50_residual_issues.py` および Auto-Heal 連携:
   - 現行バリデータで合格する物件の `needs_parser_fix` を `False` に解除し、`data_quality_issue` をクリアして `auto_heal_parsers.py` スキャンの正常化（異常0件）を達成。

