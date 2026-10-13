# 要件定義書: 継続実行時のパース・モデル不整合解消及びサーキットブレイカー誤爆防止 (Issue #898)

## 1. 背景・目的
常時ローカル本番実行（Cloud SQLへの継続保存・差分判定・推論）において、クローリングパイプラインが途中で異常中断・停止せず、常に最新情報を取得・保存し続けられる高可用性を担保する。

## 2. 課題
1. **三井詳細ページのサーキットブレイカー誤爆**:
   - `baseParser._getContent` において、`self.consecutive_timeouts` がパーサーインスタンス単位で累積するため、複数の異なる物件で発生した一時的なタイムアウトが合算され、3回に達した時点で `ServerDownException` が送出されパイプライン全体が中断してしまう。
2. **モデル定義の `blank=True` 欠落による `full_clean()` バリデーションエラー**:
   - 住友戸建（`SumifuKodate`）: `chiikiChiku`, `boukaChiiki`, `saikenchiku`, `sonotaChiiki` が物件ページに記載されていない場合、Django モデルのデフォルト（`blank=False`）により `ValidationError` が発生し、保存がスキップされてエラー扱いになる。
   - 三井マンション（`MitsuiMansion`）: 管理費・修繕積立金が未定・非公開の物件で `kanrihi`, `syuzenTsumitate`（整数）が `null=True` であるにもかかわらず `blank=True` が未指定のため `ValidationError` になる。
   - 三井投資用（`MitsuiInvestmentApartment`）: 総戸数文字列（`soukosuStr`）に `blank=True` がない。

## 3. 機能要件
* **FR-898-1**: 単一URL（ページ）のリトライ試行におけるタイムアウトと、サーバー全体が停止している「連続3回タイムアウト」の追跡を分離し、個別物件の一時タイムアウトでサーキットブレイカーが誤爆しないようにする。
* **FR-898-2**: 各不動産モデル（`SumifuKodate`, `MitsuiMansion`, `MitsuiInvestmentApartment`）の任意表示スペック項目に対して `blank=True` を付与し、情報未掲載物件でも正常に `full_clean()` を通過・DB保存できるようにする。

## 4. 受入基準
* [ ] 単一物件の取得失敗が他物件のタイムアウト累積に影響を与えず、3回のリトライ失敗後は `LoadPropertyPageException`（スキップ対象）として処理され、パイプラインが中断しないこと。
* [ ] 記載のない任意スペック（地域地区、防火地域、再建築、管理費、修繕積立金等）が存在する物件でもバリデーションエラーにならず Cloud SQL に保存できること。
* [ ] 関連ユニットテストおよびミューテーションテストがすべて合格すること。
