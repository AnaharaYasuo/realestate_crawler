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
