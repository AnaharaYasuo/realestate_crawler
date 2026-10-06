# 内部設計書: 野村投資用戸建て誤ルーティング修復および非物件URLノイズ抑止

## 1. クラス・関数変更仕様

### 1.1 `NomuraInvestmentApartment` & `NomuraInvestmentKodate` (`src/crawler/package/models/nomura.py`)
- **`NomuraInvestmentApartment.soukosu`**:
  - `soukosu = models.IntegerField(null=True, blank=True)` に変更。
  - 総戸数未記載時および誤判定時の `ValidationError: Invalid fields: soukosu` を物理根絶。
- **`NomuraInvestmentKodate.madori`**:
  - `madori = models.TextField(blank=True, default="")` を追加。
  - 戸建て特有の間取り情報を欠損なく保持。

### 1.2 `UrlRouter` (`src/crawler/package/utils/url_router.py`)
- **野村投資用戸建てルート追加**:
  ```python
  {
      "pattern": re.compile(r"nomu\.com/pro/"),
      "site": "nomura",
      "property_type": "invest_kodate",
      "parser_module": NOMURA_PARSER_MODULE,
      "parser_cls": "NomuraInvestmentKodateParser",
      "model_module": NOMURA_MODEL_MODULE,
      "model_cls": "NomuraInvestmentKodate",
  },
  ```
  - `nomu.com/pro/` パスにおいて、動的判定が `invest_kodate` または `kodate` の場合に `NomuraInvestmentKodateParser` を正しく解決可能にする。

### 1.3 `PropertyTypeDetector` (`src/crawler/package/utils/property_type_detector.py`)
- **`_match_keywords` & `_detect_rule_based` の投資戸建て判定連携**:
  - 投資シグナル（利回り・オーナーチェンジ）が存在する場合でも、テキスト内に戸建てキーワード（`KODATE_KEYWORDS`）が存在する場合は `apartment` に一律丸め込まず、`invest_kodate`（または `kodate`）として判定。
  - または `detect_investment_type` で `"Kodate"` が返るケースにおいて `invest_kodate` を返却するルートを整合。

### 1.4 `ParserBase` (`src/crawler/package/parser/baseParser.py`)
- **ノイズURLトークンの追加**:
  - `_is_non_property_href`: `skip_tokens` に `'/baikyaku/'` を追加。
  - `_reject_non_property_url`: `skip_parts` に `'/baikyaku/'` を追加。
