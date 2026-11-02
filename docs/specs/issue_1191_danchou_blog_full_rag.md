# Issue #1191: 元祖狼旅団ブログ全記事のGCSアーカイブ保存および全件ナレッジベース構築仕様書

## 1. 背景・目的
- 推薦通知対象の割安物件に対して付与される「団長コメント」および定性評価レポートが、固定のフォールバックテンプレートにより画一的になっていた。
- 本質的な分析を行うため、中身の伴わない固定フォールバックテンプレートを撤廃し、元祖狼旅団ブログ（`http://siokaraiookami.blog.fc2.com/`）の過去全記事（約140ヶ月分）をHTML丸ごとGoogle Cloud Storage（GCS）にワンショットでアーカイブ保存する。
- 保存したHTMLからタイトル・カテゴリ・投稿日・本文テキスト・重要キーワードを抽出し、網羅的なナレッジベース（`danchou_kb_full.jsonl`）を構築してRAG検索モジュールに配線する。

## 2. アーキテクチャ設計

### 2.1 ストレージ配置
- 生HTML保存先: `gs://realestate-images-sumifu-prod/danchou_raw_html/blog-entry-{id}.html`
- クレンジング済みナレッジベース: `gs://realestate-images-sumifu-prod/rag/danchou_kb_full.jsonl`
- ローカルキャッシュ: `data/rag/danchou_kb_full.jsonl`

### 2.2 ナレッジベーススキーマ (`danchou_kb_full.jsonl`)
各行 JSON:
```json
{
  "id": "entry_3008",
  "entry_id": 3008,
  "title": "カムバックサーモンの法則 - 真面目な不動産ネタ",
  "category": "真面目な不動産ネタ",
  "date": "2026/10/28",
  "url": "http://siokaraiookami.blog.fc2.com/blog-entry-3008.html",
  "target_types": ["一棟アパート", "戸建", "区分マンション"],
  "keywords": ["買い付け", "商談決裂", "売主", ...],
  "essence": "ブログ本文冒頭・重要段落の要約テキスト（約300〜500文字）",
  "body_text": "ノイズ除去後の本文全テキスト"
}
```

### 2.3 フォールバック処理の刷新 (`report_generator.py`)
- 中身の伴わない固定文章のフォールバック（例: どの区分も同じ「修繕積立金残高と専有部給排水管…」）を撤廃。
- Gemini APIが呼び出せない場合（課金未チャージ時等）は、空のダミー文章で埋めるのではなく、抽出されたマッチング団長ナレッジ（ブログ過去記事のタイトル・エッセンス）を直接提示し、虚偽や中身のない推測コメントを出力しない仕様とする。

## 3. 受入基準
1. `src/crawler/scripts/ops/archive_danchou_blog.py` により元祖ブログ全記事URLを取得し、HTMLをGCSへ一括保存できること。
2. 保存したHTMLから `danchou_kb_full.jsonl` を抽出し、GCSおよびローカルに配置できること。
3. `danchou_rag.py` が `danchou_kb_full.jsonl` を自動優先ロードし、物件特徴（キーワード・種別）に応じたエピソードを高精度に引き当てられること。
4. 単体テストおよびアーキテクチャハーネスがすべて合格すること。
