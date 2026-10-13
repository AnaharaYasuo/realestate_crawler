# 共有ProxySQL誤認停止防止および全DB接続有限タイムアウト強制 要件定義書 (Issue #916)

## 1. 概要
本要件定義書は、共有インフラ（ProxySQL VM等）の誤認停止による他ジョブの通信断・ハング誤認キルを根絶し、同時に全DB接続へ有限のクエリタイムアウト（\`read_timeout\`）を強制適用するための要件を定義する。

## 2. 背景・課題
1. **AIエージェントによる共有リソース停止の誤認**:
   - 開発セッションでユーザーからの「止めておいて」という指示を受けたAIエージェントが、Cloud Run等で稼働中の他ジョブの存在を確認せず、共有インフラであるProxySQL VM (\`proxysql-instance-prod\`) を直接 \`gcloud compute instances stop\` で停止させた。
2. **単発ジョブによる共有ProxySQLの誤認停止**:
   - \`run_pipeline.py\` の \`_can_stop_shared_proxysql()\` において、単独タスク（\`taskCount <= 1\`）完了時に「他タスク無し」と即時判定し、並行して走っていた日次定期バッチ（Task 0〜4）の存在を無視して共有ProxySQLをシャットダウンした。
3. **クローラー子プロセスにおける MySQL \`read_timeout\` 未設定**:
   - Django の標準設定（\`realestateSettings.py\`）において \`read_timeout\` が未指定であったため、ProxySQL停止時に OS の TCP 再送（25分間）でスレッドが沈黙し、ウォッチドッグによる 600秒ハング誤認キルが多発した。

## 3. 機能要件 (FR)
- **FR-001 (共有インフラ直接停止の禁止とCloud Run直接停止の許可)**:
  - \`.agents/AGENTS.md\` に開発ルールを明文化する。
  - 個別 Cloud Run 実行のキャンセル（\`gcloud run jobs executions cancel <execution_name>\`）やローカルプロセスの停止は許可する。
  - 共有インフラ（ProxySQL VM、Cloud SQL 等）に対するエージェントの自律判断での直接停止コマンド実行は全面禁止とする。
- **FR-002 (全DB接続への有限タイムアウト強制適用)**:
  - \`realestateSettings.py\` の初期化（\`configure()\` および \`get_database_config()\`）において、\`bound_mysql_timeouts()\` を常時適用する。
  - これにより、クローラー子プロセス（\`main.py\`）を含む全 Django DB コネクションで \`connect_timeout\`(10s), \`read_timeout\`(120s), \`write_timeout\`(120s) を保証する。
- **FR-003 (\`run_pipeline.py\` 共有ProxySQL停止ガードの他実行検証)**:
  - \`run_pipeline.py\` の \`_can_stop_shared_proxysql()\` は、\`taskCount <= 1\` であっても、Cloud Run API を介して自実行以外の「実行中（RUNNING / 未完了）のクローラー・MLパイプライン実行」が存在するかを確認する。
  - 他にアクティブな実行が存在する場合は停止をスキップし、Safety-Net に委譲する。

## 4. 非機能要件 (NFR)
- **NFR-001 (パフォーマンスと耐障害性)**:
  - ProxySQL 通信断時、クローラーは 25 分間待たされることなく、最大 120 秒以内に \`OperationalError\` を検知して自律復旧・Fast-Fail 判定を行う。
- **NFR-002 (ゼロリグレッション)**:
  - 既存の SQLite テスト環境や単体テスト群に一切の影響を与えない。
