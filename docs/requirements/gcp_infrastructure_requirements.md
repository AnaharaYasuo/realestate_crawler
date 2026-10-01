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
  - ProxySQL は単一 Compute Engine インスタンス（`proxysql-instance-${var.environment}`）および Direct VPC Egress 構成を採用する。
  - パイプライン（`run_pipeline.py`）起動時、Coordinator は DB アクセス前に ProxySQL インスタンス（または設定に応じた MIG）の起動・稼働状態を検証し、ポート6033の疎通健全性を確認（起動チェック）してから DB 処理に進むこと。単一インスタンス構成時は存在しない MIG Autoscaler の操作をスキップし、HTTP 404 エラーによるクラッシュを防止すること。
  - セーフティネット（`ensure_resources_stopped.py`）は、単一インスタンス名（`PROXYSQL_INSTANCE_NAME`）を優先検証し、MIG が存在しない場合でも 404 エラーで誤アラートを発報せず、単一インスタンスを安全に検査・停止すること。
  - DB疎通確認（`wait_for_db.py`）は、短時間のソケット疎通事前チェック（最大3〜5秒）を実施し、未起動・不通時に OS の TCP SYN タイムアウト（130秒×リトライ回数＝1時間）でハングせず迅速に Fail-Fast すること。
  - Cloud Run コンテナ内での GCE リソース操作（ProxySQL MIG リサイズ）は、外部 CLI（`gcloud`）に依存せず `google-cloud-compute` または REST API により自己完結すること。
  - オートスケーラー管理下 MIG に対する直接 resize 禁止（GCP API 制約）を回避するため、スケールイン/アウトはオートスケーラー設定（`min_replicas`/`max_replicas`）を介して安全に行うこと。
  - ProxySQL VM の初期化・パッケージ導入・ヘルスチェック通過までの所要時間を考慮し、ヘルスチェック待機時間は最低 240 秒のタイムアウトを確保すること。
  - バックエンド Cloud SQL インスタンスの稼働状態（`RUNNABLE`）を事前に確認し、未起動時の原因究明を迅速化すること。
- **Direct VPC Egress への統合 & Connector 廃止**:
  - Serverless VPC Access Connector の常時稼働インスタンス（e2-micro 2台、月額約2,110円）を完全廃止し、Cloud Run の Direct VPC Egress 機能 (`network_interfaces`) を用いて VPC サブネットへ直接接続し、常時固定費を $0 化すること。
- **ILB 撤廃 & ProxySQL 単一インスタンス・スケールアップ対応**:
  - 常時課金が発生する内部ロードバランサー (ILB) 転送ルール（月額約4,360円）を完全撤廃すること。
  - ProxySQL は固定内部 IP を持つ単一 Compute Engine インスタンス（初期値 `e2-micro`）として構成し、接続リクエストがインスタンスサイズに見合わなくなった場合はインスタンスタイプ変更（垂直スケールアップ: `e2-small` / `e2-medium`）により対処すること。
- **Artifact Registry ストレージ最適化 & ライフサイクル制御**:
  - CI/CD パイプラインによる継続的なコンテナビルドに伴うイメージ蓄積を防止するため、Terraform により最新 3 世代のみを保持（`keep_count = 3`）し、タグなし（UNTAGGED）イメージを自動パージするクリーンアップポリシーを定義すること。
  - 本番デプロイ時（GitHub Actions `deploy-production.yml`）に、新イメージ push 直後に最新 3 世代を超過した古いイメージを即座に削除（プルーニング）し、ストレージ容量肥大化と保管コストを即時抑止すること。
- **月額費用目安**:
  - Cloud SQL 最小インスタンス（db-f1-micro / db-g1-small）および GCS、Cloud Run Jobs 稼働時間課金を含め、月額予算（2,000円〜数千円）の範囲内で運用可能であること。

