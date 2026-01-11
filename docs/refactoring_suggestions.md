# コード改善提案書 (Refactoring Suggestions)

本ドキュメントでは、システムのさらなる保守性・拡張性・可読性向上のための未実施のリファクタリング方針を提案します。

## 改訂履歴

- **2026-01-11**: 実施済み改善を除外し、未実施の提案のみに整理

---

## Phase 3: データモデルの最適化（優先度: 高）

### 3.1 Model Organization Matrixの活用

**現状の課題:**
- 17モデル（5社×4種別-3）が個別に定義されている
- 共通フィールド（Universal Fields 8個、Transportation Fields 40個）が各モデルで重複定義
- 新規会社追加時に大量のボイラープレートコードが必要

**提案:**

抽象基底クラスとMixinを活用してフィールド定義を共通化：

```python
# src/crawler/package/models/base.py

from django.db import models

class PropertyBaseModel(models.Model):
    """全物件共通の8フィールド（Universal Fields）"""
    class Meta:
        abstract = True
    
    # Universal Fields
    propertyName = models.TextField()
    pageUrl = models.CharField(max_length=500, db_index=True)
    inputDate = models.DateField(auto_now_add=True)
    inputDateTime = models.DateTimeField(auto_now_add=True)
    priceStr = models.TextField()
    price = models.IntegerField()
    address = models.TextField()
    traffic = models.TextField()


class TransportationMixin(models.Model):
    """5路線×8フィールド=40フィールド"""
    class Meta:
        abstract = True
    
    # Route 1
    transfer1 = models.TextField(blank=True, null=True)
    railway1 = models.TextField(blank=True, null=True)
    station1 = models.TextField(blank=True, null=True)
    railwayWalkMinute1Str = models.TextField(blank=True, null=True)
    railwayWalkMinute1 = models.IntegerField(blank=True, null=True)
    busStation1 = models.TextField(blank=True, null=True)
    busWalkMinute1Str = models.TextField(blank=True, null=True)
    busWalkMinute1 = models.IntegerField(blank=True, null=True)
    
    # Route 2-5 (同様の定義)
    # ...


class MansionBaseModel(PropertyBaseModel, TransportationMixin):
    """マンション共通フィールド"""
    class Meta:
        abstract = True
    
    # Dual Storage Pattern
    senyuMensekiStr = models.TextField(blank=True, null=True)
    senyuMenseki = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    chikunengetsuStr = models.TextField(blank=True, null=True)
    chikunengetsu = models.DateField(blank=True, null=True)
    
    kanrihiStr = models.TextField(blank=True, null=True)
    kanrihi = models.IntegerField(blank=True, null=True)
    
    syuzenTsumitateStr = models.TextField(blank=True, null=True)
    syuzenTsumitate = models.IntegerField(blank=True, null=True)
    
    # マンション特有フィールド
    madori = models.TextField(blank=True, null=True)
    balconyMensekiStr = models.TextField(blank=True, null=True)
    balconyMenseki = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    # ...


class KodateBaseModel(PropertyBaseModel, TransportationMixin):
    """戸建て共通フィールド"""
    class Meta:
        abstract = True
    
    tochiMensekiStr = models.TextField(blank=True, null=True)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    tatemonoMensekiStr = models.TextField(blank=True, null=True)
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    chikunengetsuStr = models.TextField(blank=True, null=True)
    chikunengetsu = models.DateField(blank=True, null=True)
    # ...


# 使用例: src/crawler/package/models/mitsui.py
class MitsuiMansion(MansionBaseModel):
    """三井のリハウス マンション"""
    class Meta:
        db_table = 'crawler_mitsumansion'
        managed = True
    
    # 三井固有のフィールドのみ追加
    # （ほとんどの場合、追加フィールドは不要）
```

**メリット:**
- フィールド定義の重複を約80%削減（約1,600行 → 約320行）
- 新規会社追加時の実装量を大幅削減（約500行 → 約50行）
- モデル間の一貫性を保証
- マイグレーション管理が容易

**実装手順:**
1. `src/crawler/package/models/base.py`を作成
2. 既存モデルを段階的に移行（1社ずつ）
3. マイグレーションを生成・適用
4. テストで動作確認

---

### 3.2 Dual Storage Patternの自動化

**現状の課題:**
- 文字列フィールド（`priceStr`）と数値フィールド（`price`）を手動で管理
- パーサーで両方のフィールドに値を設定する必要がある
- 設定漏れによるデータ不整合のリスク

**提案:**

カスタムディスクリプタを使用して自動的に両方のフィールドを管理：

