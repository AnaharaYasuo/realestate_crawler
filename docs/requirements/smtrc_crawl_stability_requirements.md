# SMTRCクローリング安定化・全物件種別0件取得防止要件定義書 (Issue #827)

## 1. 概要
三井住友トラスト不動産（`smtrc`）の定期クローリングジョブにおいて、`mansion`、`tochi`、`kodate` で新規取得が0件となりジョブ失敗（Zero count failure）として判定・通知された不具合を解消し、居住用および投資用の全種別において安定的に物件詳細情報を取得・保存できるようにする。

## 2. 背景・課題
- **事象**:
  - `smtrc - mansion`: 新規取得 0 件 (Job 4/89)
  - `smtrc - tochi`: 新規取得 0 件 (Job 4/89)
  - `smtrc - kodate`: 新規取得 0 件 (Job 4/89)
- **原因**:
  - SMTRC の一覧ページ（`https://smtrc.jp/list/listViewLive/index?...`）取得時、相手方 Web サーバー・WAF による Bot 検知（HTTP 403 Forbidden、または 144 bytes 程度の空 HTML 応答）が発生。
  - 従来の一覧取得ロジック（`aiohttp` ベースの単純 GET）では WAF 応答時に例外発生または一覧リンク 0 件判定となり、巡回が即時終了していた。

## 3. 要件一覧
### 機能要件 (FR)
- **FR-001**: SMTRC の一覧および詳細ページ取得時、WAF 403 や微小コンテンツ（<1000 bytes）を検知した場合、Playwright ステルスブラウザ（Chromium ヘッドレス + `navigator.webdriver` 隠蔽）による自動フォールバックを行うこと。
- **FR-002**: 一覧ページから抽出された詳細リンク（`/detail/CompareDetails?propertyCode=...`）が正常にパース・保存されること。
- **FR-003**: `mansion`, `kodate`, `tochi`, `investment` の全 4 種別のパーサー（`SmtrcMansionParser`, `SmtrcKodateParser`, `SmtrcTochiParser`, `SmtrcInvestmentParser`）が、それぞれの種別エンティティ（`SmtrcMansion`, `SmtrcKodate`, `SmtrcTochi`, `SmtrcInvestment`）を正常に生成・パースできること。

### 非機能要件 (NFR)
- **NFR-001 (安定性・回復性)**: WAF 403 や微小コンテンツ発生時、最大 2 回まで Playwright ステルス取得を試行し、回復不能な場合のみ明示的な例外を発行すること。
- **NFR-002 (パフォーマンス・タイムアウト)**: 一覧巡回タイムアウトは各 2400 秒、詳細タイムアウトは 60 秒を遵守すること。
- **NFR-003 (回帰防止)**: 単体テストおよび実機統合テストにより、WAF フォールバックと全種別のエンティティ生成が常時保証されていること。