### 3.4 予算管理 & 予期せぬ過大請求防止要件 (Budget Alerts & Safety Net)
- **多段階アラート通知**:
  - 月額予算額（初期値: 2,000円）に対し、実費用の 50%, 80%, 100% 到達時、および「月末予測値が120%に達する見込み」の時点で即座にメールおよびPub/Subへアラートを発報すること。
- **早期警戒 (Forecasted Alert)**:
  - クローラー暴走や不慮のリソース増大が発生した際、月末を待たずに早期検知できること。
- **ゾンビ課金防止セーフティネット (Deadman's Switch & Guardrails / Execution-Aware Safety Net)**:
  - 時刻ベースの単純強制停止ではなく、**Cloud Run Job Execution の稼働状態と因果関係に基づく動的停止判定**を行うこと。
  - **稼働状態判定 & 執行猶予 (Grace Period)**:
    - 関連ジョブ（`realestate-crawler-pipeline-*`, `realestate-migrate-*` 等）の Execution が `RUNNING` 状態かつ許容時間（タイムアウト以内）の場合、ProxySQL 停止をスキップし、正常なクローリング処理を妨害しないこと。
    - ProxySQL 起動から 15分間（900秒）は Grace Period（起動直後猶予）として停止をスキップし、起動〜ヘルスチェック〜ジョブ起動間のレースコンディション（誤爆停止）および処理完了直後の早期停止による再起動ループを完全に遮断すること（Issue #518 により 10分 ➔ 15分へ延長）。
  - **完全停止戦略 (Dual Hard-Kill on Hang)**:
    - Cloud Run Job Execution がタイムアウト上限（最長ジョブのクローラー 7200秒 + 猶予 600秒 = 7800秒。Issue #550）を超過してハングしている「真のゾンビ」を検知した場合、ProxySQL だけを停止する片肺停止を禁止し、**Cloud Run Job Execution のキャンセル（強制停止）と ProxySQL インスタンスの停止の両方を同時に強制実行**してコンテナ課金とインスタンス課金を完全に遮断すること。
  - **親不在時の即時停止**:
    - 関連する Cloud Run Job Execution が存在しない（親不在）かつ Grace Period を超過している場合は、直ちに ProxySQL を停止して Slack へ通知すること。
- **Coordinator タイムアウト自律的フェイルセーフ (Graceful Self-Shutdown & Signal Handling)**:
  - Cloud Run Job の Coordinator（Task 0）実行中、Cloud Run タスクタイムアウト（7200秒。Issue #550 で 3600 秒から延長）に達する前に、自律的に安全停止マージン（バッファ時間: 300秒前）を検知して後続ステップを安全に中断し、確実に ProxySQL を停止（teardown）完了して終了すること。
  - Cloud Run からの強制終了シグナル（SIGTERM / SIGINT）を受信した場合でも、シグナルハンドラおよび atexit により同一プロセス内で即座にインライン teardown を実行して ProxySQL 停止を保証すること。
  - 他タスク完了待機（`wait_for_all_tasks`）は、ジョブ全体の残り許容時間に応じて動的にタイムアウト上限を制限し、Cloud Run のタイムアウトによる突然死・teardown スキップを未然に防止すること。
  - タスクアレイモードの Coordinator は、自タスク以外に終端状態（COMPLETED / FAILED）でないタスク（`CrawlerTaskExecution` 未登録を含む）が存在する場合、teardown / atexit / SIGTERM のいずれの経路でも共有 ProxySQL を停止してはならない。タスク状態を DB から取得できない場合も停止をスキップし、停止は Safety-Net に委譲すること（Issue #536）。停止判定・完了バリア・集約レポートは同一 Cloud Run 実行（`CLOUD_RUN_EXECUTION`）のタスク行のみを対象とし、同日の別実行の終端行で停止・バリア通過を許可してはならない。実行日はパイプライン起動時に一度だけ確定し、日付を跨ぐ実行でもタスク登録と照会で同一の実行日を用いること。停止をスキップした場合は後続の終了経路（atexit 等）で再判定できること。
  - Cloud Run Job の同時実行数（`crawler_parallelism`）はタスク数（`crawler_task_count`）と同値とし、全タスクを同時に起動すること。2 巡目のタスクが Coordinator の停止後に起動して DB 不通で全滅する事態、および Safety-Net の hung 判定閾値超過を防止する（Issue #536）。
- **クロールと ML パイプラインのジョブ分離 & 自動再実行禁止 (Issue #549)**:
  - クローラージョブ（`realestate-crawler-pipeline-*`）のタスクアレイ実行（`task_count > 1`）では、Coordinator を含む全タスクが自タスクのクロールのみを実行して終了すること。他タスク完了待機・全タスク集約レポート・データ検証・学習・価格推定・お宝通知・精度診断をクローラージョブ内で実行してはならない（1 タスクのタイムアウト（当時 3600 秒）にクロールと ML を詰め込むことによる恒常的タイムアウトを防止）。単一実行（`task_count <= 1`、ローカル実行等）は従来どおりクロール後に後続ステップを実行してよい。
  - 集約レポート・データ検証・学習・価格推定・お宝通知・精度診断は ML Pipeline Job（`realestate-ml-pipeline-*`）が日次 1 回だけ実行すること。ML Pipeline Job は Cloud Scheduler により、クローラー起動（16:00 UTC）からクローラーのタイムアウト（7200 秒、Issue #550）経過後の 18:10 UTC に起動し、完了バリア未達の場合も完了分のデータで続行すること（`--force`）。
  - ML Pipeline Job は起動時に Cloud SQL 稼働確認・ProxySQL 起動・疎通確認・DB 待機を自ら行い、終了時（異常時を含む）に ProxySQL を停止すること。
  - クローラージョブおよび ML Pipeline Job の `max_retries` は 0 とすること。タイムアウトや失敗は同じ処理を再実行しても解消しないため、自動再実行による課金の倍増・ProxySQL の停止/再起動の繰り返し・重複 Slack 通知を禁止する。
  - ML Pipeline Job のタイムアウトは Safety-Net の hung 判定閾値（7800 秒）未満の 3600 秒とし、正常実行中の ML パイプラインが Safety-Net にキャンセルされないこと。
- **クローラータスク上限の 2 時間化と連動スケジュール (Issue #550)**:
  - クローラージョブの 1 タスクあたりのタイムアウトは 7200 秒（2 時間）とし、Terraform `crawler_timeout` から導出した `CLOUD_RUN_JOB_TIMEOUT_SEC` をジョブへ渡して、アプリの内部締め切り（安全停止マージン 300 秒前）を Cloud Run のタスクタイムアウトと一致させること。
  - Safety-Net の hung 判定閾値は最長ジョブのタスクタイムアウト（7200 秒）+ 猶予（600 秒）= 7800 秒以上とし、2 時間以内で正常稼働中の実行をキャンセルしないこと。
  - ML Pipeline Job はクローラー最遅終了（16:00 UTC + 7200 秒 = 18:00 UTC）後の 18:10 UTC（03:10 JST）に起動すること。
  - Cloud SQL 自動バックアップはクローラー最遅終了および ML Pipeline Job 最遅終了（18:10 UTC + 3600 秒 = 19:10 UTC）以降の 20:00 UTC（05:00 JST）に開始すること。
  - Safety-Net（17-21 UTC 毎時）はクローラー最遅終了（18:00 UTC）および ML Pipeline Job 最遅終了（19:10 UTC）以降にも起動すること。
- **クロール詳細 URL の重複ディスパッチ防止**:
  - 一覧（中間）ページから抽出した詳細 URL は、同一ページ内・同一クロールプロセス内の別一覧ページ間で重複して詳細処理にディスパッチしてはならない（詳細 API ごとに 1 回）。バリデーション失敗で保存されない物件の再取得ループによるクロール時間浪費を防止する（Issue #537）。
- **リソースタグ・ラベル統一による費用分析**:
  - すべてのインフラリソースに対し、統一されたラベル（`project`, `environment`, `component`, `managed_by` 等）を付与し、BigQuery Billing Export による詳細なコスト内訳分析を可能とすること。

### 3.5 データベース・コネクションプーリング要件 (ProxySQL Connection Pooling Layer)
- **多重接続保護 & リソース管理効率化 (Connection Multiplexing & Saturation Prevention)**:
  - クライアント（大量並行クローラー、API等）からの無数の接続リクエストを受け止め、バックエンド Cloud SQL (MySQL 8.0) へはデータベースが安全に耐えられる上限ギリギリのコネクション数（設定値）を安定維持・多重化（Connection Multiplexing）してリソース効率を最大化すること。
  - バックエンド接続が上限に達した場合でも、ProxySQL 側でキューイング・バッファリングを行い、Cloud SQL 側の `Too many connections` や OOM によるクラッシュを完全に遮断すること。
- **単一インスタンス構成 & 垂直スケールアップ対応 (Single Instance & Scale-Up Strategy)**:
  - ILB による水平分散オートスケールを廃止し、常時課金のない単一 Compute Engine インスタンスとして運用すること。
  - 接続リクエストやトラフィックが現在のインスタンスサイズで見合わなくなった場合は、インスタンスタイプ変更（`e2-micro` ➔ `e2-small` ➔ `e2-medium`）による垂直スケールアップで対処すること。
  - バックエンド Cloud SQL への接続数は、上限（50等）に設定し、Cloud SQL の耐用上限を安全に保護すること。
- **起動スクリプトの APT ロック競合耐性 (Startup Script Lock-Contention Resilience)**:
  - ProxySQL インスタンスの起動スクリプトは、OS 起動直後の自動更新（unattended-upgrades 等）による DPKG/APT ロック競合で `set -euo pipefail` により即死しないよう、`apt-get` 実行前に DPKG/APT ロック解放を待機すること。
  - `apt-get` の実行は最大 5 回まで指数バックオフでリトライし、一時的なロック競合・通信瞬断でヘルスチェックタイムアウトに至らないこと（Issue #518）。
- **クローリング中の DB/ProxySQL 死活監視連動 Fast-Fail (DB Liveness Fast-Fail)**:
  - `run_all_crawlers.py` はジョブ実行ループ中に DB 接続先（ProxySQL `10.0.0.10:6033` 等）へのソケット疎通を定期監視（既定 15 秒間隔、有限タイムアウト 3 秒）すること。
  - 連続 3 回の疎通失敗で DB 応答喪失と判定し、アクティブなクローラー子プロセス群を即時安全停止し、Slack アラートを発報した上でパイプラインを非ゼロ終了すること（Issue #518）。
- **固定内部 IP による直接ルーティング (Direct Routing with Static Private IP)**:
  - サブネット内に固定内部 IP を割り当て、Cloud Run (Direct VPC Egress 経由) からは ILB を介さず単一のプライベート IP（ポート 6033）に向けて直接接続すること。
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

### 3.8 MySQL 認証プラグイン標準化 & TLS 接続要件 (MySQL Auth Plugin & TLS Standardization)
- **非推奨認証プラグイン `mysql_native_password` の完全撤廃**:
  - Cloud SQL インスタンス設定から非推奨フラグ `default_authentication_plugin = "mysql_native_password"` を削除し、MySQL 8.0 標準の `caching_sha2_password` に準拠すること（Issue #572）。
  - Cloud SQL 上の全ユーザー（`sumifu`, `monitor` 等）の認証プラグインを `caching_sha2_password` に移行し、非推奨警告スロットル通知ログ（`[Note] [MY-000000] [Server] Error log throttle is enabled...`）を恒久的に解消すること。
- **ProxySQL バックエンド TLS 暗号化接続 (`use_ssl=1`) の標準適用**:
  - ProxySQL の `mysql_servers` 定義において `use_ssl=1` を適用し、Cloud SQL へのバックエンド通信を TLS 暗号化すること。
  - これにより非 SSL 接続時の RSA 公開鍵交換要件をバイパスし、セキュアかつ高速に `caching_sha2_password` 認証を確立すること。