```python
# src/crawler/package/models/fields.py

from decimal import Decimal
from typing import Callable, Optional

class DualStorageDescriptor:
    """文字列と数値を自動的に両方保存するディスクリプタ"""
    
    def __init__(self, str_field: str, numeric_field: str, converter: Callable):
        self.str_field = str_field
        self.numeric_field = numeric_field
        self.converter = converter
    
    def __set_name__(self, owner, name):
        self.name = name
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self.str_field)
    
    def __set__(self, obj, value):
        # 文字列フィールドに元の値を保存
        setattr(obj, self.str_field, value)
        
        # 数値フィールドに変換後の値を保存
        try:
            numeric_value = self.converter(value) if value else None
            setattr(obj, self.numeric_field, numeric_value)
        except Exception:
            setattr(obj, self.numeric_field, None)


# 使用例
from package.utils import converter

class MitsuiMansion(MansionBaseModel):
    # ディスクリプタを定義
    price_dual = DualStorageDescriptor('priceStr', 'price', converter.parse_price)
    senyuMenseki_dual = DualStorageDescriptor('senyuMensekiStr', 'senyuMenseki', converter.parse_menseki)
    kanrihi_dual = DualStorageDescriptor('kanrihiStr', 'kanrihi', converter.parse_price)


# パーサーでの使用
class MitsuiMansionParser(MitsuiParser):
    def _parsePropertyDetailPage(self, item, response):
        # 1つのフィールドに設定するだけで、両方のフィールドが自動的に設定される
        item.price_dual = "5,480万円"  # priceStr="5,480万円", price=54800000
        item.senyuMenseki_dual = "81.65㎡"  # senyuMensekiStr="81.65㎡", senyuMenseki=81.65
        item.kanrihi_dual = "15,000円"  # kanrihiStr="15,000円", kanrihi=15000
        
        return item
```

**メリット:**
- 設定ミスによるデータ不整合を防止
- パーサーコードの簡潔化（約30%削減）
- 変換ロジックの一元管理

**実装手順:**
1. `src/crawler/package/models/fields.py`を作成
2. 既存モデルにディスクリプタを追加
3. パーサーを段階的に移行
4. テストで動作確認

---

## Phase 4: アーキテクチャの改善（優先度: 中）

### 4.1 型安全性の向上（Pydanticスキーマ導入）

**現状の課題:**
- Django Modelインスタンスを直接操作
- 実行時にしかフィールドの有無が分からない
- 不正なデータ（負の価格、0以下の面積等）がDB保存前に検出できない

**提案:**

Pydanticを使用した中間データスキーマを導入：

```python
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
                # ...
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

**実装手順:**
1. `requirements.txt`に`pydantic`を追加
2. `src/crawler/package/schemas/`ディレクトリを作成
3. スキーマ定義を作成
4. パーサーを段階的に移行
5. テストで動作確認

---

### 4.2 セレクタの外部化

**現状の課題:**
- CSSセレクタがコード内に埋め込まれている（例: `response.select_one("h1.headline1")`）
- サイトのHTML構造変更時にコード修正が必要
- 非エンジニアがセレクタを修正できない

**提案:**

YAML設定ファイルにセレクタを外部化：

```yaml
# config/selectors/mitsui.yaml

mansion:
  title: "h1.headline1"
  price: ".price-value"
  
  table:
    header: "td.table-header.label"
    value: "td.table-value"
  
  field_mappings:
    専有面積: "senyuMensekiStr"
    築年月: "chikunengetsuStr"
    管理費等: "kanrihiStr"
    修繕積立金: "syuzenTsumitateStr"
    間取り: "madori"
    バルコニー面積: "balconyMensekiStr"

kodate:
  title: "h1.headline1"
  price: ".price-value"
  
  table:
    header: "td.table-header.label"
    value: "td.table-value"
  
  field_mappings:
    土地面積: "tochiMensekiStr"
    建物面積: "tatemonoMensekiStr"
    築年月: "chikunengetsuStr"
```

```python
# src/crawler/package/utils/selector_loader.py

import yaml
from pathlib import Path
from typing import Dict, Any

class SelectorLoader:
    """セレクタ設定を読み込むユーティリティ"""
    
    _cache: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    def load(cls, company: str, property_type: str) -> Dict[str, Any]:
        """セレクタ設定を読み込む"""
        cache_key = f"{company}_{property_type}"
        
        if cache_key not in cls._cache:
            config_path = Path(__file__).parent.parent.parent / "config" / "selectors" / f"{company}.yaml"
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            cls._cache[cache_key] = config[property_type]
        
        return cls._cache[cache_key]


# パーサーでの使用
class MitsuiMansionParser(MitsuiParser):
    def __init__(self):
        super().__init__()
        self.selectors = SelectorLoader.load('mitsui', 'mansion')
    
    def _parsePropertyDetailPage(self, item, response):
        # セレクタを設定ファイルから取得
        title_el = response.select_one(self.selectors['title'])
        price_el = response.select_one(self.selectors['price'])
        
        # テーブル抽出
        data = self._extract_table_data(
            response,
            self.selectors['field_mappings'],
            header_selector=self.selectors['table']['header']
        )
        
        # ...
