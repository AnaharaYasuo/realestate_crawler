---
name: onboard-new-site
description: >-
  新しい不動産サイト（会社・ポータル）のクローラー、パーサー、DBモデル、URLルーター、タスク分散、
  およびML価格推定・割安判定パイプラインへの統合配線をゼロタッチで完全自律実装・検証するためのスキルです。
  ユーザーが不動産サイトのURLや名称を提示してクローラー追加・サイト対応を求めた際に使用します。
---

# 新規不動産サイト完全自律オンボーディングスキル (Zero-Touch Site Onboarding)

不動産サイト（会社名・URL・対象物件種別）が提示された際、クローラー実装から ML 価格推定・割安判定・Cloud Workflows タスク分散への反映までを **漏れゼロ（10箇所完全配線）** で自律完遂するための標準手順です。

## 必須遵守ルール（階層別 AGENTS.md）
- モデル定義: [`src/crawler/package/models/AGENTS.md`](../../../src/crawler/package/models/AGENTS.md)（4基底モデル継承・標準フィールド型統一）
- パーサー実装: [`src/crawler/package/parser/AGENTS.md`](../../../src/crawler/package/parser/AGENTS.md)（1項目1メソッド・`converter.parse_price` 使用・4層種別防衛）
- ML統合: [`src/crawler/package/ml/AGENTS.md`](../../../src/crawler/package/ml/AGENTS.md)（`SiteRegistry` 経由の自動データローダー・評価ターゲット統合）

## 実行ステップ

### Step 1: 対象サイトの構造調査（Subagent 活用推奨）
1. `research` サブエージェント（または直接取得）により対象サイトの一覧ページ・詳細ページの生HTMLを取得し、[`docs/2_crawlers/_standards/site_survey_checklist.md`](../../../docs/2_crawlers/_standards/site_survey_checklist.md) に基づいて以下を特定する：
   - 静的HTML（`aiohttp`）か動的レンダリング/WAF（`Playwright`）か
   - ページネーション方式と一覧カードの価格・URLセレクタ
   - 詳細ページのスペック表構造（`th`/`td` または `dt`/`dd`）と物件種別表記
2. 調査結果を `docs/2_crawlers/sites/site_structure_<company>.md` に作成する。

### Step 2: スキャフォールド生成と `SiteRegistry` 一元登録
1. スキャフォールドスクリプトを実行して Model / Parser / API / Selector YAML / Unit Test の雛形を生成する：
   - [`scripts/scaffold_site.py`](scripts/scaffold_site.py)
2. [`src/crawler/package/site_registry.py`](../../../src/crawler/package/site_registry.py) に `SiteDefinition` を登録し、以下の全10箇所へ自動配線させる：
   - `package/models/<company>.py`（`MansionBaseModel` / `KodateBaseModel` / `TochiBaseModel` / `InvestmentBaseModel` 継承）
   - `package/parser/<company>Parser.py`（`*ParserBase` 継承・全 `@abstractmethod` 実装）
   - `package/api/<company>.py` & `api_registry.py`
   - `main.py` (`get_dispatch_map`)
   - `crawl_jobs.py` (`CRAWL_JOBS`)
   - `task_distribution.py` (`_assign_8_task_index`)
   - `url_router.py` (`UrlRouter`)
   - `ml/constants.py` (`COMPANIES`)
   - `ml/evaluation/targets.py`

### Step 3: 配線完全性 ＆ 動的生HTML検証 ＆ ハーネスゲート実行
1. 配線検証スクリプトを実行し、クローラーから ML 学習・推論・お宝判定までの配線漏れが 0 件であることを確認する：
   - [`scripts/verify_site_wiring.py`](scripts/verify_site_wiring.py)
2. 動的アクティブ生HTML検証（3件スモーク ➔ 20件拡張）および `pytest src/crawler/tests/unit/test_architecture_harness.py` を実行し、種別誤判定 0%・純パース時間基準内・全フィールド充填率基準内であることを検証する。
