# GCP インフラストラクチャ要件定義書 (GCP Infrastructure Requirements)

## 1. 背景と目的
現在ローカルの Docker Compose 環境で実行されている不動産クローラー・価格推定パイプライン（20社以上のポータル・仲介サイト巡回、MLによる割安度推定、Slack通知）を、高い可用性・保守性およびコスト効率を備えた Google Cloud Platform (GCP) 上のクラウドネイティブ環境へ移行する。
また、将来的なサイト別分散並列実行（案C）への拡張を視野に入れ、すべてのクラウドインフラを Terraform による IaC (Infrastructure as Code) で宣言的に管理・再現可能とする。

---

## 2. システム要件

### 2.1 機能要件
1. **日次自動バッチ実行**:
   - 毎日深夜 01:00 (JST) / 16:00 (UTC) に全サイトのクローリングおよびML評価パイプラインを自動トリガーできること。
2. **ヘッドレスブラウザ実行能力**:
   - Playwright (Chromium headless) を利用した動的サイト（Athome, Homes等）のレンダリング・巡回がコンテナ内で確実に動作すること（十分な共有メモリ `/dev/shm` または tmpfs の確保）。
3. **データ永続化**:
   - リレーショナルデータ（物件詳細、マスタ情報、地価、評価スコア）を MySQL 8.0 互換データベースに安全に格納できること。
   - 物件画像・エビデンスデータをオブジェクトストレージに高可用・低コストで永続化できること。
4. **Slack 対話および通知**:
   - クローラーの完了通知・エラーアラート・お宝物件レコメンドを Slack Webhook / API 経由で送信できること。
   - Slack Agent が常時またはイベント駆動でリクエストを受信できること。
5. **秘密情報の安全な管理**:
   - DB認証情報、Slackトークン等の機密情報をコード内にハードコードせず、安全に参照・注入できること。

---

## 3. 非機能要件

### 3.1 性能・リソース要件
- **バッチ処理時間**: 全サイトの巡回・評価処理（Cloud Tasks + Cloud Run の分散並列化により大幅短縮）。
- **コンテナスペック**: 1タスクあたり 2〜4 vCPU、4〜8 GiB RAM を確保可能であること。
- **並列分散拡張性 & サイト規模別並行プロセス制御**:
  - 全20〜25社に対して一斉にジョブを開始（会社間並列）可能であること。
  - 各会社に対する同時実行プロセス数（種別並行度）は、取扱物件数およびブラウザ負荷に応じて以下の通り階層的に制御すること：
    - **超大規模ポータル (HTTP: Homes)**: 最大 5 プロセス並行（大量物件の超高速消化）
    - **超大規模ポータル (Browser: Athome)**: 最大 3 プロセス並行（Playwrightの並行消化加速）
    - **大手仲介 (三井, 住友, 東急, 野村, ミサワ)**: 最大 2 プロセス並行（居住用＋投資用のバランス消化）
    - **中小・電鉄・ハウスメーカー (積水, 大和, 旭化成, 小田急等 17社)**: 最大 1 プロセス（同一会社内完全直列で安全・低負荷消化）
  - ML学習（LightGBM, XGBoost, CatBoost, RF）でコンテナのマルチCPUコア（`n_jobs=-1`）を完全活用すること。
  - バルク価格推論（`run_bulk_ml_evaluation.py`）において、マルチスレッド/並行プール（4〜8並行）で物件モデル群を並行推論・永続化できること。
- **パイプライン制御 & 完了検知**:
  - ディスパッチャーによる全タスク投入後、DB（`crawler_task_execution`）上で全タスクの完了を検知し、後続の「データ検証 ➔ ML再学習 ➔ バルク推論 ➔ Slack通知」を一貫自動実行できること。

### 3.2 ネットワーク & セキュリティ要件
- **Bot検知（Anti-Scraping）対策**:
  - クローラーからの外部HTTPリクエストは、Cloud NAT を経由して「固定静的外部IP (Static External IP)」から発信されること（データセンター変動IPによるブロックの低減）。
- **閉域通信 (Private IP)**:
  - クローラーと Cloud SQL 間の通信は、パブリックインターネットに露出させず、Serverless VPC Access を経由したプライベートIP通信（プライベートサービスアクセス）で行うこと。
- **最小権限の原則 (Least Privilege)**:
  - クローラー専用の IAM サービスアカウントを払い出し、必要なリソース（Cloud SQL クライアント、GCS オブジェクト操作、Secret アクセス）のみに権限を限定すること。

### 3.3 コスト最適化要件
- **アイドル時コスト最小化**:
  - クローラー非稼働時間帯（日中の大半）はコンピュートリソース課金を ¥0（サーバーレス）とすること。
  - レガシー・不要リソース（未接続SSDディスク等）の完全排除を維持すること。
