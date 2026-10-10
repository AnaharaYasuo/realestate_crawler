# 外部設計書: 残り15サイトの一覧並列化および価格一致スキップ最適化 (Issue #854)

## 1. 外部インターフェース仕様
- パーサーの `parsePage` メソッドは、詳細ページURLの文字列 `str` または `ListItem(url=..., price=...)` のイテレータ／ジェネレータを返却する。
- クローラーエンジン（`differential.py`）側は受け取った `ListItem` の `price` を用いて、既存DBレコードの最新価格と突合し、変更がない場合は詳細HTTPリクエストを完全スキップする。

## 2. サイト別改修観点
- **一覧のみパーサー** (`haseko`, `adcast`, `ietan`, `kenbiya`, `toho`):
  - `parsePage` で物件カードからリンクURLと価格（万円）をパースし、`ListItem(url, price)` をイールドする。
- **階層展開パーサー** (`mitsui`, `smtrc`, `sumirin`, `odakyu`, `keikyu`, `keisei`, `seibu`, `sotetsu`, `sumai1`, `rearie`):
  - `parsePage` での `ListItem` 返却。
  - `parseRootPage` 内の地域・条件リンク展開ループを `asyncio.Semaphore` を用いた並列フェッチ・ストリーミングに刷新。
