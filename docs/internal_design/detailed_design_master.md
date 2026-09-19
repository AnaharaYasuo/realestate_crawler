# 内部設計書 (Internal Design)

本システムの内部構造、クラス継承関係、およびデータフローについて設計図を用いて説明します。

## 1. クラス継承図 (Class Diagram)

API通信およびクローリングの中核となるクラス群は、`ApiAsyncProcBase` を頂点とした継承構造を持っています。

```mermaid
classDiagram
    class ApiAsyncProcBase {
        <<Abstract>>
        -parser: ParserBase
        -semaphore: Semaphore
        +main(url)
        #_fetch()
        #_treatPage()*
        #_callApi()*
    }

    class ParseMiddlePageAsyncBase {
        <<Abstract>>
        #_treatPage()
        #_callApi()
        #_getParserFunc()*
    }

    class ParseDetailPageAsyncBase {
        <<Abstract>>
        #_run()
        #_treatPage()
        #_afterRunProc()
    }

    ApiAsyncProcBase <|-- ParseMiddlePageAsyncBase
    ApiAsyncProcBase <|-- ParseDetailPageAsyncBase

    ParseMiddlePageAsyncBase <|-- ParseMitsuiMansionArea
    ParseMiddlePageAsyncBase <|-- ParseMitsuiMansionList
    ParseDetailPageAsyncBase <|-- ParseMitsuiMansionDetail

    class ApiRegistry {
        -registry: dict
        +register(key, class)
        +get(key)
    }

    ApiAsyncProcBase ..> ApiRegistry : uses for local routing
```

---

## 2. API チェーン・データフロー (Sequence Diagram)

`task crawl` コマンド実行から DB 保存までのシーケンスです。

```mermaid
sequenceDiagram
    participant CLI as Task CLI
    participant Srv as API Server (main.py)
    participant Reg as ApiRegistry
    participant Proc as ApiAsyncProcBase
    participant Site as External Web Site
    participant DB as MySQL (Django ORM)

    CLI->>Srv: HTTP POST /api/.../start
    Srv->>Reg: get(path)
    Reg-->>Srv: Class Reference
    Srv->>Proc: main(url)
    
    loop API Chain (Start -> Region -> Area -> List)
        Proc->>Site: HTTP GET (HTML)
        Site-->>Proc: 200 OK
        Proc->>Proc: Parse URLs
        Proc->>Srv: HTTP POST /api/... (Async/Fire-and-Forget)
        Note right of Proc: or Local Routing directly
    end

    rect rgb(240, 240, 240)
    Note over Proc, DB: Detail Stage
    Proc->>Site: HTTP GET (Detail Page)
    Site-->>Proc: 200 OK
    Proc->>Proc: Extract Property Data
    Proc->>DB: item.save()
    end
    
    Proc-->>Srv: 200 finish
```

---

## 3. モデル継承関係 (Data Model Inheritance)

複数の物件種別やサイト間で共通するフィールドを効率的に管理するため、Django の抽象基底クラスを利用しています。

```mermaid
graph TD
    subgraph Django Models
        Base[django.db.models.Model]
        
        subgraph Sumifu
            SBase[SumifuModel<br/>Abstract Base: 69 fields]
            SM[SumifuMansion]
            SK[SumifuKodate]
            ST[SumifuTochi]
            SI[SumifuInvestment]
        end

        subgraph Misawa
            MBase[MisawaCommon<br/>Abstract Base: 21 fields]
            MM[MisawaMansion]
            MK[MisawaKodate]
            MT[MisawaTochi]
            MIN[MisawaInvestment]
        end

        Base --> SBase
        SBase --> SM
        SBase --> SK
        SBase --> ST
        Base --> SI

        Base --> MBase
        MBase --> MM
        MBase --> MK
        MBase --> MT
        MBase --> MIN
    end
```

---

## 4. 重複検知ロジック

本システムでは、物件の重複を `pageUrl` フィールドで識別します。
- **Index**: データベースレベルで `pageUrl` に UNIQUE インデックスまたは一般インデックスを付与。
- **Save Logic**: 既存のURLが見つかった場合、Django ORM の `update_or_create` 相当のロジック、または保存前の存在チェックにより、データの「新規作成」か「更新」かを判別します。

---

## 5. 投資用物件の実装方針 (Investment Property Implementation Strategy)

投資用物件（収益物件）のクローリングおよびデータ保存においては、以下の通り**物件種別ごとの完全分離**を基本方針とします。