- **リソースオンデマンド・ライフサイクル制御**:
  - 常時課金が発生する ProxySQL MIG（`min_replicas = 0`）および Cloud NAT は、クローリングバッチ稼働時間帯（01:00 JST等）のみオンデマンドで起動・有効化し、処理完了と同時に自動停止（スケールイン `size = 0`）すること。
- **Direct VPC Egress への統合**:
  - Serverless VPC Access Connector の常時稼働インスタンス（e2-micro 2台）を廃止し、Cloud Run の Direct VPC Egress 機能を用いて VPC サブネットへ直接接続し、常時固定費を削減すること。
- **Artifact Registry ストレージ最適化 & ライフサイクル制御**:
  - CI/CD パイプラインによる継続的なコンテナビルドに伴うイメージ蓄積を防止するため、Terraform により最新 3 世代のみを保持（`keep_count = 3`）し、タグなし（UNTAGGED）イメージを自動パージするクリーンアップポリシーを定義すること。
  - 本番デプロイ時（GitHub Actions `deploy-production.yml`）に、新イメージ push 直後に最新 3 世代を超過した古いイメージを即座に削除（プルーニング）し、ストレージ容量肥大化と保管コストを即時抑止すること。
- **月額費用目安**:
  - Cloud SQL 最小インスタンス（db-f1-micro / db-g1-small）および GCS、Cloud Run Jobs 稼働時間課金を含め、月額数千円〜1万円以内の範囲で運用可能であること。

### 3.4 予算管理 & 予期せぬ過大請求防止要件 (Budget Alerts & Safety Net)
- **多段階アラート通知**:
  - 月額予算額（初期値: 10,000円）に対し、実費用の 50%, 80%, 100% 到達時、および「月末予測値が120%に達する見込み」の時点で即座にメールおよびPub/Subへアラートを発報すること。
- **早期警戒 (Forecasted Alert)**:
  - クローラー暴走や不慮のリソース増大が発生した際、月末を待たずに早期検知できること。
