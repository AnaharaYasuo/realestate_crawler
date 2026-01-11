# コード改善提案書 (Refactoring Suggestions)

本ドキュメントでは、システムのさらなる保守性・拡張性・可読性向上のための未実施のリファクタリング方針を提案します。

---

## 実装済みの改善

以下は全て実装済みです：

- ✅ Model Organization Matrix（基底クラス作成）
- ✅ Dual Storage自動化（DualStorageDescriptor実装）
- ✅ セレクタの外部化（SelectorLoader + YAML設定）
- ✅ 型安全性の向上（Pydanticスキーマ導入）
- ✅ APIチェーンのミドルウェア化（RateLimit, Retry, Logging）
- ✅ 構造化ログの導入（structlog）

詳細は `master` ブランチのソースコードおよび `docs/` 配下のドキュメントを参照してください。

---

## 監視・運用の改善（未実装）

### 5.2 メトリクス収集

**優先度:** 低

**現状の課題:**
- パフォーマンスの可視化が困難
- ボトルネックの特定が難しい

**提案:**

Prometheusクライアントを使用したメトリクス収集：

```python
# requirements.txtに追加
prometheus-client==0.19.0

# src/crawler/package/utils/metrics.py
from prometheus_client import Counter, Histogram

# メトリクス定義
properties_scraped = Counter(
    'properties_scraped_total',
    'Total properties scraped',
    ['company', 'property_type']
)

scraping_duration = Histogram(
    'scraping_duration_seconds',
    'Time spent scraping',
    ['company', 'property_type', 'stage']
)

# 使用例
properties_scraped.labels(company='mitsui', property_type='mansion').inc()

with scraping_duration.labels(company='mitsui', property_type='mansion', stage='detail').time():
    # スクレイピング処理
    pass
```

**メリット:**
- パフォーマンス監視
- ボトルネックの特定
- SLO/SLIの設定が可能

**実装工数:** 約1週間

---

## まとめ

**実装済み:**
- ✅ Phase 3, 4, 5.1（基底クラス、Dual Storage、セレクタ外部化、Pydantic、ミドルウェア、構造化ログ）

**未実装:**
- 🔄 5.2 メトリクス収集 - 優先度: 低

これらの改善により、システムの品質・保守性・運用性がさらに向上しました。未実装の項目についても、必要に応じて段階的に導入を検討してください。
