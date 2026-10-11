# 全対象サイト中間ページ並行化・階層化 内部設計書 (Issue #870)

## 1. モジュール詳細設計

### 1.1 `src/crawler/package/api/api.py`
#### APIキー新設:
```python
API_KEY_NOMURA_INVEST_KODATE_AREA = '/api/nomura/investment/kodate/area'
API_KEY_NOMURA_INVEST_KODATE_AREA_GCP = '/nomura_investment_kodate_area'
API_KEY_NOMURA_INVEST_APARTMENT_AREA = '/api/nomura/investment/apartment/area'
API_KEY_NOMURA_INVEST_APARTMENT_AREA_GCP = '/nomura_investment_apartment_area'
```

#### 並行度判定の修正 (`_getPararellLimit`):
```python
def _getPararellLimit(self):
    pararell_limit = self._getLocalPararellLimit()
    # 詳細ページクラスのみ動的並行度制御 (AdaptiveConcurrencyController / CLOUD_DETAIL_CONCURRENCY) を適用
    if not isinstance(self, ParseDetailPageAsyncBase):
        return pararell_limit

    company = self._resolve_target_company()

    if os.getenv('IS_CLOUD', ''):
        custom_cloud_limit = os.getenv('CLOUD_DETAIL_CONCURRENCY')
        if custom_cloud_limit and custom_cloud_limit.isdigit():
            limit = int(custom_cloud_limit)
            if company:
                cap = AdaptiveConcurrencyController.SITE_CONCURRENCY_CAPS.get(company)
                if cap is not None:
                    limit = min(limit, cap)
            return limit
        return AdaptiveConcurrencyController.get_effective_concurrency(company=company)

    # Apply WAF caps locally as well if applicable
    if company:
        cap = AdaptiveConcurrencyController.SITE_CONCURRENCY_CAPS.get(company)
        if cap is not None:
            pararell_limit = min(pararell_limit, cap)

    return pararell_limit
```

### 1.2 `src/crawler/package/api/nomura_investment.py`
- `MIDDLE_PARARELL_LIMIT = 3` を新設
- `ParseNomuraInvestAreaFuncAsyncBase(ParseMiddlePageAsyncBase)` を新設:
  - `_getParserFunc`: `self.parser.parseAreaPage`
  - `_getLocalPararellLimit`: `return MIDDLE_PARARELL_LIMIT`
  - `_getCloudPararellLimit`: `return MIDDLE_PARARELL_LIMIT`
- `ParseNomuraInvestListFuncAsyncBase`:
  - `_getLocalPararellLimit`: `return MIDDLE_PARARELL_LIMIT`
  - `_getCloudPararellLimit`: `return MIDDLE_PARARELL_LIMIT`
- `ParseNomuraInvestStartAsyncBase`:
  - `urlList`: 主要エリア展開（東京 `131`、神奈川 `141`、埼玉 `111`、千葉 `121`、大阪 `271`、京都 `261`、愛知 `231` 等）
  - `_getLocalPararellLimit`: `return 5`
  - `_getApiKey`: `AREA` API キーを返却して `AreaFuncAsync` へディスパッチ。
- 派生クラスおよび Registry 登録:
  - `ParseNomuraInvestKodateAreaFuncAsync`, `ParseNomuraInvestApartmentAreaFuncAsync` を登録。

### 1.3 `src/crawler/package/api/mizuho.py`
- `MIDDLE_PARARELL_LIMIT = 3` を定義
- `ParseMizuhoMansionStartAsync`, `ParseMizuhoKodateStartAsync`, `ParseMizuhoTochiStartAsync`, `ParseMizuhoInvestmentStartAsync` の `_getLocalPararellLimit` / `_getCloudPararellLimit` を `return MIDDLE_PARARELL_LIMIT`（3）へ更新。

### 1.4 `src/crawler/package/api/homes.py`
- `MIDDLE_PARARELL_LIMIT = 3` を定義
- `ParseHomesMansionStartAsync`, `ParseHomesKodateStartAsync`, `ParseHomesInvestApartmentStartAsync`, `ParseHomesTochiStartAsync` の `_getLocalPararellLimit` / `_getCloudPararellLimit` を `return MIDDLE_PARARELL_LIMIT`（3）へ更新。

### 1.5 他の中間ページモジュール (`mitsui_investment.py`, `sumifu_investment.py`, `tokyu_investment.py`, `misawa.py`, `misawa_investment.py`, `athome.py`, その他)
- `MIDDLE_PARARELL_LIMIT = 3`（または定数定義・返却値）を設定し、中間ページ処理の並行探索度を 3 に引き上げる。
