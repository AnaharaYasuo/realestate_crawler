# 要件定義: Safety-Net通知文言改善および住友不動産投資用戸建てセレクター修復

## 1. 背景と課題
- **Safety-Net通知の表現課題**:
  - 定期リソース停止監視スクリプト（`ensure_resources_stopped.py`）において、クローラーやMLパイプラインが正常稼働中のためProxySQLを稼働維持する際のSlack通知文言が「クローラー/MLパイプライン正常実行中のためProxySQL停止をスキップしました」となっている。
  - 「スキップ」という表現が、処理の一部が失敗または未完了になったかのような誤解を運用者に与えるため、「起動を継続しました」という明確かつ肯定的な表現へ改善が求められている。
- **住友不動産（sumifu）投資用戸建てのセレクター欠損**:
  - `sumifu.yaml` に `invest_kodate` のキーが存在しないため、`SelectorLoader.load('sumifu', 'invest_kodate')` を実行した際に `KeyError` が発生する。
  - `sumifu` の投資物件（戸建て・アパート・一棟）は同一の検索・詳細UI（`/pro/` 配下）を共有しており、`invest_kodate` および `invest_apartment` も共通の投資物件セレクター（`investment`）の定義を参照・継承して動作する必要がある。

## 2. 要件一覧
- **REQ-001 (Slack通知文言改善)**:
  - `ensure_resources_stopped.py` における GCE 単一インスタンス監視および MIG 監視の両方で、正常ジョブ稼働中の ProxySQL 稼働継続通知文言を「クローラー/MLパイプライン正常実行中のためProxySQLの起動を継続しました」に変更する。
- **REQ-002 (セレクター設定の拡充)**:
  - `config/selectors/sumifu.yaml` に `invest_kodate` および `invest_apartment` の定義を追加し、`SelectorLoader.load('sumifu', 'invest_kodate')` および `SelectorLoader.load('sumifu', 'invest_apartment')` が正常にセレクター辞書を取得できるようにする。
- **REQ-003 (後方互換性とテスト適合)**:
  - 既存の Safety-Net ユニットテスト（`test_ensure_resources_stopped.py`, `test_crawler_safety_net_hourly_664.py`）を新文言に合わせて更新し、PASSさせる。
  - 新規に `sumifu` 投資用戸建て・アパートのセレクターロードおよびパース検証を行うテストを追加する。
