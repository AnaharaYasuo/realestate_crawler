# Realestate Crawler

[![DeepWiki](https://deepwiki.com/badge-maker?url=https%3A%2F%2Fdeepwiki.com%2FAnaharaYasuo%2Frealestate_crawler)](https://deepwiki.com/AnaharaYasuo/realestate_crawler)

このプロジェクトは、5社の主要な不動産サイトから不動産物件情報を自動的に収集（スクレイピング）し、データベースに保存するためのツールです。

## 概要

### システムの目的

本システムは以下の3つの主要目的を持ちます：

1. **データ収集**: 5社の不動産サイトから非同期HTTPリクエストとHTML解析により物件情報を自動取得
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

**収集対象**: 5社 × 4カテゴリ（居住用3種別 + 投資用）

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
# 特定のパーサーのみテスト
docker compose exec -T app pytest src/crawler/tests/unit/test_mitsui_parser.py -v

# 詳細なログ出力
docker compose exec -T app pytest src/crawler/tests/unit/ -v -s
```

---

## 仕様ドキュメント (Specifications)

詳細な仕様については、以下のドキュメントを参照してください。

*   **[外部設計書 (Basic Design)](docs/basic_design/basic_design_master.md)**
    *   クローラー仕様 (Fire-and-Forget, エラーハンドリング)
    *   URL構造・パラメータ定義
*   **[内部設計書 (Detailed Design)](docs/detailed_design/detailed_design_master.md)**
    *   データベーススキーマ定義 (全17モデル)
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
    *   **[site_structures/](docs/requirements/site_structures/)**: 各社サイト構造解析資料
    *   **[project_status_and_design_intent.md](docs/requirements/project_status_and_design_intent.md)**: プロジェクトのビジョン・設計意図・開発状況


### 📐 2. 外部設計 (Basic Design)
`docs/basic_design/`
外部システムの仕様やインターフェース定義。
*   **[basic_design_master.md](docs/basic_design/basic_design_master.md)**
    *   クローラー仕様詳細
    *   サンプル物件URLリスト

### 🔧 3. 内部設計 (Internal Design)
`docs/internal_design/`
システム内部のアーキテクチャやデータ構造。

**技術仕様書:**
- **[データベーススキーマ設計](docs/internal_design/database_schema.md)** - 全モデルのフィールド定義とリレーション
- **[詳細設計マスター](docs/internal_design/detailed_design_master.md)** - システム全体の詳細設計概要
- **[API構造設計](docs/internal_design/api_structure.md)** - 再帰的API連鎖アーキテクチャと投資用物件取得戦略の詳細
- **[フィールド名統一規約](docs/internal_design/field_naming_standards.md)** - 全共通モデルのフィールド名統一規約
- **[投資用物件の種別定義](docs/domain/property_types.md)** - 不動産投資における戸建・アパートの定義と判定ロジック
- **[パーサー設計ガイドライン](docs/parser_design_guidelines.md)** - 一項目一関数（One-Item-One-Method）の設計思想と実装規約


### 🛠️ 4. 実装・開発 (Implementation)
`docs/implementation/`
開発者向けの環境構築・実装ガイド。
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


### 🔧 5. 運用・保守 (Operation)
`docs/operation/`
運用手順やドキュメント管理ルール。
*   **[operation_manual_master.md](docs/operation/operation_manual_master.md)**
    *   運用トラブルシューティング
    *   ドキュメント管理ガイドライン

    **詳細ドキュメント:**
    *   **[troubleshooting.md](docs/operation/troubleshooting.md)**: トラブルシューティング
    *   **[documentation_guidelines.md](docs/operation/documentation_guidelines.md)**: ドキュメント管理ガイドライン


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

## 定期クローリングとエラー監視

本システムは、`scheduler` コンテナを利用したcron自動クローリングおよびパースエラー監視機能を備えています。

### 1. 動作概要
* **実行スケジュール**: 毎日深夜 `02:00` に自動起動します。
* **順次実行**: 5社 × 最大6物件種別の計25ジョブを順次実行します。
* **負荷軽減**: ジョブ間に `180秒`（3分）のクールダウンを挟み、対象サイトへのアクセス集中を避けます。
* **エラー監視**: 実行完了後、`scripts/monitor_error_pages.py` が自動起動し、過去24時間以内に `error_pages/` に退避されたパースエラーを集計・分析して `logs/error_report_YYYYMMDD.json` に出力します。

### 2. 手動での全社実行・テスト
定期バッチ処理を手動で直接実行したり、動作確認を行うことができます。

```bash
# クローラーの一括順次実行（手動トリガー）
docker compose exec -T scheduler python src/crawler/scripts/run_all_crawlers.py

# ジョブのリスト確認（シミュレーション）
docker compose exec -T scheduler python src/crawler/scripts/run_all_crawlers.py --dry-run

# エラーページ監視レポートの単体実行
docker compose exec -T scheduler python src/crawler/scripts/monitor_error_pages.py
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

## 次のステップ

初めてのユーザーが次に学ぶべき内容：

### 1. システムの理解を深める
- **[外部設計書](docs/basic_design/basic_design_master.md)**: Fire-and-Forgetパターン、エラーハンドリング
- **[内部設計書](docs/detailed_design/detailed_design_master.md)**: データベーススキーマ、Dual Storageパターン

### 2. 開発を始める
- **[開発者ガイド](docs/implementation/developer_guide_master.md)**: 環境構築、デバッグ方法、API構造


---

## ディレクトリ構成

*   `src/crawler/`: アプリケーションコード
    *   `main.py`: エントリーポイント
    *   `package/`: クローラーロジック
    *   `tests/`: テストコード