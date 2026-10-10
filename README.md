# Realestate Crawler

[![DeepWiki](https://deepwiki.com/badge-maker?url=https%3A%2F%2Fdeepwiki.com%2FAnaharaYasuo%2Frealestate_crawler)](https://deepwiki.com/AnaharaYasuo/realestate_crawler)

このプロジェクトは、主要不動産会社・ポータルサイト計22社以上から不動産物件情報を自動的に収集（スクレイピング）し、データベースに保存するためのツールです。

## 概要

### システムの目的

本システムは以下の3つの主要目的を持ちます：

1. **データ収集**: 22社以上の不動産サイトから非同期HTTPリクエストとHTML解析により物件情報を自動取得
2. **データ永続化**: 正規化されたデータベーススキーマ（16-17テーブル）に変換・保存
3. **投資評価・スクリーニング**: 周辺統計（地価・所得・駅力）、機械学習による理論価格予測、Geminiによる画像評価、および**「積算価格評価」「収支・キャッシュフロー・DSCR/CoCローンシミュレーション」**を行い、総合投資スコアとして可視化し、基準値を超える優良物件をSlackチャンネルへ自動でアラート通知します。

### 対応サイトと物件種別

| 会社 | 居住用物件 | 投資用物件（収集対象） | 備考 |
|------|-----------|---------------------|------|
| 三井のリハウス | マンション・戸建て・土地 | 一棟マンション・一棟アパート・戸建て | 区分マンション、ビル、店舗等は対象外 |
| 住友不動産販売 | マンション・戸建て・土地 | 一棟マンション・一棟アパート・投資用戸建 | 12種類中3種類を収集 |
| 東急リバブル | マンション・戸建て・土地 | マンション一棟・アパート | 戸建ては対象外（サイトに物件種別なし） |
| 野村の仲介+ | マンション・戸建て・土地 | 一棟マンション・一棟アパート・投資用戸建 | 11種類中3種類を収集 |
| ミサワホーム不動産 | マンション・戸建て・土地 | 一棟マンション・一棟アパート | 戸建ては対象外（サイトに物件種別なし） |
| 三井住友トラスト不動産 | マンション・戸建て・土地 | 一棟マンション・一棟アパート・一棟ビル等 | 投資用物件に対応 |
| 三菱UFJ不動産販売 | マンション・戸建て・土地 | 一棟マンション・一棟アパート・一棟ビル等 | 投資用物件に対応 |
| みずほ不動産販売 | マンション・戸建て・土地 | 一棟マンション・一棟アパート・一棟ビル等 | 投資用物件に対応 |
| 小田急不動産 | マンション・戸建て・土地 | 一棟マンション・一棟アパート・一棟ビル等 | 投資用物件に対応 |
| 東京建物不動産販売 | マンション・戸建て・土地 | N/A | 居住用3種別を収集 |
| 大和ハウスリアルエステート | マンション・戸建て・土地 | N/A | 居住用3種別を収集 |
| 住友林業ホームサービス | マンション・戸建て・土地 | 一棟マンション・一棟アパート等 | 4種別を収集 |
| セキスイハイム不動産 | マンション・戸建て・土地 | N/A | 居住用3種別を収集 |
| パナソニックホームズ不動産 | マンション・戸建て・土地 | N/A | 居住用3種別を収集 |
| 京王不動産 | マンション・戸建て・土地 | N/A | 居住用3種別を収集 |
| 西武不動産 | マンション・戸建て・土地 | N/A | 居住用3種別を収集 |
| 京急不動産 | マンション・戸建て・土地 | N/A | 居住用3種別を収集 |
| 相鉄不動産販売 | マンション・戸建て・土地 | N/A | 居住用3種別を収集 |
| 京成不動産 | マンション・戸建て・土地 | N/A | 居住用3種別を収集 |
| 大京穴吹不動産 | マンション・戸建て・土地 | N/A | 居住用3種別を収集 |
| LIFULL HOME'S | マンション・戸建て・土地 | 一棟アパート | ポータルサイト |
| アットホーム | マンション・戸建て・土地 | 一棟アパート | ポータルサイト |

**収集対象**: 主要不動産会社各社の居住用3種別（マンション・戸建て・土地）＋投資用物件

> [!NOTE]
> **投資用物件の収集対象**
> - 一棟マンション（RC造・鉄骨造などの集合住宅一棟）
> - 一棟アパート（木造・軽量鉄骨造などの集合住宅一棟）
> - 戸建て（投資用一戸建て）※サイトにより対応状況が異なる
> 
> 区分マンション、ビル、店舗/事務所、工場/倉庫、ホテル/旅館などは収集対象外です。
> 各サイトの全物件種別については、[収益不動産サイト物件種別一覧](docs/requirements/investment_property_types.md)を参照してください。

### システムの特徴

ローカルAPIサーバーを構築し、HTTPリクエストを受け取ることで各サイトのクローリング・解析処理を実行します。収集したデータはMySQLデータベースへ保存されます。
本プロジェクトでは [Task](https://taskfile.dev/) と [Docker Compose](https://docs.docker.com/compose/) を使用して環境構築および実行を行います。

### Slackアラート通知の設定

基準スコアを上回る優良物件をSlackへ通知するため、`.env` ファイルに以下の環境変数を設定します（`.env.example` 参照）：
- `SLACK_BOT_TOKEN`: `xoxb-...` 形式のSlackボットトークン
- `SLACK_CHANNEL_ID`: `C...` 形式の通知先チャンネルID

## 前提条件

*   [Docker Desktop](https://www.docker.com/products/docker-desktop) がインストールされ、起動していること
*   [Task](https://taskfile.dev/installation/) コマンドがインストールされていること

## セットアップ & 起動

### セットアップフロー概要

`task init` コマンドは以下の3ステップを自動実行します：

1. **Dockerイメージビルド**
   - `python:3.11-slim` ベースイメージ使用
   - MySQLクライアントライブラリのインストール
   - Python依存関係のインストール（aiohttp, BeautifulSoup4, Django等）

2. **コンテナ起動**
   - `app` コンテナ: アプリケーションサーバー（ポート8000）
   - `mysql` コンテナ: データベースサーバー（ポート3306）

3. **データベース初期化**
   - `src/crawler/db_setup.py` を実行
   - Djangoマイグレーションにより16-17テーブルを作成

### 初回セットアップ

初回実行時や、環境をリセットしてクリーンな状態で開始したい場合は `init` タスクを使用します。

```bash
task init
```

### 期待される出力

```bash
[+] Building 23.5s (10/10) FINISHED
[+] Running 2/2
 ✔ Container realestate_crawler-mysql-1  Started
 ✔ Container realestate_crawler-app-1    Started
Operations to perform:
  Apply all migrations: package
Running migrations:
  Applying package.0001_initial... OK
```

### 検証方法

コンテナが正常に起動しているか確認：

```bash
docker compose ps
```

両方のコンテナが `Up` 状態であればセットアップ成功です。

## 使用方法

### 1. サーバーの起動 (通常時)

すでにセットアップが完了しており、サーバーを再起動したい場合は以下のコマンドを使用します。

```bash
task default
```
バックグラウンドでサーバーが起動し、`http://localhost:8000` で待機状態になります。

### 2. クローラーの実行

`task crawl` コマンドでクローラーを起動します。`COMPANY` (対象サイト) と `TYPE` (物件種別) を指定してください。

**実行例:**

```bash
# 三井のリハウス / マンション
task crawl COMPANY=mitsui TYPE=mansion
```

**パラメータ:**

*   **COMPANY**:
    *   `mitsui`: 三井のリハウス
    *   `sumifu`: 住友不動産販売
    *   `tokyu`: 東急リバブル
    *   `nomura`: ノムコム・プロ (投資用)
    *   `misawa`: ミサワホーム不動産
    *   `smtrc`: 三井住友トラスト不動産
    *   `sumai1`: 三菱UFJ不動産販売 (住まい1)
    *   `sekisui`: 積水ハウス不動産 (BIZ投資)
    *   `afr`: 旭化成不動産レジデンス (ヘーベル)
    *   `mizuho`: みずほ不動産販売
    *   `odakyu`: 小田急不動産
    *   `totate`: 東京建物不動産販売
    *   `daiwa`: 大和ハウスリアルエステート
    *   `sumirin`: 住友林業ホームサービス (すみなび)
    *   `heim`: セキスイハイム不動産 (住むハイム)
    *   `rearie`: パナソニックホームズ不動産 (リアリエ)
    *   `keio`: 京王不動産
    *   `seibu`: 西武不動産 (西武の住まい情報)
    *   `keikyu`: 京急不動産 (京急の住まい)
    *   `sotetsu`: 相鉄不動産販売
    *   `keisei`: 京成不動産 (京成土地建物)
    *   `daikyo`: 大京穴吹不動産 (オリックス)
    *   `homes`: LIFULL HOME'S (ポータル)
    *   `athome`: アットホーム (ポータル)
*   **TYPE**:
    *   `mansion`: 中古マンション
    *   `tochi`: 土地
    *   `kodate`: 戸建て

**対応表:**

| COMPANY | TYPE |
| :--- | :--- |
| `mitsui` | `mansion`, `tochi`, `kodate`, `investment` |
| `sumifu` | `mansion`, `tochi`, `kodate`, `investment` |
| `tokyu` | `mansion`, `tochi`, `kodate`, `investment` |
| `nomura` | `mansion`, `tochi`, `kodate`, `investment` |
| `misawa` | `mansion`, `tochi`, `kodate`, `investment` |
| `smtrc` | `mansion`, `tochi`, `kodate` |
| `sumai1` | `mansion`, `tochi`, `kodate` |
| `sekisui` | `mansion`, `tochi`, `kodate` |
| `afr` | `mansion`, `tochi`, `kodate` |
| `mizuho` | `mansion`, `tochi`, `kodate` |
| `odakyu` | `mansion`, `tochi`, `kodate` |
| `totate` | `mansion`, `tochi`, `kodate` |
| `daiwa` | `mansion`, `tochi`, `kodate` |
| `sumirin` | `mansion`, `tochi`, `kodate`, `investment` |
| `heim` | `mansion`, `tochi`, `kodate` |
| `rearie` | `mansion`, `tochi`, `kodate` |
| `keio` | `mansion`, `tochi`, `kodate` |
| `seibu` | `mansion`, `tochi`, `kodate` |
| `keikyu` | `mansion`, `tochi`, `kodate` |
| `sotetsu` | `mansion`, `tochi`, `kodate` |
| `keisei` | `mansion`, `tochi`, `kodate` |
| `daikyo` | `mansion`, `tochi`, `kodate` |
| `homes` | `mansion`, `tochi`, `kodate`, `invest_apartment` |
| `athome` | `mansion`, `tochi`, `kodate`, `invest_apartment` |

---

## システムアーキテクチャ概要

### Fire-and-Forget パターン

本システムは「Fire-and-Forget」方式の非同期API呼び出しを採用しています。

**特徴:**
- **再帰的呼び出し**: Start → Region → List → Detail の各ステップが次のステップをHTTPリクエストで起動
- **即時レスポンス**: 各APIは処理完了を待たず、即座にHTTP 200を返却
- **タイムアウト許容**: 3秒のタイムアウト設定。接続確立時点で成功とみなす
- **サーバーレス対応**: Google Cloud Functions等での分散実行が可能

**処理フロー:**
```
User → task crawl
  ↓
Start API (HTTP 200即時返却)
  ↓ (非同期POST)
Region API (HTTP 200即時返却)
  ↓ (非同期POST × N地域)
List API (HTTP 200即時返却)
  ↓ (非同期POST × M物件)
Detail API → DB保存
```

### 並列処理設定

| パラメータ | 値 | 説明 |
|-----------|-----|------|
| `FIRE_AND_FORGET_TIMEOUT` | 3.0秒 | 次ステップ起動時のタイムアウト |
| `DEFAULT_PARARELL_LIMIT` | 2 | デフォルト並列数 |
| `DETAIL_PARARELL_LIMIT` | 6 | 詳細ページ取得時の並列数 |
| `TCP_CONNECTOR_LIMIT` | 100 | TCP接続プール上限 |

---

## 技術スタック (Tech Stack)

### コア言語
- **Python 3.11** (`python:3.11-slim` Dockerイメージ)

### HTTP & パース
- **aiohttp**: 非同期HTTPクライアント（JavaScriptレンダリング不要）
  - 役割: 不動産サイトからHTMLを取得
  - ファイル: `src/crawler/package/api/api.py`
- **BeautifulSoup4 (bs4)**: HTML解析・データ抽出
  - 役割: HTMLから物件情報を抽出
  - ファイル: `src/crawler/package/parser/*Parser.py`
- **lxml**: BeautifulSoup4のパーサーエンジン

### データ層
- **Django**: ORM（モデル定義・マイグレーション）
  - 役割: データベーススキーマ管理
  - ファイル: `src/crawler/package/models/`
- **django-db-connection-pool**: SQLAlchemyベースのDB接続プール仲介ライブラリ
  - 役割: クローラー並行実行時のMySQL接続数制限超過 (Too many connections) を防ぐコネクションプーリング
- **mysqlclient**: MySQLデータベースアダプター
- **MySQL 8.0**: リレーショナルデータベース（Dockerコンテナ）

### インフラ
- **Docker / Docker Compose**: コンテナ化・オーケストレーション
  - 設定: `docker-compose.yml`, `Dockerfile`
- **Task (Taskfile)**: CLIタスク自動化
  - 設定: `Taskfile.yml`

### テスト
- **pytest**: テストフレームワーク
  - テスト: `src/crawler/tests/`

> [!NOTE]
> 以前のバージョンで使用していた Playwright (JavaScriptレンダリング) は、軽量化と安定性向上のため削除されました。
> 現在は `aiohttp` + `BeautifulSoup4` による高速な静的HTML解析を採用しています。

### 3. ログの確認

アプリケーションのログをリアルタイムで確認するには：

```bash
task logs
```

### 4. サーバーの停止

アプリケーションコンテナの停止:

```bash
task stop
```

### 5. クオータ制限回避用自動実行ループ（Antigravity専用）

Antigravityエージェントのクオータ制限を回避し、バックグラウンドで開発を継続させるための自動実行スケジュールです。

*   **指示内容テキスト**: [antigravity_instruction.txt](file:///c:/Users/weare/Documents/realestate_crawler/antigravity_instruction.txt)

**動作概要:**
1. エージェントは自ら開発指示（[antigravity_instruction.txt](file:///c:/Users/weare/Documents/realestate_crawler/antigravity_instruction.txt)）を読み込み、APIクオータが許す限り、連続して次の開発イテレーションを自律的に実行し続けます。
2. **ハイブリッド役割分担（マルチエージェント方式）**:
   * クオータ節約と高精度の設計を両立するため、親エージェント（Claude等の高機能モデル）が設計方針を決定します。
   * 実際のファイル編集や再学習、テスト実行等の実作業は、親エージェントが低廉なモデル（Gemini等）をサブエージェントとして起動して実行させ、トークン消費を最小化します。
3. クオータ制限エラー等に直面して開発を継続できなくなった場合、エージェントは自律的に `schedule` ツールを使用し、5時間（18,000秒）後に自身を再起動するワンショットタイマーを仕掛けて休眠に入ります。
4. タイマーが発火すると自動的にセッションが再開され、ステップ1からの自律開発ループが再起動します。外部プロセスや固定cronを使用しないため、セッションロック競合は発生しません。
5. 指示内容を変更したい場合は、[antigravity_instruction.txt](file:///c:/Users/weare/Documents/realestate_crawler/antigravity_instruction.txt) を直接書き換えて保存してください。次回の再開時に新しい指示が自動で読み込まれます。

---

## トラブルシューティング

### コンテナ起動失敗

**症状**: `task init` 実行後にコンテナが起動しない

**原因と対処:**
1. **ポート競合**: 8000番または3306番ポートが既に使用されている
   ```bash
   # ポート使用状況確認（Windows）
   netstat -an | findstr "8000"
   netstat -an | findstr "3306"
   ```
   対処: 使用中のプロセスを停止するか、`docker-compose.yml` でポート番号を変更

2. **Docker Desktop未起動**: Docker Desktopが起動していない
   
   対処: Docker Desktopを起動してから再実行

### データベース接続エラー

**症状**: `OperationalError: (2003, "Can't connect to MySQL server")`

**原因と対処:**
1. **MySQLコンテナ未起動**: コンテナが起動していない
   ```bash
   docker compose ps
   # mysql コンテナが Up でない場合
   task default
   ```

2. **接続数上限**: 同時接続数が上限に達している
   
   対処: `task stop` → `task default` で再起動

### クローラー実行後にデータが入らない

**症状**: `task crawl` 実行後、データベースにレコードが追加されない

**確認手順:**
1. **ログ確認**:
   ```bash
   task logs
   ```
   エラーメッセージを確認

2. **パースエラー**: `ReadPropertyNameException` が出力されている場合
   - サイトのHTML構造が変更された可能性
   - 該当パーサーの修正が必要

3. **ネットワークエラー**: `ClientConnectorError` が出力されている場合
   - 一時的なネットワーク障害
   - 自動リトライ（10秒後）が実行される

### パーサーテスト失敗

**症状**: `task test` でテストが失敗する

**対処:**
```bash
# 全テスト実行（単体テスト＋ライブ到達・全フィールド動的統合テスト）
task test

# 全ジョブ本番経路クローリング保証（ライブ）
# ローカル: 静的HTMLは -n 4、Playwright会社は順次
# GitHub Actions: 静的HTMLは -n auto、Playwright会社は順次
task test-live

# 修正確認など: 対象サイト/ジョブだけライブ検証
task test-live SITES=sumifu,odakyu
task test-live SITES=sumifu_mansion,odakyu_investment
task test-live COMPANY=sumifu TYPE=mansion
# 強制モード: MODE=ci または MODE=local
task test-live MODE=ci

# オフライン: CRAWL_JOBS カタログ同期ゲートのみ
task test-catalog

# 特定のパーサーのみテスト
docker compose exec -T app pytest src/crawler/tests/unit/test_mitsui_parser.py -v

# 詳細なログ出力
docker compose exec -T app pytest src/crawler/tests/ -v -s
```


---

## 仕様ドキュメント (Specifications)

詳細な仕様については、以下のドキュメントを参照してください。

*   **[外部設計書 (Basic Design)](docs/basic_design/basic_design_master.md)**
    *   クローラー仕様 (Fire-and-Forget, エラーハンドリング)
    *   障害耐性・クローラー優先順位制御 (Smallest-Site-First, サーキットブレイカー, 0件取得失敗判定)
    *   URL構造・パラメータ定義
*   **[内部設計書 (Detailed Design)](docs/internal_design/detailed_design_master.md)**
    *   データベーススキーマ定義 (全17モデル)
    *   アーキテクチャ原則 (階層型Baseパーサー, モニタリング, Slack疎通検証)
    *   APIエンドポイント構造
    *   クラス図・シーケンス図

---

## ドキュメント一覧 (Documentation)

ドキュメントは工程別に整理されています。

### 📋 1. 要件定義 (Requirements)
`docs/requirements/`
ユーザーの要求仕様や事前調査結果。
*   **[requirements_master.md](docs/requirements/requirements_master.md)**
    *   基本要件定義書
    *   投資用物件種別定義一覧
    *   予備調査レポート (住友不動産ほか)
    *   サイト構造解析資料 (`site_structures/` ディレクトリへの参照)

    **詳細ドキュメント:**
    *   **[investment_property_types.md](docs/requirements/investment_property_types.md)**: 投資用物件種別定義一覧
    *   **[sumifu_crawling_report.md](docs/requirements/sumifu_crawling_report.md)**: 住友不動産予備調査レポート
    *   **[additional_brokers_research.md](docs/requirements/additional_brokers_research.md)**: 不動産会社クローラー開発ロードマップ ＆ ターゲットリスト
    *   **[site_structures/](docs/2_crawlers/sites/)**: 各社サイト構造解析資料（ietan, haseko, adcast, toho 他）
    *   **[project_status_and_design_intent.md](docs/requirements/project_status_and_design_intent.md)**: プロジェクトのビジョン・設計意図・開発状況
    *   **[land_evaluation_design.md](docs/requirements/land_evaluation_design.md)**: 土地情報収集＆高精度土地評価エンジン詳細設計書
    *   **[security_scan_workflow.md](docs/requirements/security_scan_workflow.md)**: セキュリティ自動スキャンワークフロー要件定義書 (Trivy, Semgrep, Checkov, Prowler)
    *   **[sonar_zero_issues_requirements.md](docs/requirements/sonar_zero_issues_requirements.md)**: SonarCloudオープン課題全件解消 ＆ Strict Quality Gate・多層防御要件定義書
    *   **[proxysql_mig_client_param_requirements.md](docs/requirements/proxysql_mig_client_param_requirements.md)**: ProxySQL MIG クライアント引数整合性修復およびフォールバック強化要件定義書
    *   **[gcs_failure_telemetry_requirements.md](docs/requirements/gcs_failure_telemetry_requirements.md)**: GCSリアルタイム障害テレメトリ・一括オートヒール要件定義書 (Issue #466, #477)
    *   **[new_relic_monitoring_requirements.md](docs/requirements/new_relic_monitoring_requirements.md)**: New Relic 統合監視要件定義書 (APM・外形監視・コンテナ/DB・Cloud Logging・GenAI・Change Tracking・アラート) (Issue #471, #473, #478)
    *   **[pipeline_resilience_and_slack_progress_requirements.md](docs/requirements/pipeline_resilience_and_slack_progress_requirements.md)**: パイプライン耐障害性向上＆ML価格推定・お宝物件通知進捗Slack通知要件定義書 (Issue #492)
    *   **[parser_getter_architecture_requirements.md](docs/requirements/parser_getter_architecture_requirements.md)**: パーサー Getter メソッド化および表示バリエーション吸収 要件定義書 (Issue #564)
    *   **[batch_metrics_specification.md](docs/requirements/batch_metrics_specification.md)**: バッチ処理標準メトリクス表示要件定義書 (学習・推定・配信の件数・時間・スループット可視化) (Issue #647)
    *   **[slack_validation_delisted_requirements.md](docs/requirements/slack_validation_delisted_requirements.md)**: Slack進捗通知の分離、公開終了物件のDB保持、価格推定前データ検証の厳格化およびAuto-Healフラグ連携要件定義書 (Issue #665)
    *   **[slack_notification_channel_separation_requirements.md](docs/requirements/slack_notification_channel_separation_requirements.md)**: Slack通知チャンネル責務分離要件定義書 (Issue #688)
    *   **[codegraph_operational_integration_requirements.md](docs/requirements/codegraph_operational_integration_requirements.md)**: CodeGraphインデックス自動同期およびMCP運用の組み込み要件定義書 (Issue #744)
    *   **[yield_and_validator_thresholds_requirements.md](docs/requirements/yield_and_validator_thresholds_requirements.md)**: 投資物件利回り補正およびバリデーション許容境界の是正要件定義書 (Issue #791)
    *   **[crawler_stability_and_count_requirements.md](docs/requirements/crawler_stability_and_count_requirements.md)**: クローラー巡回安定化・動的種別集計・WAF/タイムアウト耐性強化 要件定義書 (Issue #819, #820, #821, #822)
    *   **[task_array_fast_exit_requirements.md](docs/requirements/task_array_fast_exit_requirements.md)**: タスクアレイ完了時のプロセス即時終了保証および最終タスクへの全体集約委譲 要件定義書 (Issue #823)

### 📐 2. 外部設計 (Basic Design)
`docs/basic_design/`
外部システムの仕様やインターフェース定義。
*   **[basic_design_master.md](docs/basic_design/basic_design_master.md)**
    *   クローラー仕様詳細
    *   サンプル物件URLリスト
*   **[security_scan_workflow.md](docs/basic_design/security_scan_workflow.md)**: セキュリティ自動スキャン基本設計書 (多層防御アーキテクチャ・並列ジョブ構成)
*   **[sonar_zero_issues_basic_design.md](docs/basic_design/sonar_zero_issues_basic_design.md)**: SonarCloudオープン課題全件解消 ＆ Strict Quality Gateアーキテクチャ基本設計書
*   **[proxysql_mig_client_param_basic_design.md](docs/basic_design/proxysql_mig_client_param_basic_design.md)**: ProxySQL MIG クライアント引数整合性修復およびフォールバック設計書
*   **[gcs_failure_telemetry_basic_design.md](docs/basic_design/gcs_failure_telemetry_basic_design.md)**: GCSリアルタイム障害テレメトリ・一括オートヒール基本設計書 (Issue #466, #477)
*   **[new_relic_monitoring_design.md](docs/basic_design/new_relic_monitoring_design.md)**: New Relic 統合監視基本設計書 (フルスタック可観測性・APM・Synthetics・Cloud Run・ログ統合) (Issue #471, #473, #478)
*   **[pipeline_resilience_and_slack_progress_basic_design.md](docs/basic_design/pipeline_resilience_and_slack_progress_basic_design.md)**: パイプライン耐障害性向上＆ML価格推定・お宝物件通知進捗Slack通知基本設計書 (Issue #492)
*   **[parser_getter_architecture_basic_design.md](docs/basic_design/parser_getter_architecture_basic_design.md)**: パーサー Getter メソッド化 基本設計書 (Issue #564)
*   **[batch_metrics_design.md](docs/basic_design/batch_metrics_design.md)**: バッチ処理標準メトリクス基本設計書 (Issue #647)
*   **[slack_validation_delisted_basic_design.md](docs/basic_design/slack_validation_delisted_basic_design.md)**: Slack進捗通知の分離、公開終了物件のDB保持、価格推定前データ検証の厳格化およびAuto-Healフラグ連携基本設計書 (Issue #665)
*   **[slack_notification_channel_separation_basic_design.md](docs/basic_design/slack_notification_channel_separation_basic_design.md)**: Slack通知チャンネル責務分離基本設計書 (Issue #688)
*   **[codegraph_operational_integration_basic_design.md](docs/basic_design/codegraph_operational_integration_basic_design.md)**: CodeGraph 運用組み込み基本設計書 (Gitフック・Taskfile・エージェント規範) (Issue #744)
*   **[yield_and_validator_thresholds_basic_design.md](docs/basic_design/yield_and_validator_thresholds_basic_design.md)**: 投資物件利回り補正およびバリデーション許容境界の是正基本設計書 (Issue #791)
*   **[crawler_stability_and_count_external_design.md](docs/external_design/crawler_stability_and_count_external_design.md)**: クローラー巡回安定化・動的種別集計・WAF/タイムアウト耐性強化 外部設計書 (Issue #819, #820, #821, #822)
*   **[task_array_fast_exit_external_design.md](docs/external_design/task_array_fast_exit_external_design.md)**: タスクアレイ完了時のプロセス即時終了保証および最終タスクへの全体集約委譲 外部設計書 (Issue #823)

### 🔧 3. 内部設計 (Internal Design)
`docs/internal_design/`
システム内部のアーキテクチャやデータ構造。

**技術仕様書:**
- **[データベーススキーマ設計](docs/internal_design/database_schema.md)** - 全モデルのフィールド定義とリレーション (土地評価用新フィールドの追加を反映)
- **[詳細設計マスター](docs/internal_design/detailed_design_master.md)** - システム全体の詳細設計概要
- **[API構造設計](docs/internal_design/api_structure.md)** - 再帰的API連鎖アーキテクチャ、投資用物件取得戦略、および価格推定APIの詳細
- **[価格推定API OpenAPI仕様書](docs/api/openapi.yaml)** - Swaggerで閲覧可能な価格推定API仕様書（OpenAPI 3.0）
- **[フィールド名統一規約](docs/internal_design/field_naming_standards.md)** - 全共通モデルのフィールド名統一規約
- **[MLモデル仕様書](docs/internal_design/ml_model_specifications.md)** - 機械学習モデル・学習・推論・バルク評価パイプライン仕様書（2段階スクリーニング・特徴量・責務分割アーキテクチャ・参照マスタ軽量化・ストリーミング評価）
- **[パーサー実装手順ガイドライン](docs/implementation/parser_implementation_procedure.md)** - 一項目一メソッド（Template Method パターン）、基底クラス `@abstractmethod` 抽象設計規約、および関数名漢字利用禁止規約
- **[日次予測精度診断運用ポリシー](docs/internal_design/ml_prediction_diagnostics_policy.md)** - MdAPEを主軸とした価格帯・種別別ズレ日次診断、ワースト要因タギング、AIインサイト運用仕様
- **[SonarCloud課題全件解消詳細設計](docs/internal_design/sonar_zero_issues_internal_design.md)** - SonarCloud課題ゼロ化およびStrict Quality Gate・CI多層防御モジュール詳細設計書
- **[マクロ経済時系列予測モデル設計書](docs/internal_design/macro_time_series_forecaster.md)** - 正則化多変量自己回帰 (Ridge VAR) による相場モメンタム特徴量 (`repi_growth_3m`, `macro_regime_score`) 仕様
- **[1物件1リクエスト完結型AI属性抽出設計書](docs/internal_design/single_unified_property_ai_extractor.md)** - 1物件1AIリクエスト原則、マルチモーダル画像・全観点一括抽出スキーマ仕様
- **[建物マスタ設計書](docs/internal_design/building_master_design.md)** - マンション名寄せ・自動スペック伝搬・BuildingMasterモデル仕様
- [CodeRabbitレビュー＆マージゲート内部設計書](docs/internal_design/coderabbit_gate_internal_design.md) - CodeRabbit自動コードレビュー設定、未解決レビューコメント解決必須化、CIマージブロックゲート仕様
- [セキュリティ自動スキャン内部設計書](docs/internal_design/security_scan_workflow.md) - Trivy, Semgrep, Checkov 並列スキャン、SARIFアップロード、Prowler GCPライブ監査仕様
- **[ProxySQL MIG クライアント引数整合性修復およびフォールバック内部設計書](docs/internal_design/proxysql_mig_client_param_internal_design.md)** - RegionInstanceGroupManagersClient 引数不整合修復および多重防御フォールバック内部設計
- **[GCSリアルタイム障害テレメトリ・一括オートヒール内部設計書](docs/internal_design/gcs_failure_telemetry_internal_design.md)** - リアルタイム障害JSON/生HTML GCS出力・分散タスク集約・Slack DevAgentゼロタッチ連携内部設計書 (Issue #466, #477)
- **[New Relic 統合監視内部詳細設計書](docs/internal_design/new_relic_monitoring_internal_design.md)** - New Relic APM初期化・Synthetics・GenAI監視・デプロイ追跡・NRQLアラート詳細設計 (Issue #471, #473, #478)
- **[パイプライン耐障害性向上＆ML価格推定・お宝物件通知進捗Slack通知内部詳細設計書](docs/internal_design/pipeline_resilience_and_slack_progress_internal_design.md)** - クローリング異常終了時の後続パイプライン継続実行およびバルク価格推定・お宝物件スクリーニング進捗Slack通知詳細設計書 (Issue #492)
- **[パーサー Getter メソッド化 内部設計書](docs/internal_design/parser_getter_architecture_internal_design.md)** - パーサー Getter メソッド化および表示バリエーション吸収 内部設計書 (Issue #564)
- **[バッチ処理標準メトリクス内部設計書](docs/internal_design/batch_metrics_internal_design.md)** - バッチ処理標準メトリクス内部設計書 (Issue #647)
- **[Slack進捗通知分離・公開終了保持・厳格バリデーション内部設計書](docs/internal_design/slack_validation_delisted_internal_design.md)** - Slack進捗通知の分離、公開終了物件のDB保持、価格推定前データ検証の厳格化およびAuto-Healフラグ連携内部設計書 (Issue #665)
- **[Slack通知チャンネル責務分離内部設計書](docs/internal_design/slack_notification_channel_separation_internal_design.md)** - Slack通知チャンネル責務分離内部設計書 (Issue #688)
- **[CodeGraph 運用組み込み内部設計書](docs/internal_design/codegraph_operational_integration_internal_design.md)** - Git フック仕様（post-merge / post-checkout）、Taskfile定義、AGENTS.md行動規範および自動テスト仕様 (Issue #744)
- **[投資物件利回り補正およびバリデーション許容境界の是正内部設計書](docs/internal_design/yield_and_validator_thresholds_internal_design.md)** - 利回りフォールバック自動算出、投資ポータルURL低額許容、および50億円上限閾値設定 (Issue #791)
- **[クローラー巡回安定化・動的種別集計・WAF/タイムアウト耐性強化内部設計書](docs/internal_design/crawler_stability_and_count_internal_design.md)** - 動的種別判定集計・Tokyu/Sumifu投資モデル合算・SMTRC WAFリトライ・Sumai1タイムアウト緩和 (Issue #819, #820, #821, #822)
- **[タスクアレイ完了時のプロセス即時終了保証および最終タスクへの全体集約委譲 内部設計書](docs/internal_design/task_array_fast_exit_internal_design.md)** - 先行完了タスクの全体集約スキップ・即時exit(0)および最終完了タスクへのレポート委譲 (Issue #823)




### 🛠️ 4. 実装・開発・運用 (Implementation & Operation)
`docs/implementation/` & `docs/operation/`
開発者向けの環境構築・実装・常駐運用ガイド。
*   **[developer_guide_master.md](docs/implementation/developer_guide_master.md)**
    *   開発者向けガイド (環境構築、デバッグ)
    *   クイックスタート
    *   Taskコマンドリファレンス
    *   リファクタリング提案

    **詳細ドキュメント:**
    *   **[quick_start.md](docs/implementation/quick_start.md)**: クイックスタートガイド
    *   **[task_commands.md](docs/implementation/task_commands.md)**: Taskコマンドリファレンス
    *   **[parser_implementation_procedure.md](docs/implementation/parser_implementation_procedure.md)**: パーサー実装手順ガイドライン
    *   **[parser_design_guidelines.md](docs/implementation/parser_design_guidelines.md)**: パーサー設計ガイドライン
    *   **[ai_developer_guide.md](docs/implementation/ai_developer_guide.md)**: AI駆動開発ガイドライン (AIエージェント向け)
    *   **[slack_agent_guidelines.md](docs/operation/slack_agent_guidelines.md)**: Slack 24/7 常駐型自動応答エージェント仕様書（先頭識別子無帰還判定・動的段階的通知間隔）


### 🔧 5. 運用・保守 (Operation)
`docs/operation/`
運用手順やドキュメント管理ルール。
*   **[operation_manual_master.md](docs/operation/operation_manual_master.md)**
    *   運用トラブルシューティング
    *   ドキュメント管理ガイドライン

    **詳細ドキュメント:**
    *   **[troubleshooting.md](docs/operation/troubleshooting.md)**: トラブルシューティング
    *   **[documentation_guidelines.md](docs/operation/documentation_guidelines.md)**: ドキュメント管理ガイドライン
    *   **[slack_agent_setup.md](docs/operation/slack_agent_setup.md)**: Slack 開発 Agent ボット設定手順



---

## Task コマンド完全リファレンス
(詳細は [developer_guide_master.md](docs/implementation/developer_guide_master.md) を参照)

| コマンド | 説明 | 内部動作 | 使用例 |
|---------|------|---------|--------|
| `task init` | 初期セットアップ | `docker compose up -d --build` + DB初期化 | 初回セットアップ時 |
| `task default` | サーバー起動 | `docker compose up -d` | 通常の起動 |
| `task stop` | サーバー停止 | `docker compose down` | 作業終了時 |
| `task crawl` | クローラー実行 | `curl POST http://localhost:8000/...` | `task crawl COMPANY=mitsui TYPE=mansion` |
| `task logs` | ログ表示 | `docker compose logs -f app` | デバッグ時 |
| `task test` | テスト実行 | `docker compose exec -T app pytest` | コード変更後 |
| `task ci:precheck` | プッシュ前CI事前検証 | `ruff check` + `sonar diff` + `pytest unit` + `mutation` | リモートpush前 |

## 定期クローリングとエラー監視

本システムは、`scheduler` コンテナを利用したcron自動クローリングおよびパースエラー監視機能を備えています。

### 1. 動作概要
* **実行スケジュール**: 毎日深夜 `02:00` に自動起動します。
* **順次実行**: 22社 × 最大5物件種別の計89ジョブを並列実行します。
* **負荷軽減**: ジョブ間に `180秒`（3分）のクールダウンを挟み、対象サイトへのアクセス集中を避けます。
* **エラー監視**: 実行完了後、`scripts/ops/monitor_error_pages.py` が自動起動し、過去24時間以内に `error_pages/` に退避されたパースエラーを集計・分析して `logs/error_report_YYYYMMDD.json` に出力します。


### 2. 手動での全社実行・テスト
定期バッチ処理を手動で直接実行したり、動作確認を行うことができます。

```bash
# 一括パイプライン実行
docker compose exec -T app python src/crawler/scripts/ops/run_pipeline.py
(Slack疎通チェック ➔ 全件クローリング ➔ データ検証 ➔ MLバルク評価 ➔ お宝物件通知)

# ドライラン（疎通確認のみ）
docker compose exec -T app python src/crawler/scripts/ops/run_all_crawlers.py --dry-run


# エラーページ監視レポートの単体実行
docker compose exec -T app python src/crawler/scripts/ops/monitor_error_pages.py
```

### 3. 環境変数カスタマイズ
`docker-compose.yml` の `scheduler` サービスの `environment` で以下の項目をカスタマイズ可能です：
* `CRAWL_COOLDOWN_SEC`: ジョブ間の待機秒数（デフォルト: `180`）
* `CRAWL_TIMEOUT_SEC`: 1ジョブの最大実行秒数（デフォルト: `1800`）
* `CRAWLER_LIMIT`: 1ジョブで保存する最大物件数（デフォルト: `100`。本番時は `0`（無制限）に設定することを推奨）

### 詳細な使用例

**初回セットアップ:**
```bash
task init
# 出力: Dockerイメージビルド → コンテナ起動 → DB初期化
```

**クローラー実行（複数パターン）:**
```bash
# 三井のリハウス - マンション
task crawl COMPANY=mitsui TYPE=mansion

# 住友不動産販売 - 投資用
task crawl COMPANY=sumifu TYPE=investment

# 東急リバブル - 戸建て
task crawl COMPANY=tokyu TYPE=kodate
```

**ログ監視（リアルタイム）:**
```bash
task logs
# Ctrl+C で終了
```

---

## ドキュメント体系 (Domain-Driven Documentation)

本プロジェクトの仕様・設計・運用ドキュメントは、7つのドメインに分類・集約されています。

```text
docs/
├── 1_architecture/              # [基盤] 全体システム方針・共通設計原則
├── 2_crawlers/                  # [クローラー] 収集エンジン・サイト別仕様 ＋ クローラー品質検証
├── 3_data_models/               # [データ] モデル・DB永続化・クレンジング ＋ データ完全性検証
├── 4_valuation_and_ml/          # [評価・ML] 不動産査定・機械学習・画像評価 ＋ モデル品質検証
├── 5_alert_and_delivery/        # [通知・配信] 投資判定スコア配信・Slack運用 ＋ 配信疎通検証
├── 6_platform_and_release/      # [プラットフォーム] インフラ・CI/CD・コード管理・デプロイ戦略
└── 7_operations_and_improvement/# [運用・改善] 稼働監視・自律修復(Auto-Heal)・機能改善ループ
```

### 🏢 クローラー開発者・パーサー新規追加向け中核ガイド
- **[クローラー対象サイト 事前調査チェックリスト](docs/2_crawlers/_standards/site_survey_checklist.md)**: サイトのHTMLレンダリング、URL・ページング、スペック表構造、WAF・掲載終了の事前調査シート
- **[新規サイトクローラー・パーサー実装ハンドブック](docs/2_crawlers/_standards/new_site_implementation_guide.md)**: 他社パーサーと同等の高水準で一発作成するための標準手順書
- **[クローラー巡回・ページネーション標準アーキテクチャ](docs/2_crawlers/_standards/crawler_pagination_architecture.md)**: 4大ページ送り戦略および事前間引き（2段階パース）プロトコル
- **[共通データ正規化・クレンジング規約](docs/3_data_models/data_normalization_and_cleansing.md)**: 全角半角・和暦・面積・価格の統一クレンジングパイプライン
- **[掲載終了確定プロトコルと誤認防止仕様](docs/2_crawlers/_standards/listing_ended_prevention_protocol.md)**: WAF/一時的エラーを掲載終了と誤認させない多重確認ルール
- **[クロスポータル多媒体横断名寄せ（ファジーデデュープ）仕様](docs/3_data_models/cross_portal_fuzzy_deduplication.md)**: 住所・面積・階数・建物名スコアリングによる同一物件Upsert仕様
- **[オートヒール品質ゲート＆データ完全性保証仕様](docs/7_operations_and_improvement/auto_heal_quality_gate.md)**: AI修正による空文字化・見せかけ修復を防止する非空率アサーション

---

## 次のステップ

初めてのユーザーが次に学ぶべき内容：

### 1. システムの理解を深める
- **[要件定義書](docs/requirements/requirements_master.md)**: システム要件、機能要件（差分クロール FR-004-DIFF、価格改定履歴 FR-005-HIST、重複データ移行 FR-005-MIGRATE、バルク推論）
- **[物件詳細URL価格推定API要件定義書](docs/requirements/predict_by_url_requirements.md)**: URL指定推定API、3段階キャッシュ、SSRF防御、クローリング候補収集要件
- **[GCPインフラ要件定義書](docs/requirements/gcp_infrastructure_requirements.md)**: クラウド移行要件・非機能要件
- **[基本設計書](docs/basic_design/basic_design_master.md)**: 差分クロールパターン、価格履歴パターン、移行・重複排除アーキテクチャ、Fire-and-Forgetパターン
- **[物件詳細URL価格推定API基本設計書](docs/basic_design/predict_by_url_design.md)**: エンドポイント設計、リクエスト/レスポンス、シーケンス図、エラー仕様
- **[OpenAPI 3.0 仕様書](docs/api/openapi.yaml)**: Swagger / OpenAPI インターフェース定義
- **[GCPアーキテクチャ基本設計書](docs/basic_design/gcp_architecture_design.md)**: Cloud Run Jobs / Cloud SQL / GCS サーバーレス構成
- **[内部設計書](docs/internal_design/detailed_design_master.md)**: 差分クロール・価格履歴シーケンス図、データベーススキーマ、Dual Storageパターン
- **[物件詳細URL価格推定API内部設計書](docs/internal_design/predict_by_url_internal_design.md)**: Singleflight、URLルーター、候補モデルスキーマ、SSRF防御
- **[データベース定義書](docs/internal_design/database_schema.md)**: 各社物件テーブル、PropertyPriceHistory（価格改定履歴）定義、updateDateTimeフィールド
- **[GCP並列分散実行内部設計書](docs/internal_design/gcp_parallel_execution_design.md)**: Cloud Tasks + Cloud Run による並列分散クローリング・レート制限およびマルチスレッドML推論仕様
- **[Terraform詳細設計書](docs/internal_design/terraform_specification.md)**: GCP IaC リソース定義・変数・出力仕様
- **[GCPコスト最適化・オンデマンドライフサイクル制御内部設計書](docs/internal_design/gcp_cost_optimization_design.md)**: ProxySQL MIGオンデマンド起動・起動チェック・タイムアウト時自律安全停止（SIGTERMハンドラ・早期停止）・安全停止セーフティネット、Direct VPC Egress、Artifact Registry保持ポリシー
- **[CodeRabbitレビュー＆未解決ゲート詳細設計書](docs/internal_design/coderabbit_gate_internal_design.md)**: CodeRabbit自動コードレビュー、未解決コメント・未完了チェックボックスのマージブロック強制設計
- **[MLモデル仕様書](docs/internal_design/ml_model_specifications.md)**: 一次・二次理論価格推定、アンサンブル重み最適化、スミアリング補正
- **[1物件1AIリクエスト属性抽出設計書](docs/internal_design/single_unified_property_ai_extractor.md)**: 1物件1リクエスト完結属性抽出、地代・借地権および建物マスタ連携仕様
- **[重複物件名寄せ階層設計書](docs/internal_design/property_deduplication_policy.md)**: 登録最古優先（ID順単調性保証）による重複物件の親決定、循環参照・多段チェーン防止および平坦化仕様
- **[物件URL一意性制約および重複排除・アップサート仕様要件](docs/requirements/pageurl_unique_constraint_requirements.md)**: PropertyBaseModel.pageUrl一意制約化、既存データ重複クレンジングおよびバルク評価耐障害性仕様 (Issue #660)
- **[プロ買い付け目線リスク・画地幾何解析要件定義書](docs/requirements/professional_risk_and_shape_analysis.md)**: 区画図判定、国税庁不整形地補正・かげ地割合、擁壁・解体・インフラ・階段等のプロ目線リスク評価要件
- **[プロ買い付け目線リスク・画地幾何解析基本設計書](docs/basic_design/professional_risk_and_shape_analysis.md)**: テキスト・画像解析パイプライン分離、画像選別・優先度制御、幾何エンジン連携
- **[プロ買い付け目線リスク・画地幾何解析内部設計書](docs/internal_design/professional_risk_and_shape_analysis.md)**: text_risk_analyzer/image_handler詳細仕様、PropertyEvaluationモデルマッピング、オーケストレーション
- **[Prodマージ高速化・CIトリガー最適化要件定義書](docs/requirements/prod_merge_ci_speedup.md)**: リリースPR自動起票、重複レビュー・テスト排除、Dependabot集約要件
- **[Prodマージ高速化・CIトリガー最適化基本設計書](docs/basic_design/prod_merge_ci_speedup.md)**: CD高速化アーキテクチャ、Fast-Pass設計、Dependabotグループ化
- **[Prodマージ高速化・CIトリガー最適化内部設計書](docs/internal_design/prod_merge_ci_speedup.md)**: auto-release-pr詳細実装、review-gate/dependabot/coderabbit設定仕様
- **[CI/CD パイプライン最適化要件定義書](docs/requirements/ci_cd_optimization_requirements.md)**: master push 重複ジョブ廃止・PR提出時一本化・Production Gate 10秒化要件
- **[CI/CD パイプライン最適化内部設計書](docs/internal_design/ci_cd_optimization_design.md)**: ワークフロー別トリガー見直し・production ブランチ保護ルール詳細仕様
- **[PR事前全検証機構（Pre-PR Check）要件定義書](docs/requirements/pre_pr_check_requirements.md)**: SonarCloud / CodeRabbit CLI / Linter / 単体テスト一括水際検証要件
- **[PR事前全検証機構（Pre-PR Check）基本設計書](docs/basic_design/pre_pr_check_design.md)**: 8大検証ステージ・Taskコマンド・Pre-Push Hook遮断アーキテクチャ
- **[PR事前全検証機構（Pre-PR Check）内部設計仕様書](docs/internal_design/pre_pr_check_specification.md)**: pre_pr_check.py / StageResult / CLIオプション詳細仕様
- **[Google GenAI SDK 移行要件定義書](docs/requirements/google_genai_sdk_migration.md)**: 非推奨 `google.generativeai` から `google-genai` への移行要件・受入基準
- **[Google GenAI SDK 移行基本設計書](docs/basic_design/google_genai_sdk_migration.md)**: アーキテクチャ変更点・クライアント設計
- **[GCS障害テレメトリ要件定義書](docs/requirements/gcs_failure_telemetry_requirements.md)**: 障害HTML保存・再パース検証要件 (Issue #466, #561)
- **[GCS障害テレメトリ基本設計書](docs/basic_design/gcs_failure_telemetry_basic_design.md)**: 障害HTML永続化・再パース検証アーキテクチャ (Issue #466, #561)
- **[GCS障害テレメトリ内部設計書](docs/internal_design/gcs_failure_telemetry_internal_design.md)**: FailureReporter・ErrorPageReplayer・fetch_run_failures 詳細仕様 (Issue #466, #561)
- **[Cloud Workflows 統合オーケストレーション要件定義書](docs/requirements/cloud_workflows_orchestration_requirements.md)**: クロール・ML・割安物件配信の一貫自動化とタイムアウト集約要件
- **[Cloud Workflows 統合オーケストレーション基本設計書](docs/basic_design/cloud_workflows_orchestration_basic_design.md)**: Workflows ステートマシン、ProxySQL 連動、7h/5h タイムアウト設計
- **[Cloud Workflows 統合オーケストレーション内部設計書](docs/internal_design/cloud_workflows_orchestration_internal_design.md)**: YAML 定義仕様、ハング監視実装仕様
- **[パーサー項目別Getter疎結合アーキテクチャ要件定義書](docs/requirements/parser_getter_architecture_requirements.md)**: 項目別Getterによるパース処理疎結合化、引数レスポンス単一化、表示差分吸収仕様
- **[パーサー項目別Getter疎結合アーキテクチャ基本設計書](docs/basic_design/parser_getter_architecture_basic_design.md)**: 種別基底パーサー階層、get_<field>(response) 設計、キャッシュ・委譲構造
- **[パーサー項目別Getter疎結合アーキテクチャ内部設計書](docs/internal_design/parser_getter_architecture_internal_design.md)**: メソッドシグネチャ、正規表現・型変換、モデル空欄許容マッピング仕様
- **[Slack Socket Mode 自律修復要件定義書](docs/requirements/slack_socket_mode_auto_heal_requirements.md)**: クローラー異常検知 ➔ Slack Socket Mode ➔ Antigravity 自律修復中継要件、Top-50頻度優先・完了報告プロトコル要件 (Issue #575, #596, #767, #779)
- **[Slack Socket Mode 自律修復基本設計書](docs/basic_design/slack_socket_mode_auto_heal_basic_design.md)**: Slack Socket Mode 中継アーキテクチャ・自己ループ防止設計、完了報告プロトコル・トークン節約設計 (Issue #575, #596, #767, #779)
- **[Slack Socket Mode 自律修復内部設計書](docs/internal_design/slack_socket_mode_auto_heal_internal_design.md)**: slack_agent / auto_heal_parsers / aggregate_and_sort_targets / 完了報告プロトコル詳細仕様 (Issue #575, #596, #767, #779)
- **[pre_pr_check 並列最適化・テスト動的選別要件定義書](docs/requirements/pre_pr_check_optimization_requirements.md)**: 差分ファイル別テスト選別・先行テスト並列キック・CodeRabbitスキップ要件 (Issue #579)
- **[pre_pr_check 並列最適化・テスト動的選別基本設計書](docs/basic_design/pre_pr_check_optimization_basic_design.md)**: 並行パイプライン・直列ミューテーション分離・Cavemanサマリー設計 (Issue #579)
- **[MySQL認証プラグイン移行要件定義書](docs/requirements/mysql_auth_plugin_migration_requirements.md)**: caching_sha2_password 移行・非推奨警告解消要件 (Issue #572)
- **[MySQL認証プラグイン移行基本設計書](docs/basic_design/mysql_auth_plugin_migration_basic_design.md)**: ProxySQL TLS 接続および暗号化認証アーキテクチャ (Issue #572)
- **[MySQL認証プラグイン移行内部設計書](docs/internal_design/mysql_auth_plugin_migration_internal_design.md)**: Terraform / ProxySQL 定義差分および TDD テスト仕様 (Issue #572)
- **[種別誤判定防止＆データ監視最適化要件定義書](docs/requirements/property_type_detection_and_validation_requirements.md)**: PropertyTypeDetector URL優先判定・validate_data 直近走査化要件 (Issue #584)
- **[種別誤判定防止＆データ監視最適化基本設計書](docs/basic_design/property_type_detection_and_validation_basic_design.md)**: URL先行評価・7日間直近フィルタ・CLIオプション基本設計 (Issue #584)
- **[種別誤判定防止＆データ監視最適化内部設計書](docs/internal_design/property_type_detection_and_validation_internal_design.md)**: _detect_rule_based / validate_data 詳細仕様 (Issue #584)
- **[Review Gate CodeRabbit 自動Resolve化要件定義書](docs/requirements/review_gate_auto_resolve_requirements.md)**: 古いCHANGES_REQUESTED自動失効・未解決スレッド自動Resolve仕様 (Issue #589)
- **[Review Gate CodeRabbit 自動Resolve化基本設計書](docs/basic_design/review_gate_auto_resolve_basic_design.md)**: GitHub GraphQL自動スレッド解決・Gateデッドロック解消設計 (Issue #589)
- **[Review Gate CodeRabbit 自動Resolve化内部設計書](docs/internal_design/review_gate_auto_resolve_internal_design.md)**: autoResolveCodeRabbitThreads・CHANGES_REQUESTEDバイパス詳細仕様 (Issue #589)
- **[デプロイ時イメージ管理要件定義書](docs/requirements/deploy_image_lifecycle_requirements.md)**: 本番デプロイ時のイメージ孤立防止・プルーニング順序要件 (Issue #593)
- **[デプロイ時イメージ管理基本設計書](docs/basic_design/deploy_image_lifecycle_basic_design.md)**: 全更新完了後プルーニング原則および安全シーケンス設計 (Issue #593)
- **[デプロイ時イメージ管理内部設計書](docs/internal_design/deploy_image_lifecycle_internal_design.md)**: deploy-production ワークフローにおけるステップ順序・Prune仕様 (Issue #593)
- **[掲載終了ページ共通ハンドリング要件定義書](docs/requirements/listing_ended_handling_requirements.md)**: 掲載終了ページの基底包括検知・クローリングエラー防止要件 (Issue #600)
- **[掲載終了ページ共通ハンドリング基本設計書](docs/basic_design/listing_ended_handling_basic_design.md)**: 基底パーサー検知パイプライン・キーワード定義・エラー除外アーキテクチャ (Issue #600)
- **[掲載終了ページ共通ハンドリング内部設計書](docs/internal_design/listing_ended_handling_internal_design.md)**: ParserBase._raise_if_listing_ended詳細仕様・TDD検証設計 (Issue #600)
- **[CI/PR監視--watch禁止・有限タイムアウト要件定義書](docs/requirements/finite_timeout_ci_watch_requirements.md)**: 無制限--watch禁止・有限タイムアウトポーリング強制・ハング根絶要件 (Issue #602)
- **[CI/PR監視--watch禁止・有限タイムアウト基本設計書](docs/basic_design/finite_timeout_ci_watch_basic_design.md)**: 非同期ポーリングアーキテクチャ・スタック検知・即時診断設計 (Issue #602)
- **[CI/PR監視--watch禁止・有限タイムアウト内部設計書](docs/internal_design/finite_timeout_ci_watch_internal_design.md)**: check_pr_ci_status.py CLI仕様・カテゴリ別分類・タイムアウト制御仕様 (Issue #602)
- **[Slack通知最適化・テスト時外部送信遮断およびチャンネル不整合是正要件定義書](docs/requirements/slack_notification_optimization_requirements.md)**: テスト時実API送信物理遮断・事前接続サイレント化・チャンネル不整合是正要件 (Issue #642)
- **[Slack通知最適化・テスト時外部送信遮断およびチャンネル不整合是正基本設計書](docs/basic_design/slack_notification_optimization_basic_design.md)**: テスト隔離バリア・Silent Health Check・チャンネル集中ルーティング設計 (Issue #642)
- **[Slack通知最適化・テスト時外部送信遮断およびチャンネル不整合是正内部設計書](docs/internal_design/slack_notification_optimization_internal_design.md)**: conftest自動遮断fixture・verify_slack_credentials・get_alert_channel詳細仕様 (Issue #642)
- **[smtrcタイムアウト延長・所在階パースおよびバリデータ誤検知解消要件定義書](docs/requirements/smtrc_timeout_and_parser_heal_requirements.md)**: smtrcタイムアウト延長(2400s)・所在階複合表記抽出・バリデータ階数判定フォールバック要件 (Issue #723)
- **[smtrcタイムアウト延長・所在階パースおよびバリデータ誤検知解消基本設計書](docs/basic_design/smtrc_timeout_and_parser_heal_basic_design.md)**: API/パーサー/バリデータ3層連携による巡回安定化・階数判定基本設計 (Issue #723)
- **[smtrcタイムアウト延長・所在階パースおよびバリデータ誤検知解消内部設計書](docs/internal_design/smtrc_timeout_and_parser_heal_internal_design.md)**: _getTimeOutSecond/kaisuStr/floorType_kai詳細実装およびテスト仕様 (Issue #723)
- **[smtrc投資物件パース現行利回り対応・年収文字列正規化要件定義書](docs/requirements/smtrc_investment_yield_and_rent_requirements.md)**: 現行利回り抽出・年収日付注記分離・クランプ防止要件 (Issue #775)
- **[smtrc投資物件パース現行利回り対応・年収文字列正規化基本設計書](docs/basic_design/smtrc_investment_yield_and_rent_basic_design.md)**: converter.parse_yen/SmtrcInvestmentParser連携アーキテクチャ (Issue #775)
- **[smtrc投資物件パース現行利回り対応・年収文字列正規化内部設計書](docs/internal_design/smtrc_investment_yield_and_rent_internal_design.md)**: parse_yen正規表現・SmtrcInvestmentParser詳細仕様 (Issue #775)
- **[Safety-Net通知文言改善および住友不動産投資用戸建てセレクター修復要件定義書](docs/requirements/safetynet_msg_and_sumifu_invest_requirements.md)**: ProxySQL稼働維持通知文言の改善およびsumifu invest_kodateセレクターKeyError解消要件 (Issue #727)
- **[Safety-Net通知文言改善および住友不動産投資用戸建てセレクター修復基本設計書](docs/basic_design/safetynet_msg_and_sumifu_invest_basic_design.md)**: ensure_resources_stopped通知ヘッダー変更およびsumifu.yaml定義拡張基本設計 (Issue #727)
- **[Safety-Net通知文言改善および住友不動産投資用戸建てセレクター修復内部設計書](docs/internal_design/safetynet_msg_and_sumifu_invest_internal_design.md)**: GCE/MIG通知メッセージ更新・sumifuParser property_type設定詳細仕様 (Issue #727)
- **[野村投資用戸建て誤ルーティング修復および非物件URLノイズ抑止要件定義書](docs/requirements/nomura_invest_routing_and_noise_filter_requirements.md)**: 野村投資用戸建てルーティング・モデル適正化および非物件ノイズ除外要件 (Issue #754)
- **[ログ出力改善・TRACE/DEBUG新設およびノーレベル出力禁止要件定義書](docs/requirements/logging_trace_debug_requirements.md)**: TRACE/DEBUG新設・print禁止・infoログ適正化要件 (Issue #783)
- **[ログ出力改善・TRACE/DEBUG新設およびノーレベル出力禁止基本設計書](docs/basic_design/logging_trace_debug_basic_design.md)**: ログレベル階層・Cloud Loggingマッピング・レベル適正化基本設計 (Issue #783)
- **[ログ出力改善・TRACE/DEBUG新設およびノーレベル出力禁止内部設計書](docs/internal_design/logging_trace_debug_internal_design.md)**: logging_config.py trace実装・呼出箇所移行詳細仕様 (Issue #783)
- **[Auto-Heal一括修復要件定義書](docs/requirements/auto_heal_bulk_fixes_requirements.md)**: 野村戸建間取り・小田急投資面積欠損スキップ・投資交通および低価格バリデータ適正化要件 (Issue #787)
- **[残留50課題パース・バリデーション一括解消要件定義書](docs/requirements/heal_50_residual_issues_requirements.md)**: 三井交通tdヘッダー・東急階数/構造SCSSフォールバック・利回り0%許容・古民家1850年許容・所在階復元および評価レコード適正化要件 (Issue #794)
- **[残留50課題パース・バリデーション一括解消内部設計書](docs/internal_design/heal_50_residual_issues_design.md)**: ParserBase._getValueByLabel拡張・TokyuMansionParser SCSSフォールバック・PropertyDataValidator調整・一括解決スクリプト仕様 (Issue #794)
- **[適応型並列度＆DB過負荷制御要件定義書](docs/requirements/adaptive_concurrency_and_db_throttling_requirements.md)**: ジョブ並列度1.5倍化(9並列)・アクティブジョブ連動詳細並行度・DB過負荷自己適応型スロットリング要件 (Issue #795)
- **[適応型並列度＆DB過負荷制御外部設計書](docs/external_design/adaptive_concurrency_and_db_throttling_external_design.md)**: CLIオプション(--parallel 9)・環境変数および動的ログ仕様 (Issue #795)
- **[適応型並列度＆DB過負荷制御内部設計書](docs/internal_design/adaptive_concurrency_and_db_throttling_internal_design.md)**: AdaptiveConcurrencyController・_save_item_with_retryサーキットブレーカー詳細仕様 (Issue #795)


### 2. 開発を始める

- **[開発者ガイド](docs/implementation/developer_guide_master.md)**: 環境構築、デバッグ方法、API構造
- **[Taskコマンド完全リファレンス](docs/implementation/task_commands.md)**: Taskコマンド一覧および仕様
- **[SonarCloud事前検証・コーディング規約ガイド](docs/implementation/sonar_guardrail_guide.md)**: SonarLint設定、S3776/S8786対策、ローカルガードレール運用
- **[Terraformデプロイガイド](terraform/README.md)**: GCPインフラ一括プロビジョニング手順



---

## ディレクトリ構成

*   `src/crawler/`: アプリケーションコード
    *   `main.py`: エントリーポイント
    *   `package/`: クローラーロジック
    *   `tests/`: テストコード
*   `terraform/`: GCP インフラストラクチャ定義 (IaC)