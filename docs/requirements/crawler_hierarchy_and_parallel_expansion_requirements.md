# 全対象サイト中間ページ並行化・階層化 要件定義書 (Issue #870)

## 1. 概要 / ユーザーストーリー
* **ユーザーとして**: 不動産クローラー運用管理者として
* **目的**: 調査済みの全対象サイト（野村投資、みずほ、ホームズ、三井投資、住友投資、東急投資、ミサワ、アットホーム、および中小仲介・電鉄系など）の中間ページ探索を多階層化・並行探索化（`MIDDLE_PARARELL_LIMIT = 3`）する。
* **価値**: これまでマンション系のみに限定されていた中間ページ並行化を全物件種別（戸建・土地・投資用）および未対応クローラー全社に水平展開し、直列探索による巡回ボトルネックを抜本解消してシステム全体のスループットを最大化する。

## 2. 機能要件 (FR)

### FR-870-001: 野村投資（nomu.com/pro）の中間階層化および並行化
- `nomura_investment.py` において、`Start ➔ List ➔ Detail` の直列構造から、`AreaFuncAsync`（エリア階層）を新設した `Start ➔ Area ➔ List ➔ Detail` の4階層構造へ再編。
- `ParseNomuraInvestStartAsyncBase` で主要エリア（東京 `131`、神奈川 `141`、埼玉 `111`、千葉 `121`、大阪 `271`、京都 `261`、愛知 `231` 等）を投入し、`AreaFuncAsync`（`MIDDLE_PARARELL_LIMIT = 3`）で並行探索する。

### FR-870-002: みずほ不動産販売（mizuho-re.co.jp）の探索並行化
- `mizuho.py` の中間ページクラス（`ParseMizuhoMansionStartAsync`, `ParseMizuhoKodateStartAsync`, `ParseMizuhoTochiStartAsync`, `ParseMizuhoInvestmentStartAsync`）の並行探索リミットを 1 から **3**（`MIDDLE_PARARELL_LIMIT = 3`）へ引き上げる。

### FR-870-003: ホームズ（homes.co.jp）の探索並行化
- `homes.py` の中間ページクラス（`ParseHomesMansionStartAsync`, `ParseHomesKodateStartAsync`, `ParseHomesInvestApartmentStartAsync`, `ParseHomesTochiStartAsync`）の並行探索リミットを 1 から **3**（`MIDDLE_PARARELL_LIMIT = 3`）へ引き上げる。

### FR-870-004: 大手投資用（三井・住友・東急・ミサワ）および中小・電鉄系クローラー全社の並行度適正化
- `mitsui_investment.py`, `sumifu_investment.py`, `tokyu_investment.py`, `misawa_investment.py`, `misawa.py` の中間ページ並行探索リミット（Area / List）を **3**（`MIDDLE_PARARELL_LIMIT = 3`）へ引き上げる。
- `athome.py`, `smtrc.py`, `sumai1.py`, `odakyu.py`, `totate.py`, `afr.py`, `daikyo.py`, `daiwa.py`, `heim.py`, `keikyu.py`, `keio.py`, `keisei.py`, `rearie.py`, `seibu.py`, `sekisui.py`, `sotetsu.py`, `sumirin.py` の中間ページ並行探索リミットを 1 から **3**（`MIDDLE_PARARELL_LIMIT = 3`）へ適正化する。

### FR-870-005: 共通基底（`api.py`）における詳細並行度と中間並行度の明確な分離
- `ApiAsyncProcBase._getPararellLimit()` において、`CLOUD_DETAIL_CONCURRENCY` / `AdaptiveConcurrencyController` の詳細動的制御を詳細ページクラス（`ParseDetailPageAsyncBase`）に限定適用し、中間ページクラス（`ParseMiddlePageAsyncBase`）では `_getLocalPararellLimit()` の設定値（3）を尊重して安定した並行探索を保証する。

## 3. 非機能要件 (NFR)
- **NFR-870-001 (クローリング所要時間の大幅短縮)**: 全社の中間ページ探索並行化により、中間巡回時間が従来の約1/3に短縮されること。
- **NFR-870-002 (WAF/DoS過負荷防止の堅持)**: 詳細ページへの最終ディスパッチは `AdaptiveConcurrencyController` のサイト別WAFキャップおよびレートリミットディレイ（`SITE_DOWNLOAD_DELAYS`）によって確実に保護され、相手先サーバーへのスパイク負荷を防止すること。
- **NFR-870-003 (単体・回帰テスト全件合格)**: 既存のテスト、新規並行度テスト、およびミューテーションテストが全て合格すること。
