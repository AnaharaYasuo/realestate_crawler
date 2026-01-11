# コード改善提案書 (Refactoring Suggestions)

本ドキュメントでは、システムのさらなる保守性・拡張性・可読性向上のための未実施のリファクタリング方針を提案します。

## 改訂履歴

- **2026-01-11**: Phase 3とPhase 4の一部実装完了に伴い更新

---

## 実装済みの改善

以下は既に実装済みです：

- ✅ Model Organization Matrix（基底クラス作成）
- ✅ Dual Storage自動化（DualStorageDescriptor実装）
- ✅ セレクタの外部化（SelectorLoader + YAML設定）

詳細は `feature/advanced-refactoring` ブランチを参照してください。

---

## Phase 4: アーキテクチャの改善（未実装）

### 4.1 型安全性の向上（Pydanticスキーマ導入）

**優先度:** 中

**現状の課題:**
- Django Modelインスタンスを直接操作
- 実行時にしかフィールドの有無が分からない
- 不正なデータ（負の価格、0以下の面積等）がDB保存前に検出できない

**提案:**

Pydanticを使用した中間データスキーマを導入：

```python
# requirements.txtに追加
pydantic==2.5.0

# src/crawler/package/schemas/property.py
from pydantic import BaseModel, Field, validator
from typing import Optional
from decimal import Decimal
from datetime import date

class PropertyDataSchema(BaseModel):
    """パース結果の中間データスキーマ"""
    
    # Universal Fields
    propertyName: str = Field(..., min_length=1)
    pageUrl: str = Field(..., min_length=1)
    priceStr: str
    price: int = Field(ge=0)
    address: str
    
    @validator('price')
    def validate_price(cls, v):
        if v < 0:
            raise ValueError('価格は0以上である必要があります')
        if v > 100_000_000_000:  # 1000億円
            raise ValueError('価格が異常に高額です')
        return v
    
    class Config:
        validate_assignment = True


class MansionDataSchema(PropertyDataSchema):
    """マンション物件のスキーマ"""
    
    senyuMensekiStr: Optional[str] = None
    senyuMenseki: Optional[Decimal] = Field(None, ge=0)
    
    chikunengetsuStr: Optional[str] = None
    chikunengetsu: Optional[date] = None
    
    kanrihiStr: Optional[str] = None
    kanrihi: Optional[int] = Field(None, ge=0)
    
    @validator('senyuMenseki')
    def validate_menseki(cls, v):
        if v is not None and v <= 0:
            raise ValueError('面積は正の値である必要があります')
        if v is not None and v > 1000:
            raise ValueError('面積が異常に大きいです')
        return v


# パーサーでの使用
class MitsuiMansionParser(MitsuiParser):
    def _parsePropertyDetailPage(self, item, response):
        # Pydanticモデルでバリデーション
        try:
            data = MansionDataSchema(
                propertyName=self._clean_text(title_el.get_text()),
                pageUrl=str(response.url),
                priceStr=price_str,
                price=converter.parse_price(price_str),
                address=address_str,
                senyuMensekiStr=menseki_str,
                senyuMenseki=converter.parse_menseki(menseki_str),
            )
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            raise
        
        # Django Modelに変換
        for field, value in data.dict(exclude_none=True).items():
            setattr(item, field, value)
        
        return item
```

**メリット:**
- 型ヒントによるIDE支援（自動補完、型チェック）
- 不正なデータのDB保存前遮断
- バリデーションエラーの早期発見
- ドキュメントとしての役割（スキーマ定義が仕様書になる）

**実装工数:** 約2週間

---

### 4.3 APIチェーンのミドルウェア化

**優先度:** 中

**現状の課題:**
- API連鎖（Start → Region → List → Detail）がハードコード
- 特定ステップでのみリトライを増やす、レート制限を追加するのが困難
- 横断的関心事（ログ、監視、エラーハンドリング）がAPI実装に混在

**提案:**

ミドルウェアパターンを導入して横断的関心事を分離：

