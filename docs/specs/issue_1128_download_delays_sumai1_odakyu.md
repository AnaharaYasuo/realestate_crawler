# 仕様書: Issue #1128 odakyu および sumai1 への Download Delay 設定による接続タイムアウト防止

## 1. 概要
`odakyu`（小田急不動産）および `sumai1`（住友林業ホームサービス）において、数十ページに及ぶ一覧巡回や詳細ページ連続取得時に相手側Webサーバー・CDNの接続制限キューや一時的タイムアウトが発生する事象を防止するため、リクエスト間隔（`SITE_DOWNLOAD_DELAYS`）に 0.5 秒のウェイトを設定し、紳士的かつ安定したクローリングを実現する。

## 2. 変更仕様
- `src/crawler/package/api/api.py`:
  - `SITE_DOWNLOAD_DELAYS` に以下を追加:
    - `"sumai1": 0.5`
    - `"odakyu": 0.5`
- `src/crawler/tests/unit/test_download_delays_1128.py`:
  - `SITE_DOWNLOAD_DELAYS` に `sumai1` と `odakyu` が適切に 0.5 秒で設定されていることを検証するユニットテストを追加。

## 3. 受入基準 (Acceptance Criteria)
- [x] `SITE_DOWNLOAD_DELAYS` に `sumai1: 0.5` と `odakyu: 0.5` が設定されていること。
- [x] ユニットテストが正常に合格すること。
- [x] CI（単体/結合/ML/実クロール保証/SonarCloud/Trivy/Review Gate）が合格すること。
- [x] `production` ブランチへのリリース PR がマージされること。
