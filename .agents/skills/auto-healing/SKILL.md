---
name: auto-healing
description: 直近のクローリング監視やDBデータ整合性テストで検出されたパースエラー・異常値を、AIが自律的に調査・修正・テスト・PR作成・マージまで全自動で復旧・修復（Self-Healing）するためのスキルです。
---

# 自律型AIパーサー自己修復 (Self-Healing) スキル

このスキルは、データ整合性チェックによって生成された自己修復指示書（`/app/Temp/auto_heal_instruction.json`）を検知した際にトリガーされ、人手を介さずに全自動でバグ修正・テスト・マージまでを行うための実行ガイドラインです。

## 起動条件
* `c:\Users\weare\Documents\realestate_crawler\Temp\auto_heal_instruction.json` ファイルが存在する場合、本スキルに従って最優先で自己修復タスクを開始してください。

---

## 実行ステップ

### 1. 指示書の読み込みと修復計画の立案
* `/app/Temp/auto_heal_instruction.json` を開き、修復対象の物件URL、物件種別、エラー・異常検出の理由（例: 価格極小、間口0m等）を確認します。
* 対象物件のポータルサイトに対応するパーサークラス（`src/crawler/package/parser/` 内）を特定します。

### 2. 原因の自動特定（実機調査）
* `browser_subagent` を起動して、指示書に記載された物件の URL に直接アクセスします。
* 物件詳細ページの HTML 構造（特にスペックテーブルの表記やラベル、価格・面積の表記方法）を分析します。
* **【分析の観点】**:
  * 億円切り捨てが発生していないか？ (「億」のパース抜け)
  * 前面道路幅員や間口が、なぜ `0` または未取得になっているか？ (接道テキストの表現揺らぎ、正規表現の漏れ)
  * テーブルのキー名が変更されていないか？ (「物件種目」➡「種別」など)

### 3. パーサーコードの修正
* 特定した原因に基づき、 `src/crawler/package/parser/[company]Parser.py` を Micro-Diff 方針（最小限の変更ブロック）に従って修正します。
* 共通の親メソッドやユーティリティ (`converter.py` 等) にバグがある場合は、 blast radius（影響範囲）を確認した上で修正を適用します。

### 4. ローカルテストによる検証
* 修正したパーサーの動作を確認するため、模擬 HTML または対象 URL を直接パースするテストスクリプトを作成・実行します。
* **テスト実行コマンド**:
  * `docker-compose exec -T app python Temp/test_parser_fixes.py` （または新規テスト）
* パース結果が実際の画面の数値と100%一致し、エラーが解消されたことを実証します。

### 5. Git コミット・PR作成・自動マージの実行
* テストが成功したら、以下の Git 操作をホストの git 実行ファイル（`C:\Program Files\Git\cmd\git.exe`）および GitHub CLI（`C:\Program Files (x86)\GitHub CLI\gh.exe`）を用いて行います。
* エイリアスのいたずらを防ぐため、必ず**フルパス**でコマンドを起動してください。

```bash
# 1. 退避中の変更があればstashし、ブランチを作成
& "C:\Program Files\Git\cmd\git.exe" checkout -b fix/auto-heal-[company]-[date]

# 2. 修正したパーサーをコミット
& "C:\Program Files\Git\cmd\git.exe" add src/crawler/package/parser/
& "C:\Program Files\Git\cmd\git.exe" commit -m "fix(auto-heal): resolve parsing anomaly for [company] [url]"
& "C:\Program Files\Git\cmd\git.exe" push origin fix/auto-heal-[company]-[date]

# 3. Pull Requestの作成
& "C:\Program Files (x86)\GitHub CLI\gh.exe" pr create --title "fix(auto-heal): [company] parser bugfix" --body "Automatically healed parsing anomaly detected at [url]" --base master --head fix/auto-heal-[company]-[date]

# 4. PRの自動マージと後片付け
& "C:\Program Files (x86)\GitHub CLI\gh.exe" pr merge --merge --delete-branch
& "C:\Program Files\Git\cmd\git.exe" checkout master
& "C:\Program Files\Git\cmd\git.exe" pull origin master
```

### 6. 指示書の削除 (クローズ)
* 自己修復が完了したら、 `/app/Temp/auto_heal_instruction.json` ファイルを削除し、 Slack の `property_alart` チャンネルに対して「自動調査・修正・マージまでが正常に完了した旨」を報告してタスクを終了します。