```python
# src/crawler/package/api/middleware.py
from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CrawlerMiddleware(ABC):
    """ミドルウェアの基底クラス"""
    
    @abstractmethod
    async def process_request(self, request_context: dict) -> Optional[dict]:
        """リクエスト前処理"""
        pass
    
    @abstractmethod
    async def process_response(self, response_context: dict) -> dict:
        """レスポンス後処理"""
        pass


class RateLimitMiddleware(CrawlerMiddleware):
    """レート制限ミドルウェア"""
    
    def __init__(self, delay: float = 1.0):
        self.delay = delay
    
    async def process_request(self, request_context: dict) -> None:
        await asyncio.sleep(self.delay)
        return None
    
    async def process_response(self, response_context: dict) -> dict:
        return response_context


class RetryMiddleware(CrawlerMiddleware):
    """リトライミドルウェア"""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 10.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def process_request(self, request_context: dict) -> None:
        return None
    
    async def process_response(self, response_context: dict) -> dict:
        if response_context.get('status') >= 500:
            retry_count = response_context.get('retry_count', 0)
            if retry_count < self.max_retries:
                logger.warning(f"Retrying (attempt {retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(self.retry_delay)
                response_context['should_retry'] = True
                response_context['retry_count'] = retry_count + 1
        
        return response_context


# APIクラスでの使用
class MitsuiMansionStartApi(ApiAsyncProcBase):
    middlewares = [
        RateLimitMiddleware(delay=1.0),
        RetryMiddleware(max_retries=3, retry_delay=10.0),
    ]
```

**メリット:**
- 横断的関心事の分離
- 柔軟なカスタマイズ（ミドルウェアの追加・削除が容易）
- 既存コードを汚さない拡張
- テストが容易（ミドルウェア単体でテスト可能）

**実装工数:** 約3週間

---

## Phase 5: 監視・運用の改善（未実装）

### 5.1 構造化ログの導入

**優先度:** 低

**現状の課題:**
- ログが非構造化（文字列のみ）
- ログの検索・分析が困難
- 問題の早期発見が難しい

**提案:**

structlogを使用した構造化ログ：

```python
# requirements.txtに追加
structlog==23.1.0

# src/crawler/package/utils/logging_config.py
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()

# 使用例
logger.info(
    "property_parsed",
    company="mitsui",
    property_type="mansion",
    property_name="〇〇マンション",
    price=54800000,
    url="https://...",
)
```

**メリット:**
- ログの検索・分析が容易
- 問題の早期発見
- 監視ツールとの統合が容易

**実装工数:** 約3日

---

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

## 実装優先度マトリックス

| 改善項目 | 優先度 | 難易度 | 影響範囲 | 期待効果 | 実装工数 |
|---------|--------|--------|---------|---------|---------|
| **型安全性向上（Pydantic）** | 中 | 中 | パーサー全体 | 品質◎ | 2週間 |
| **ミドルウェア化** | 中 | 高 | API層 | 拡張性◎ | 3週間 |
| **構造化ログ** | 低 | 低 | 全体 | 運用性○ | 3日 |
| **メトリクス収集** | 低 | 中 | 全体 | 運用性○ | 1週間 |

---

## 期待される効果

### 定量的効果

| 指標 | 現状 | Phase 4完了後 | Phase 5完了後 |
|------|------|--------------|--------------|
| バグ検出率 | 実行時 | コンパイル時+実行時 | コンパイル時+実行時 |
| ログ検索時間 | 5分 | 5分 | 30秒（-90%） |
| 問題特定時間 | 30分 | 20分 | 5分（-83%） |

### 定性的効果

**Phase 4完了後:**
- ✅ 型安全性による開発効率向上
- ✅ 横断的関心事の分離

**Phase 5完了後:**
- ✅ 運用監視の充実
- ✅ 問題の早期発見
- ✅ パフォーマンス最適化

---

## 実装ロードマップ

### 短期（1ヶ月）
1. Pydanticスキーマの導入
2. 既存パーサーへの段階的適用
3. 統合テストの実施

### 中期（2-3ヶ月）
1. ミドルウェアパターンの導入
2. 既存APIクラスへの適用
3. パフォーマンステスト

### 長期（3-6ヶ月）
1. 構造化ログの導入
2. メトリクス収集の実装
3. 監視ダッシュボードの構築

---

## まとめ

**実装済み:**
- ✅ Model Organization Matrix（基底クラス）
- ✅ Dual Storage自動化
- ✅ セレクタ外部化

**未実装（推奨順）:**
1. 🔄 型安全性向上（Pydantic）- 優先度: 中
2. 🔄 ミドルウェア化 - 優先度: 中
3. 📊 構造化ログ - 優先度: 低
4. 📊 メトリクス収集 - 優先度: 低

これらの改善により、システムの品質・保守性・運用性がさらに向上します。