### 5.1 背景
投資用物件には以下の3つの主要な種別が存在し、それぞれ扱う属性データが大きく異なります。
1. **一棟マンション (Whole Mansion)**: 満室時想定年収、総戸数、建物構造（RC等）、エレベーター有無など、ビル全体に関わる項目が多い。
2. **一棟アパート (Whole Apartment)**: 一棟マンションに近いが、木造や軽量鉄骨が多く、独自の項目が必要な場合がある。
3. **投資用戸建 (Investment House)**: 通常の居住用戸建に近く、部屋数や間取りが重要だが、利回り情報も付随する。

これらを単一の「投資用全般テーブル」で管理しようとすると、NULL許容フィールドが大量に発生し、データ品質の管理が困難になります。また、将来的なメンテナンスコストも増大します。

### 5.2 アーキテクチャ方針

#### A. クローラークラスの分離
物件種別ごとに専用の `DetailParser` クラス（非同期処理クラス）を作成します。
汎用的なクラスで分岐処理を行うのではなく、明確にクラスを分けることで責務を分離します。

*   `Parse[SiteName]InvestmentMansionDetail`
*   `Parse[SiteName]InvestmentApartmentDetail`
*   `Parse[SiteName]InvestmentHouseDetail`

#### B. データベーステーブルの分離
物件種別ごとに独立したテーブル（Djangoモデル）を作成します。共通項目（価格、所在地、URLなど）は抽象基底クラス (`InvestmentBaseModel`) で定義し、継承させます。

| 物件種別 | テーブル名 (例) | モデルクラス名 (例) | 備考 |
| :--- | :--- | :--- | :--- |
| 一棟マンション | `[site]_investment_mansion` | `[Site]InvestmentMansion` | 建物全体情報中心 |
| 一棟アパート | `[site]_investment_apartment` | `[Site]InvestmentApartment` | 同上 |
| 投資用戸建 | `[site]_investment_house` | `[Site]InvestmentHouse` | 戸建情報＋利回り |

#### C. データフローの変更
ミドルページ（一覧ページ）の解析ロジック (`_treatPage`) において、リンク先の物件種別を判別し、適切な詳細ページ用パーサークラスへルーティングを行います。

**判別方法:**
*   多くのサイトでは一覧ページの各アイテムに「種別」がテキストで記載されています（例：「一棟マンション」「売アパート」）。
*   URL構造に種別が含まれる場合もあります（例: `/mansion/` vs `/apartment/`）。
*   これらを利用して、API Registryから呼び出すべきパーサークラスを動的に決定します。

---

---

## 6. システムアーキテクチャ & 設計方針 (Architecture Principles)

### 6.1 データベース接続コネクションプーリング方針
- 高並列クローリングおよび将来的な Cloud Functions 等のサーバーレス環境移行を見据え、`django-db-connection-pool` による DB コネクションプール管理を採用する。
- 接続上限およびリトライ処理を制御し、`Too many connections (1040)` エラーを未然に防ぐ。

### 6.2 Playwright 利用制限とメモリ並列数独立制御方針
- **Playwright 使用の最小化**: 原則 Playwright は WAF 対策が必須なサイト（Athome等）のみに限定し、その他のサイトでは Playwright を使用せず `aiohttp` 等の軽量HTTP通信に統一する。
- **高メモリジョブと標準ジョブの並列数分離**: `run_all_crawlers.py` で並行処理を行う際は、メモリ消費の大きい Playwright ジョブ上限（`--playwright-parallel`）と標準ジョブ上限（`--parallel` / `--standard-parallel`）を独立して制御する。

### 6.3 クロール処理とMLモデル評価の分離・バルク推論方針 (B案)
- **クローリングとML評価の分離**: クローリング時は同期的ML評価（モデルファイル読込＋推論）を行わず、パースおよびDB保存のみをミリ秒単位で完了させる。
- **バルク推論の実施**: ML 評価はモデルを1回のみメモリロードして一括処理するバルク評価バッチ（`run_bulk_ml_evaluation.py`）または一括評価ステップで処理する。