- **ゾンビ課金防止セーフティネット (Deadman's Switch & Guardrails)**:
  - バッチ異常終了やクラッシュによって ProxySQL MIG や Cloud NAT が停止しなかった場合に備え、毎朝 05:00 JST にリソース停止状態を自動点検し、稼働中の場合は強制停止 (`size = 0`) して Slack へ警告を発報するデッドマンズスイッチを備えること。
  - 日中帯（06:00〜24:00 JST）に ProxySQL インスタンスが稼働している場合は、Cloud Monitoring から重大度 ERROR で即時アラートを発報すること。
- **リソースタグ・ラベル統一による費用分析**:
  - すべてのインフラリソースに対し、統一されたラベル（`project`, `environment`, `component`, `managed_by` 等）を付与し、BigQuery Billing Export による詳細なコスト内訳分析を可能とすること。

### 3.5 データベース・コネクションプーリング要件 (ProxySQL Connection Pooling Layer)
- **多重接続保護 & リソース管理効率化 (Connection Multiplexing & Saturation Prevention)**:
  - クライアント（大量並行クローラー、API等）からの無数の接続リクエストを受け止め、バックエンド Cloud SQL (MySQL 8.0) へはデータベースが安全に耐えられる上限ギリギリのコネクション数（設定値）を安定維持・多重化（Connection Multiplexing）してリソース効率を最大化すること。
  - バックエンド接続が上限に達した場合でも、ProxySQL 側でキューイング・バッファリングを行い、Cloud SQL 側の `Too many connections` や OOM によるクラッシュを完全に遮断すること。
- **動的オートスケーリング & 高可用性 (Autoscaling: Min 1, Max 2 & Multi-Zone)**:
  - 通常時は最小構成の 1 台（`min_replicas = 1`）で待機し、クローラー実行時やAPI高負荷時には CPU 利用率（70%等）に応じて最大 2 台（`max_replicas = 2`、2つの異なるゾーン）へ動的オートスケールすること。
  - スケールイン（2台 ➔ 1台）時のクエリ切断を防止するため、内部ロードバランサー（ILB）側でコネクションドレイン（Connection Draining: 300秒）を適用すること。
  - バックエンド Cloud SQL への接続数は、各インスタンス上限を 50 に設定し、2台スケール時でも計 100 接続以内に収めて Cloud SQL の耐用上限を安全に保護すること。
- **負荷分散 & 透過的接続 (Internal Load Balancer)**:
  - 内部TCPロードバランサー (ILB) を配置し、Cloud Run (VPC Access Connector 経由) からは単一のプライベート IP（ポート 6033）に向けて接続可能であること。
- **Cloud Run / Service からの接続統一 (ProxySQL Direct Routing)**:
  - アプリ（Django）側でのコネクションプーリング（`dj_db_conn_pool` 等）を完全禁止し、`django.db.backends.mysql` かつ `CONN_MAX_AGE = 0` によりクエリ終了時に即時ソケットを切断すること。接続プーリング・多重化は ProxySQL 層に一元集約し、ワーカー急増時の不要なコネクション滞留を排除すること。
  - DBスキーママイグレーション（DDL）を実行する Migrate Job のみ、直接 Cloud SQL（ポート 3306）への接続を維持すること。

### 3.7 サーバーレス分散クローラー ＆ ML パイプライン分離要件 (Distributed Crawler Services & Decoupled ML Jobs)
- **クローラーワーカーのサービス化 (Cloud Run Service + Cloud Tasks)**:
  - クローラー処理を単一ジョブ直列実行から、Cloud Tasks キュー経由で起動される Cloud Run サービスワーカー（`/api/crawl/task`）へ移行すること。
  - 1タスク＝1サイト×1種別に細分化し、Cloud Tasks のレートリミット（`max_dispatches_per_second`）および並列制御（`max_concurrent_dispatches`）により、相手サイトへのアクセス集中（BAN）をインフラ層で抑止すること。
- **0件取得・パース異常時の無限リトライ防止 (Fast-Fail Task Consumption)**:
  - 0件取得異常、パースエラー、相手サイト連続タイムアウト等が発生した場合は、Cloud Tasks が同一異常タスクを無駄に再試行しないよう HTTP 200（または再試行不要ステータス）を返却してタスクを消化し、DB のステータスを `FAILED` に記録して Slack アラートを発報すること。
- **ジョブの二分割 ＆ オンデマンド待機課金ゼロ化 (Two-Phase Decoupled Jobs)**:
  - 親ジョブを「タスク投入役（Dispatcher Job）」と「学習・推論役（ML Pipeline Job）」の2つに分割すること。
  - Dispatcher Job はバッチ開始時に ProxySQL MIG をスケールアウト（`size: 0 -> 1`）し、疎通確認後に Cloud Tasks へタスクを投入して即座に終了（プロセス exit 0）し、クローリング中の親ジョブ待機課金を ¥0 とすること。
  - ML Pipeline Job はクローリング全完了後に起動し、4vCPU / 8GiB の集中リソースで ML モデル再学習・バルク価格推定・お宝物件 Slack 通知を実行し、完了フックで ProxySQL MIG を安全にスケールイン（`size: 1 -> 0`）停止すること。

### 3.6 データベース監視・ヘルスチェック認証およびログ重大度昇格要件 (Database Monitoring & Log Severity Elevation)
- **ProxySQL 監視専用ユーザー (`monitor`) の独立プロビジョニング**:
  - ProxySQL の内部ヘルスチェックモジュール（ping, read_only 判定）が Cloud SQL バックエンドと通信するための専用 MySQL ユーザー (`monitor`) を Cloud SQL 上に安全なランダムパスワードで自動生成・プロビジョニングすること。
  - 監視パスワードは Secret Manager に安全に保管し、ProxySQL 設定ファイル (`/etc/proxysql.cnf`) 内の `mysql_variables` (`monitor_username`, `monitor_password`) に正確に注入して `Access denied (MY-010926)` による認証拒否・スパムログを完全に根絶すること。
- **ProxySQL 管理インターフェースのセキュア化**:
  - デフォルトの管理用認証情報 (`admin:admin`, `radmin:radmin`) の使用を禁止し、Terraform の `random_password` で生成されたセキュアなパスワードを適用して Secret Manager で管理すること。
- **MySQL ログの重大度昇格 (Log Severity Elevation: Note ➔ ERROR)**:
  - MySQL 8.0 において通常 `[Note] [MY-010926]` (NOTICE/DEFAULT) として記録される認証拒否・アクセス遮断ログ (`Access denied for user`) を Cloud Logging のログベースメトリクス (`google_logging_metric`) で確実に捕捉すること。
  - 該当メトリクスを監視する Cloud Monitoring アラートポリシー (`google_monitoring_alert_policy`) を定義し、重大度 `ERROR` として Slack / メールへ即時発報・可視化すること。
- **包括的 MySQL サーバ障害アラート**:
  - MySQL `[ERROR]` ログおよび接続上限到達 (`MY-010048` / `Too many connections`)、ProxySQL MIG の異常インスタンス発生を検知し、重大度 `ERROR` / `CRITICAL` で通知すること。
- **アプリケーションログレベルの適正化**:
  - 外部通信・ミドルウェアにおける 5xx/4xx レスポンス、DBクエリ例外、キャッシュ取得失敗など、システムの不具合・異常を示す事象を `INFO` や `DEBUG` でサイレントに握りつぶさず、必ず `ERROR` または `WARNING` ログとして出力すること。