```

**メリット:**
- サイト変更への即応性向上（コード修正不要）
- ロジックと設定の分離
- 非エンジニアでもセレクタ修正が可能
- 設定の一元管理

**実装手順:**
1. `config/selectors/`ディレクトリを作成
2. 各社のYAML設定ファイルを作成
3. `SelectorLoader`クラスを実装
4. パーサーを段階的に移行
5. テストで動作確認

---

### 4.3 APIチェーンのミドルウェア化

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
        """リクエスト前処理。Noneを返すと処理を継続、dictを返すと即座にレスポンスとして返却"""
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
                logger.warning(f"Retrying request (attempt {retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(self.retry_delay)
                response_context['should_retry'] = True
                response_context['retry_count'] = retry_count + 1
        
        return response_context


class LoggingMiddleware(CrawlerMiddleware):
    """ログ記録ミドルウェア"""
    
    async def process_request(self, request_context: dict) -> None:
        logger.info(f"Request: {request_context.get('url')}")
        return None
    
    async def process_response(self, response_context: dict) -> dict:
        logger.info(f"Response: {response_context.get('status')} - {response_context.get('url')}")
        return response_context


# APIクラスでの使用
class MitsuiMansionStartApi(ApiAsyncProcBase):
    """三井のリハウス マンション Start API"""
    
    middlewares = [
        RateLimitMiddleware(delay=1.0),
        RetryMiddleware(max_retries=3, retry_delay=10.0),
        LoggingMiddleware(),
    ]
    
    async def main(self, request):
        # ミドルウェアのprocess_requestを実行
        request_context = {'url': request.url, 'method': 'GET'}
        for middleware in self.middlewares:
            result = await middleware.process_request(request_context)
            if result is not None:
                return result
        
        # 実際の処理
        response = await self._fetch(request.url)
        
        # ミドルウェアのprocess_responseを実行
        response_context = {'status': response.status, 'url': request.url}
        for middleware in reversed(self.middlewares):
            response_context = await middleware.process_response(response_context)
        
        return response
```

**メリット:**
- 横断的関心事の分離
- 柔軟なカスタマイズ（ミドルウェアの追加・削除が容易）
- 既存コードを汚さない拡張
- テストが容易（ミドルウェア単体でテスト可能）

**実装手順:**
1. `src/crawler/package/api/middleware.py`を作成
2. 基本的なミドルウェアを実装
3. `ApiAsyncProcBase`にミドルウェア機構を追加
4. 既存APIクラスを段階的に移行
5. テストで動作確認

---

## Phase 5: 監視・運用の改善（優先度: 低）

### 5.1 構造化ログの導入

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

---

## 実装優先度マトリックス

| 改善項目 | 優先度 | 難易度 | 影響範囲 | 期待効果 | 実装工数 |
|---------|--------|--------|---------|---------|---------|
| **Model Organization Matrix** | 高 | 中 | モデル定義 | 保守性◎ | 2週間 |
| **Dual Storage自動化** | 高 | 低 | パーサー | 品質◎ | 1週間 |
| **型安全性向上（Pydantic）** | 中 | 中 | パーサー全体 | 品質◎ | 2週間 |
| **セレクタ外部化** | 中 | 低 | パーサー | 保守性○ | 1週間 |
| **ミドルウェア化** | 中 | 高 | API層 | 拡張性◎ | 3週間 |
| **構造化ログ** | 低 | 低 | 全体 | 運用性○ | 3日 |

---

## 期待される効果

### 定量的効果

| 指標 | 現状 | Phase 3完了後 | Phase 4完了後 |
|------|------|--------------|--------------|
| モデル定義行数 | 約2,000行 | 約1,500行（-25%） | 約1,200行（-40%） |
| パーサー行数 | 約3,000行 | 約2,800行（-7%） | 約2,500行（-17%） |
| 新規会社追加工数 | 3日 | 2日（-33%） | 1日（-67%） |
| バグ検出率 | 実行時 | 実行時 | コンパイル時+実行時 |

### 定性的効果

**Phase 3完了後:**
- ✅ モデル定義の一貫性向上
- ✅ Dual Storage Patternの自動化による品質向上
- ✅ 新規会社追加の容易化

**Phase 4完了後:**
- ✅ 型安全性による開発効率向上
- ✅ サイト変更への即応性向上
- ✅ 横断的関心事の分離

**Phase 5完了後:**
- ✅ 運用監視の充実
- ✅ 問題の早期発見

---

## 実装ロードマップ

### 短期（1-2週間）
1. Model Organization Matrixの設計・実装
2. Dual Storage自動化の実装
3. 単体テストの実施

### 中期（1ヶ月）
1. Pydanticスキーマの導入
2. セレクタ外部化の実装
3. 統合テストの実施

### 長期（2-3ヶ月）
1. ミドルウェアパターンの導入
2. 構造化ログの導入
3. 本番環境での検証

---

## まとめ

これらの改善により、以下の成果が期待されます：

- **保守性**: モデル定義の重複削減、設定の外部化により大幅向上
- **拡張性**: 新規会社追加工数が3日→1日に短縮
- **品質**: 型安全性とバリデーションにより不正データを事前遮断
- **運用性**: 構造化ログにより問題の早期発見が可能

優先度の高いPhase 3から順次実装することを推奨します。
