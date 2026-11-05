# RAG ナレッジ収集・分類仕様 (rag_knowledge_ingestion_spec)

## 1. 目的
RAG（`danchou_rag.py`）の知識ベースを、公的データ・業界資料・実務家の知見・自社データから拡充し、出典・ライセンス・鮮度を保ったまま GCS に分類保存する。

## 2. ストレージ構成（GCS: `GCS_BUCKET_NAME` 配下）
```
rag/
  raw/<source_id>/<yyyymmdd>/...      # 取得原本（ライセンスが許す場合のみ）
  curated/<category>/<source_id>.jsonl # 正規化済みチャンク（RAG 検索対象）
  manifest/sources.jsonl              # 出典台帳（ライセンス・利用可否・最終取得日）
  quarantine/                         # 規約未確認・要レビュー（検索対象外）
```
`category`: `law` / `guideline` / `tax` / `statistics` / `hazard` / `case_law` / `market_report` / `practitioner_insight` / `own_decision_log` / `own_model_feedback`

## 3. チャンクスキーマ（既存 `danchou_kb_full.jsonl` 互換 + 拡張）
既存: `id, title, url, target_types, essence, body_text`
拡張（必須）: `source_id, category, license, fetched_at, valid_from, valid_to, region, kind(fact|judgement), speaker_role, confidence, summary_only(bool)`

## 4. 収集ルール（遵守事項）
1. 出典URL・取得日・ライセンスを全件に付与。未記載は `quarantine/`。
2. 構造単位でチャンク化（法令=条・項、通達=項目）。固定文字数分割は禁止。
3. 事実と判断を分離（`kind`）。対立する見解は併記。
4. 著作権物は原文保存せず、自作要約＋出典のみ（`summary_only=true`）。
5. Q&A・口コミ・SNS・有料コンテンツは、規約確認が済むまで収集しない（クローラー取得禁止）。
6. 市況系は `valid_to` を持たせ、検索時に鮮度で重み付け。
7. robots.txt・利用規約・API 制限を尊重（レート制限、識別可能な User-Agent）。
8. 差分更新（ハッシュ比較）。改正・廃止は `valid_to` で失効させる。

## 5. 収集波（優先順）
| 波 | 対象 |
|---|---|
| 1 | e-Gov 法令API、国交省ガイドライン、国税庁通達、不動産情報ライブラリ、国土数値情報 |
| 2 | 不動産鑑定評価基準、審議会資料、RETIO 判例解説、フラット35 資料、J-SHIS |
| 3 | 自社: 判断ログ、推定誤差要因、採否フィードバック |
| 4 | 取材書き起こし（本人許諾つき）、業界団体の公開実務資料 |

## 6. 検証
- スキーマ検証テスト（必須フィールド、ライセンス空欄は quarantine へ）
- チャンク化の単体テスト（法令の条単位分割）
- 差分更新・失効の単体テスト