### 6.4 ユーザー指示の設計方針自動ドキュメント保持原則
- ユーザーから指示された設計方針・システム構成ルール・パフォーマンス制約は、単なる一回限りの対応で終わらせず、必ず [AGENTS.md](file:///.agents/AGENTS.md) および `docs/` 配下の仕様・運用ドキュメントに記載・更新して恒久的に保持する。

### 6.5 物件種別別 Base パーサー階層設計原則
- **階層型パーサーアーキテクチャ**: `ParserBase` 直下に、物件種別ごとの Base パーサークラス（`MansionParserBase`, `KodateParserBase`, `TochiParserBase`, `InvestmentParserBase` 等）を階層的に配置する。
- **全抽象メソッド化**: `ParserBase` には全種別共通項目（`_parsePropertyName`, `_parsePriceStr`, `_parsePrice`, `_parseAddress`, `_parseTransport1` 等）の `@abstractmethod` を定義し、種別特有のパース項目は各種別 Base クラスで `@abstractmethod` として定義する。
- **派生パーサーの完全継承強制**: 各社のパーサークラスは対応する種別別 Base クラスを継承し、未実装の抽象メソッドが存在しないよう厳格に保証する。

### 6.6 ライブ到達・全フィールド動的統合テスト設計原則
- **動的詳細URL抽出**: 各不動産サイトのスタート/一覧URLから最新アクティブ物件の詳細URLを自動抽出する。
- **全定義フィールド検証**: 単一物件パース後、そのモデルで定義された全取得対象フィールド（価格・住所・面積・間取り・構造・築年・交通・建蔽率・容積率等）を取り出し、パース漏れ（意図しない `None` や空文字列）が発生していないかを包括アサーションする。


### 6.7 クローラー優先順位制御設計原則 (Smallest-Site-First)
- `run_all_crawlers.py` の実行リスト構成において、処理データ量の少ない小規模サイト・ハウスメーカー系・電鉄系サイトを先頭に配置する。
- 処理時間が長くなりがちな大手ポータル（Homes, Athome）および大手仲介を後半に割り当てることで、パイプライン中断時でも収集済みサイト数を最大化する。

### 6.8 連続タイムアウト Fast-Fail ＆ サーキットブレイカー設計原則
- 同一サイトに対するリクエストで連続 3 回以上のタイムアウト/通信不能が発生した場合、ジョブ実行エンジンが状態異常を検出して当該サイトの処理を即時 Abort（中断）する。
- リトライの無限ループや後続処理の完全停止（ハングアップ）を防止する。

### 6.9 0件取得失敗分類 ＆ 404掲載終了フィルタリング原則
- **Zero-Count Failure**: クローリングプロセスが正常終了しても取得件数が 0 件の場合は「成功」として扱わず「0件取得異常」としてシステムログ・Slackへ失敗判定を発報する。
- **404/掲載終了通知除外**: 対象詳細URLが 404 (Not Found) または掲載終了状態である場合は物件削除ライフサイクルとして検知し、Slack エラーアラートへの発報から自動除外する。

### 6.10 Slack疎通事前自己チェック設計原則 (Step 0)
- ジョブ起動前段階で `src/crawler/scripts/debug_tools/check_slack_connection.py` を事前実行し、設定中の全 Slack チャンネルへの API 送信権限およびチャンネル存在有無をテストする。
- 疎通失敗時はメインパイプラインの起動前に即座に失敗ログを出力して停止する。

### 6.11 本番コンテナイメージのアセット同梱設計原則 (Dockerfile Packaging)
- クローラー実行に必要な静的セレクター設定ファイル（`config/selectors/*.yaml`）は、本番 Docker イメージのビルド時に `/app/config/` 配下へ漏れなく COPY 同梱する。
- ローカル環境のボリュームマウント（ホストパス直結）への暗黙依存を排除し、Cloud Run 等のサーバーレス環境でもパーサーが `FileNotFoundError` を起こさず自己完結して動作可能であることを保証する。

### 6.12 リストページリンク抽出の物件種別・賃貸フィルタリングおよびパース安全性設計原則
- **種別外・賃貸リンクの厳格除外**: `baseParser.py` の `_parsePageCore` において、一覧ページから抽出されるリンクについて、`/chintai/`, `/rent/` などの賃貸物件URLおよび他種別へのクロスリンクを自動除外する。
- **セレクターパスプレフィックス照合**: `xpath_pattern` で `contains(@href, '...')` が指定されている場合、一覧解析時にその必須パス文字列（例: `/tochi/detail_`, `/mansion/detail_` 等）を抽出し、一致しない関連リンク（マンションおすすめリンク等）を `yield` 対象から排除する。
- **文字列操作およびシリアライズのNoneガード**: 各パーサー（`sumifuParser.py` 等）において、属性値の取得や文字列正規化（`normalize` 等）を行う際は `NoneType` に対する `.replace()` 呼び出しや、`lxml.html.tostring` への BeautifulSoup オブジェクト直接渡しを排除し、型安全かつ例外フリーなパース処理を保証する。

### 6.13 DB保存時文字列フィールドNoneサニタイズ原則および完全修飾URL結合ガード
- **CharField/TextField の None サニタイズ**: `baseParser.py` の `clean_parsed_item` において、`models.CharField` および `models.TextField` を対象に、値が `None` でかつ `not field.null`（DB側でNOT NULL制約）の場合は、一律空文字 `""` にサニタイズする。これにより、パース処理で `None` が代入された場合でも `IntegrityError: (1048, "Column '...' cannot be null")` の発生を完全に防ぐ。
- **URL結合における urljoin 適用原則**: 各パーサー（`sumifuParser.py` 等）において、リンク先URLを組み立てる際は文字列単純結合（`self.BASE_URL + linkUrl`）を廃止し、すべて `urllib.parse.urljoin` を適用する。これにより、取得したリンクが既に完全修飾URL（`https://...`）である場合に二重ホスト名（`www.stepon.co.jphttps:443` 等）が発生し DNS 解決不能となるバグを根絶する。

### 6.14 GCP Cloud Logging 構造化ロギングおよびログレベル適正化設計原則
- **GCP Cloud Logging 標準フォーマット準拠**:
  - `src/crawler/package/utils/logging_config.py` に Google Cloud Logging 準拠のカスタムプロセッサを実装。
  - 出力フィールド: `severity` (DEBUG/INFO/WARNING/ERROR/CRITICAL), `message`, `timestamp` (ISO 8601 UTC), `logger`, `logging.googleapis.com/sourceLocation` (`file`, `line`, `function`)。
  - 標準ライブラリ `logging` の出力を `structlog.stdlib.ProcessorFormatter` でブリッジし、プロジェクト内のすべての `logging.getLogger(__name__)` を自動で構造化。
- **環境自動判定と文字コードUTF-8強制**:
  - `K_SERVICE`, `CLOUD_RUN_JOB`, `GOOGLE_CLOUD_PROJECT`, `IS_CLOUD="true"`, または `LOG_FORMAT="json"` が存在する場合は JSON 構造化モード、それ以外はローカルコンソールモードで動作。
  - `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` および `sys.stderr.reconfigure(encoding="utf-8", errors="replace")` を初期化時に実行し、GCP/Windows/Docker環境での日本語文字化け（`?` 置換）を根絶。
- **ログレベルの適正化**:
  - 毎物件発生する `Local routing: ...`, `Middleware Request/Response: ...`, `start/finished afterRunProc`, `Attempting/Successfully saved item (Single): ...` はすべて `DEBUG` レベルへ適正化。
  - 例外発生時は多重ログ出力を廃止し、単一の `logger.error(..., exc_info=True)` に集約して完全なスタックトレースを単一のJSONペイロード内に格納する。
### 6.15 野村不動産スペックテーブルのモーダル用語集除外およびツールチップ/ヘルプ除去原則
- **モーダル用語集テーブルの除外**: 野村不動産の詳細ページに配置されている `div.fullModal` などのモーダルダイアログ内の用語解説用テーブルは、物件スペックではなく用語説明であるため、スペック抽出（`_scrape_specs`）対象から完全に除外する。
- **th/dt/status からのヘルプ・ツールチップ要素除去**: `th`、`dt`、`item_status_title` のテキスト抽出前に、`.item_help`, `.icon_help`, `.tooltip`, `.help` 等の要素を `decompose()` してキー名に混入するのを防止し、正規化キー（`専有面積`, `間取り` 等）を正確に保持する。
- **ハイライトカードからの専有面積フォールバック**: `_parseSenyuMenseki` において、`specs` からの取得に加え、ページ内サマリーブロック（`td > div.inner` や `div.inner > div.heading: 専有面積` ➔ `p`）からの直接抽出フォールバックを実装し、NOT NULL 制約カラムの `IntegrityError` 発生を完全に抑止する。

### 6.16 Dependabot日次自動マージ＆自律修復スクリプト設計原則
- **モジュール配置**: `src/crawler/scripts/ops/dependabot_automerge.py`
- **主要クラス・関数**:
  - `DependabotPrInspector`:
    - `fetch_dependabot_prs()`: `gh pr list --app dependabot --state open --json number,title,mergeable,statusCheckRollup,headRefName,url` により一覧取得。
    - `evaluate_pr_status(pr_data)`: CI checks（`conclusion`, `status`）および `mergeable` を解析し、状態（`MERGE_READY`, `NEED_REBASE`, `CI_RUNNING`, `CI_FAILED`）を分類。
  - `DependabotAutoMerger`:
    - `execute_merge(pr_number)`: `gh pr merge <number> --squash --delete-branch` を実行。
    - `request_rebase(pr_number)`: コンフリクトまたは `master` 遅延に対し、`gh pr update-branch` または PR コメントに `@dependabot rebase` を投稿して自動再生成。
    - `report_summary()`: 処理結果（マージ成功件数、リベース要求件数、CI実行中・失敗件数）を集計出力。
- **CLIオプション**:
  - `--dry-run`: 実際のマージやコメント投稿を行わず状態判定のみ出力（ローカル監視用）。
  - `--auto-rebase`: コンフリクト/遅延PRに対して自動リベース要求を発行。
  - `--auto-merge`: CI成功済みPRの自動マージを実行。
- **GitHub Actions 連携 (`.github/workflows/dependabot-automerge.yml`)**:
  - 定時（JST 09:00 / UTC 00:00）に実行され、`--auto-merge --auto-rebase` を指定してスクリプトをキック。
  - 実行サマリーを `$GITHUB_STEP_SUMMARY` へ Markdown 出力。

### 6.17 CI並列分散ワークフロー・差分スキップおよび先行実行設計仕様
- **pytest-xdist マルチプロセス並列化**:
  - `pytest -n auto` を導入し、CI仮想マシン（4 vCPU）のCPUリソースを自動検出し並列実行する。
  - `pytest-cov` の `--cov` オプションと併用し、並列テスト実行結果からカバレッジをマージして `coverage.xml` を出力する。
- **test.yml マトリクス並列化および集約ゲート**:
  - `strategy.matrix.test-group`:
    - `unit`: `src/crawler/tests/unit/`（単体テスト群、428件）
    - `integration`: `src/crawler/tests/integration/`（`test_live_reachability.py`, `test_crawler_pipeline_e2e.py`）
    - `ml`: `src/crawler/tests/test_ml_pipeline.py src/crawler/tests/test_image_handler.py`（ML学習・画像処理テスト）
  - 各マトリクスジョブ（`test-matrix`）が独立した GitHub Actions ランナーで完全並行稼働。
  - 集約ジョブ `test`（`needs: test-matrix`）により、ブランチ保護ルール互換性を維持しつつ全マトリクスの合否を一元判定。
- **変更差分フィルタリング (`dorny/paths-filter`)**:
  - `docs`: `['docs/**', '*.md', '.agents/**', 'LICENSE']` のみの変更時はテスト・Dockerビルドを完全スキップ。
  - `terraform`: `['terraform/**']` の変更時はアプリテストをスキップして `terraform-plan` のみ実行。
  - スキップ時でも集約ジョブ `test` は成功ステータスを返し、PRマージをブロックしない。
- **SonarCloud 先行独立パイプライン**:
  - PR作成/更新時に最優先で独立起動。
  - `-m "not live"` オプションにより外部実サイトへの生通信テストを除外し、モック＆単体テストで純粋なコードカバレッジを高速測定（所要時間2分以内）。
- **Production PR 完全並列化**:
  - `production` 宛て PR では `Verify Source Branch is master`、Terraform Plan、テストマトリクス、Snykスキャンを待ち時間ゼロで完全同時並行起動。
- **Docker BuildKit GHA キャッシュ連携**:
  - `docker/setup-buildx-action` と BuildKit cache (`type=gha,scope=app`) を利用し、Dockerレイヤーキャッシュ（OS依存・Python依存パッケージ・Playwrightブラウザ）をGitHub Actions Cache上に永続化。
  - キャッシュヒット時はイメージの再ビルドをスキップし、起動オーバーヘッドを4分半から20秒未満に圧縮する。

### 6.18 不動産価格 (price) BigIntegerField 拡張および 32-bit オーバーフロー防止ガード設計原則
- **BigIntegerField へのモデル拡張**: `PropertyBaseModel.price` を `models.IntegerField`（符号付き 32-bit INT、上限 2,147,483,647円＝約21.4億円）から `models.BigIntegerField`（符号付き 64-bit BIGINT、上限 約922京円）へ変更する。これにより、一棟売りビル、投資用大規模マンション、都心高級レジデンス等の21.4億円超（24億円、30億円、50億円等）の高額物件において発生する `django.db.utils.DataError: (1264, "Out of range value for column 'price' at row 1")` を根絶する。
- **保存前サニタイズ (クランプ安全ガード)**: `baseParser.py` の `clean_parsed_item` において、`price` 値が数値型として正しくパースされているかを保証し、未マイグレーション環境等における MySQL `INT` カラムへの適合性を担保するフェイルセーフ機構を配置する。

### 6.19 住友不動産ステップ投資物件 Shift_JIS(CP932) エンコーディング適正化原則
- **Shift_JIS(CP932) レスポンスの正確なデコード**: 住友不動産ステップの投資用物件詳細ページ（`/pro/detail_...`）はサーバーから Shift_JIS (CP932) で配信される。`SumifuInvestmentParserBase.getCharset()` の戻り値を `"cp932"` に明示指定し、従来の UTF-8 強制デコードによる全日本語文字（`所在地`, `価格` 等）の化け（`\ufffd` への置換）およびそれに伴う `StrictExtractionFailed: address is empty` 例外（48時間で109件発生）を根絶する。

### 6.20 非物件リンク・JavaScript URL 厳格除外および数値カラム NOT NULL/オーバーフローガード原則
- **非物件リンク・JavaScript 擬似リンクの除外**: `baseParser.py` の `_parsePageCore` および各社パーサーの `parsePropertyListPage` / `parseNextPage` において、`javascript:`, `mailto:`, `tel:`, `#`, および問い合わせページ（`/inquiry`, `/contact`）のリンクを完全除外する。これにより `urljoin` による `https://...javascript:void(0);` 結合異常（`InvalidUrlClientError`）および問い合わせページの誤パースによる `'NoneType' object has no attribute 'replace'` を根絶する。
- **数値フィールドの NOT NULL ガードおよび 32-bit INT クランプ**: `clean_parsed_item` において、`annualRent`, `monthlyRent`, `soukosu`, `chikunen` 等の数値カラムが `None` でかつ DB 側 `NOT NULL` 制約の場合は自動で `0` を代入し `IntegrityError (1048)` を防止する。また `IntegerField` に対し 21.4億円超の値が代入された際は 32-bit 最大値（`2147483647`）へ自動クランプし `DataError (1264)` の発生を完全に抑止する。
### 6.21 Slack アラートチャンネル通知内容のERRORレベルログ同期原則
- **アラート送信時のERRORログ出力強制**: `package.utils.slack.send_slack_message` において、送信先がアラートチャンネル（`is_alert_channel(channel) == True`）である場合、Slack API の成否に関わらず、必ず `logger.error(f"[SLACK ALERT -> {channel}]:\n{message}")` を同期出力する。
- **アラートチャンネル判定ロジック (`is_alert_channel`)**:
  - チャンネル名が `alerts-` で始まる場合（`#alerts-mansion`, `#alerts-kodate`, `#alerts-tochi`, `#alerts-invest-apartment`, `#alerts-invest-kodate`, `#alerts-invest` 等）
  - チャンネル名が `property_alert` の場合
  - 環境変数 `SLACK_ALERT_*`（`SLACK_ALERT_PROPERTY_ALERT`, `SLACK_ALERT_MANSION`, `SLACK_ALERT_KODATE`, `SLACK_ALERT_TOCHI`, `SLACK_ALERT_INVEST_APARTMENT`, `SLACK_ALERT_INVEST_KODATE`, `SLACK_ALERT_CHANNEL_ID` 等）で設定されたIDまたは名称と一致する場合
  - 既知のアラートチャンネルID（`C0BJWUCTRNU`, `C0BHZA5ASDT`, `C0BJ2JVGCLS`, `C0BJ6B4R3E0`, `C0BJ0KSJEDC` 等）に一致する場合
- **GCP Cloud Logging / 外部監視との連携**: アプリケーションログに `severity: ERROR` で出力されることにより、GCP Cloud Logging のログスキャン（`severity>=ERROR`）や 24時間監視バッチで Slack アラート発報の事実・内容が漏れなく集約されることを保証する。
- **データバリデーションスクリプト (`validate_data.py`) のログレベル適正化**: 異常データ検出時のチャンネル通知ログを従来の `logging.info` から `logging.error` に改め、アラート内容全文をエラーログとして確実に残す。

---

## 7. 参照ドキュメント

- [データベース定義書 (Database Schema)](database_schema.md): 完全なテーブル・カラム定義
- [API構造ドキュメント (API Structure)](api_structure.md): エンドポイント構造と処理フロー

---

**最終更新**: 2026年9月20日  
**バージョン**: 2.2 (Slackアラートチャンネル通知内容のERRORレベルログ同期原則追記)


