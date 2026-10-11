# 全対象サイト中間ページ並行化・階層化 外部設計書 (Issue #870)

## 1. 外部インターフェースおよび設定仕様

### 1.1 野村投資用（nomura_investment）APIキーおよび階層構造
- 新規APIキー定義 (`src/crawler/package/api/api.py`):
  ```python
  API_KEY_NOMURA_INVEST_KODATE_AREA = '/api/nomura/investment/kodate/area'
  API_KEY_NOMURA_INVEST_KODATE_AREA_GCP = '/nomura_investment_kodate_area'
  API_KEY_NOMURA_INVEST_APARTMENT_AREA = '/api/nomura/investment/apartment/area'
  API_KEY_NOMURA_INVEST_APARTMENT_AREA_GCP = '/nomura_investment_apartment_area'
  ```
- 探索階層フロー:
  `Start` ➔ `Area` ➔ `List` ➔ `Detail`
  - `Start`: `ParseNomuraInvestKodateStartAsync` / `ParseNomuraInvestApartmentStartAsync`（主要エリアURL一覧を展開）
  - `Area`: `ParseNomuraInvestKodateAreaFuncAsync` / `ParseNomuraInvestApartmentAreaFuncAsync`（エリア内の一覧ページURLを展開、並列度3）
  - `List`: `ParseNomuraInvestKodateListFuncAsync` / `ParseNomuraInvestApartmentListFuncAsync`（物件詳細URLを展開・次ページネーション、並列度3）
  - `Detail`: `ParseNomuraInvestKodateDetailFuncAsync` / `ParseNomuraInvestApartmentDetailFuncAsync`（詳細パース・保存、WAF制御適用）

### 1.2 全サイトの中間ページ並行度設定 (`MIDDLE_PARARELL_LIMIT = 3`)
以下の各モジュールにおける中間ページ探索クラスの `_getLocalPararellLimit()` / `_getCloudPararellLimit()` を **3** に統一：
- `nomura_investment.py`: Start (5), Area (3), List (3)
- `mizuho.py`: Start (3)
- `homes.py`: Start (3)
- `mitsui_investment.py`: Start (3), Area (3), List (3)
- `sumifu_investment.py`: Start (3), List (3)
- `tokyu_investment.py`: Start (3), List (3)
- `misawa.py`: List (3)
- `misawa_investment.py`: List (3)
- `athome.py`, `smtrc.py`, `sumai1.py`, `odakyu.py`, `totate.py`, `afr.py`, `daikyo.py`, `daiwa.py`, `heim.py`, `keikyu.py`, `keio.py`, `keisei.py`, `rearie.py`, `seibu.py`, `sekisui.py`, `sotetsu.py`, `sumirin.py`: Start (3)

### 1.3 `ApiAsyncProcBase` の並行度評価分岐
- `package/api/api.py`:
  - `_getPararellLimit()` において、自身が `ParseDetailPageAsyncBase` のサブクラスである場合にのみ動的詳細並行度制御（`AdaptiveConcurrencyController` / `CLOUD_DETAIL_CONCURRENCY`）を適用。
  - 中間ページクラス（`ParseMiddlePageAsyncBase` およびその他の探索クラス）では、自身に設定された静的並行度（`_getLocalPararellLimit()` = 3）をそのまま使用。
