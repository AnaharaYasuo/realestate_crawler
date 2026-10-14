# 外部設計書: 健美家パーサーにおける用語解説欄による築年月・スペック上書き破壊の防止 (Issue #926)

## 1. 対象コンポーネント
- `src/crawler/package/parser/kenbiyaParser.py` (`KenbiyaParserBase`)

## 2. 仕様変更概要
健美家の物件詳細ページにおいて、`KenbiyaParserBase._get_specs(response: BeautifulSoup)` が返すスペック辞書 `specs` の抽出仕様を以下のように変更する。

### 2.1 スコープ限定と除外ルール
1. **優先走査スコープ**:
   - `response.select("div.property dl, div.property table")` が存在する場合は、正規スペックブロックである `div.property` 内のスペックを最優先で走査する。
2. **用語解説領域の完全除外**:
   - `div.box_outline`, `div#guide_outline`, クラス名に `box_outline` や `guide` を含む要素配下の `<dl>` および `<table>` を走査対象から完全に除外する。
3. **First-Come-First-Served 原則**:
   - スペック辞書への代入時、すでに有効な値が格納されているキー（例: `"築年月"`）に対しては、後続の同一キーによる上書きを行わない（`if key and cleaned_val and key not in specs:`）。

## 3. 外部インターフェースへの影響
- パース結果のモデル属性（`item.chikunengetsu`, `item.chikunengetsuStr` 等）に正しい値（例: `1991-07-01`, `"1991年7月（築35年）"`）が反映されるようになり、インターフェースの変更（引数・戻り値型）はない。
