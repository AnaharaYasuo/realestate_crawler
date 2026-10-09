# クローラー巡回安定化・動的種別集計・WAF/タイムアウト耐性強化 要件定義書 (Issues #819, #820, #821, #822)

## 1. 概要
本番および定期クローリングにおいて検出された以下の4つの課題を解消し、パイプラインの安定性とデータ整合性を担保する。
1. **Tokyu / Sumifu 戸建て投資ジョブにおける動的種別判定時の保存件数集計不整合 (Issues #819, #821)**:
   - サイト側の一覧ページに投資用マンションや一棟アパートが混在しており、`PropertyTypeDetector` により適正なアパート種別（`TokyuInvestmentApartment`, `SumifuInvestmentApartment`）へ動的に切り替えて保存されている。
   - しかし、`run_all_crawlers.py` の `get_count_for_job` がジョブ名（`invest_kodate`）に対応するテーブル（`tokyu_investment_kodate`, `sumifu_investment_kodate`）のみをカウントしていたため、成果が保存されているにもかかわらず 0件取得失敗と判定されていた。
2. **SMTRC における WAF ブロック/軽量HTML応答検知とリトライ強化 (Issue #820)**:
   - SMTRC サーバーへのリクエスト時、144 bytes などの微小なブロック/空HTMLが返された場合にそのまま処理が進み、0件取得となっていた。
   - Playwright によるステルス取得を導入し、レスポンス長が閾値（1000 bytes 未満）の場合にはリトライする耐性を付与する。
3. **Sumai1 における一時的接続遅延時のタイムアウト耐性向上 (Issue #822)**:
   - Sumai1 のマンション巡回時、相手サーバーの遅延により15秒タイムアウトが連続3回発生して `ServerDownException`（Exit Code 1）で即死していた。
   - バックオフ待機とリトライ、および適切なタイムアウト秒数の設定により耐性を向上させる。

## 2. 目的とスコープ
* **目的**:
  1. 動的種別切り替えが発生する投資ジョブにおける正確な件数集計の実現。
  2. WAF・アクセス制限による微小バイト応答時の自律リトライによる0件取得防止。
  3. 一時的なネットワーク/相手先遅延に対する Fast-Fail 閾値の適正化。
* **スコープ**:
  - `src/crawler/scripts/ops/run_all_crawlers.py`
  - `src/crawler/package/parser/tokyuParser.py`
  - `src/crawler/package/parser/smtrcParser.py`
  - `src/crawler/package/parser/sumai1Parser.py`
  - `src/crawler/package/parser/baseParser.py`
  - `src/crawler/tests/unit/` 配下のテストコード

## 3. 要件一覧
* **REQ-819-01**: `run_all_crawlers.py` の `get_count_for_job` において、`invest_kodate` ジョブの実行結果確認時、動的種別判定で `apartment` / `invest_apartment` テーブルに保存された件数も関連件数として加算集計すること。
* **REQ-819-02**: `tokyuParser.py` の `TokyuInvestmentKodateParser` に `property_type = 'invest_kodate'` を明示的に設定し、基底クラスの `investment` による誤判定を防止すること。
* **REQ-820-01**: `smtrcParser.py` において、取得したレスポンスのサイズが 1000 bytes 未満の場合は WAF/ブランク応答と判定し、Playwright ステルスモードによるリトライを実行すること。
* **REQ-822-01**: `sumai1Parser.py` において、タイムアウト設定を最適化（20秒等）し、一時的な相手先遅延による `ServerDownException` を防止すること。
