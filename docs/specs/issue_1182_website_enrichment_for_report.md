# 仕様書: AI定性評価時の物件Webサイト本文・備考・リフォーム情報取得およびレポート反映

- **対象Issue**: #1182
- **対象ブランチ**: `feat/issue-1182-website-enrichment-for-report`
- **対象ファイル**:
  - `src/crawler/package/ml/report_generator.py`
  - `src/crawler/package/models/evaluation.py`
  - `src/crawler/scripts/ops/send_recommendations.py`
  - `src/crawler/tests/unit/test_danchou_rag.py`
  - `src/crawler/tests/unit/test_report_generator_web_enrichment.py`

---

## 1. 背景・目的 (Why & What)

### 背景とユーザー課題
Antigravity クローラーおよびMLパイプラインでは、割安判定された物件に対してプロ鑑定および元祖・狼旅団団長RAGによる高度な定性評価レポートを自動生成している。
しかし、これまでLLM（Gemini API）やフォールバックに与えられていたコンテキストはDBに格納された数値・カテゴリ情報（価格、駅距離、築年数、構造、面積、容積率、接道等）に限られていた。
物件詳細Webサイト（ポータルや仲介会社サイト）には、「2026年8月リノベーション済」「大規模修繕工事中」「満室稼働中・全部賃貸中」「建築条件なし・解体更地渡し」「プロパンガス/都市ガス」「告知事項あり/心理的瑕疵」といった、物件固有の極めて重要なセールスポイントや実態情報が文章で記載されている。

### 目的
推薦対象に選ばれた物件のAI定性評価実行時に、対象物件のWebページURLからテキスト情報（備考・セールスポイント・設備・リフォーム履歴等）を能動的にフェッチ・クレンジングし、LLMプロンプトおよびルールベースフォールバックに反映させる。
これにより、サイトに書かれている固有情報を読み込んだ上で、真に個別具体的で高付加価値なプロ鑑定＆団長目利きレポートを出力する。

---

## 2. 外部設計 (Architecture & Data Flow)

```
[send_recommendations.py]
          │
          │ 割安物件抽出 (matched_candidates)
          ▼
[report_generator.py: generate_professional_and_danchou_report]
          │
          │ 1. 物件URLからWeb本文抽出 (fetch_property_page_text)
          │    - タイムアウト5秒、UA偽装、エンコーディング自動判定 (chardet/shift_jis/utf-8)
          │    - BeautifulSoupでscript/style/nav/footer除外、クレンジング
          │    - 最大3,000文字の要約コンテキストを抽出
          │
          ├──▶ 2. Gemini API プロンプトに【Webサイト掲載の個別情報・備考】として注入
          │       - GeminiがWebサイトの実態（リノベ歴、大規模修繕、入居状況等）を読み込んで回答
          │
          └──▶ 3. API制限/エラー時のフォールバック関数
                  - Web本文からキーワード検出（「リノベ」「大規模修繕」「満室」「建築条件なし」「プロパン」等）
                  - キーワードに応じた動的コメント・DDチェック項目の最適化
          │
          ▼
[PropertyEvaluation DB永続化 & Slack配信]
  - site_details_text の要約を evaluation レコードにも必要に応じて保持
  - Slackに物件固有の事実が反映されたレポートが配信される
```

---

## 3. 内部設計 (Implementation Details)

### 3.1 Web本文取得ユーティリティ `fetch_property_page_text(url: str, timeout: int = 5) -> str`
- `urllib.request` を使用（依存性最小化、軽量）。
- `User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36`
- レスポンスのエンコーディング自動検出（`chardet` および `Content-Type` ヘッダ、fallback: `utf-8` / `shift_jis` / `cp932`）。
- HTMLタグ・不要要素（`script`, `style`, `noscript`, `header`, `footer`, `nav`, `svg`）を完全除去。
- 連続空白・改行を圧縮し、重要度の高い先頭〜中盤から最大3,000文字を抽出。
- 失敗時（HTTP 403, 404, タイムアウト, NWエラー等）は空文字列 `""` を返し、例外を握り潰してメイン処理（DB構造化データのみの既存動作）を一切止めない。

### 3.2 プロンプト拡充 `_build_rag_prompt`
プロンプト内に以下セクションを追加：
```text
【物件詳細サイト（Web）掲載の個別情報・備考・アピールポイント】
{site_text}
```
Gemini 指示文に以下を追加：
「・Webサイトに記載されているリフォーム・リノベーション履歴、修繕状況、現況入居・空室状況、建築条件、設備、特記事項等の個別具体的事実があれば、必ずAI総括サマリー、最有効使用、団長目利き、DDチェックリストの内容に明確に反映させよ。」

### 3.3 フォールバック処理のWebテキスト加味
Gemini APIがクォータ制限（402等）等でフォールバックした場合でも：
- マンション: 「リノベ」「大規模修繕」「ペット可」「空室/オーナーチェンジ」を検出し、最有効使用や目利きコメントに「直近リノベーション完了済みによる即入居/即賃貸可能」「大規模修繕工事進行中」等を反映。
- 戸建: 「新築」「リフォーム済」「再建築不可」「駐車3台」等のキーワードを検知してコメント分岐。
- 一棟: 「満室稼働」「全室賃貸中」「プロパンガス」等を検知してコメント分岐。
- 土地: 「建築条件なし」「更地渡し」「古家あり」「確定測量済」等を検知してコメント分岐。

---

## 4. テスト計画 (TDD & Quality Assurance)

1. **単体テスト (`test_report_generator_web_enrichment.py`)**:
   - `fetch_property_page_text`: 正常系HTMLからのテキスト抽出、異常系（HTTPError/Timeout）時の安全な空文字返却。
   - `_build_rag_prompt`: `site_text` が存在する場合にプロンプトに含まれること。
   - フォールバック生成: `site_text` に含まれるキーワード（例：「リノベーション工事完成」「満室稼働中」）が、フォールバックの最有効使用・サマリー・団長コメントに反映されること。
2. **結合テスト・回帰テスト**:
   - 既存の `test_danchou_rag.py` および `test_investment_recommendations.py` が100%合格すること。
   - アーキテクチャハーネス `test_architecture_harness.py` 全件合格。
   - SonarCloud、Ruff リンター適合。
