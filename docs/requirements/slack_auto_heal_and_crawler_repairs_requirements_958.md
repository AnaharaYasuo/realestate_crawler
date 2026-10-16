# 要件定義書: Slackエラー読取・低件数検知のオートヒール統合およびathome/homesクローラー修復

## 1. 概要・背景
不動産クローラー運用において、現在以下の2つの重大な課題が存在している：
1. **オートヒールスキルのスコープ不足**: 現行の `auto_heal_parsers.py` は DB（PropertyEvaluation）のデータ不整合レコードのみをスキャンしており、Slack に投稿された「0件取得警告」「パース例外」「極小件数異常」のログを自律修復対象として取り込めていない。
2. **大規模サイト（athome, homes）のクローリング欠損**:
   - **athome**: サイト構造変更等により、平均取得件数が 0.4件に低迷し、0件警告が頻発（166回以上）。
   - **homes**: 一覧取得セレクター不一致や価格パース時の正規表現例外（`AttributeError`）により、本来数万件ある大規模サイトにもかかわらず平均 2.8件しか取得できていない。

## 2. 目的
- Slack の過去エラー投稿（0件警告、パース例外、低件数異常）を `auto_heal_parsers.py` が自動読取して自己修復指示書（`Temp/auto_heal_instruction.json`）の Top-50 に統合できるようにする。
- `.agents/skills/auto-healing/SKILL.md` の規約を更新し、Slackエラー読取をオートヒールの標準フローとして明文化する。
- `athome` および `homes` のクローラー・パーサーを修復し、0件取得およびパース例外を解消して正常な件数取得を実現する。

## 3. 受入基準 (Acceptance Criteria)
* **AC-1**: `auto_heal_parsers.py` が Slack API（`conversations.history`）を利用して過去のエラーログ（0件警告、パース例外、低件数異常）を収集・抽出し、DBスキャン結果と合算して Top-50 の指示書（`Temp/auto_heal_instruction.json`）を生成できること。
* **AC-2**: `.agents/skills/auto-healing/SKILL.md` に Slack エラー読取および低件数異常の自己修復フローが明記・包含されていること。
* **AC-3**: `athome` の一覧URL抽出セレクターおよびパーサーが修復され、0件取得異常が解消されること。
* **AC-4**: `homes` の一覧取得セレクターおよび `priceStr` パース例外が修復され、安定して物件データが抽出できること。
* **AC-5**: 単体テスト・リグレッションテストが全件 Pass すること。
