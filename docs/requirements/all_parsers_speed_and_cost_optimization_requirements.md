# 要求仕様書: 残り15サイトの一覧並列化および価格一致スキップ最適化 (Issue #854)

## 1. 概要
不動産クローラーにおける未対応の15パーサー（三井のリハウス、三井住友トラスト、住友林業、小田急、京急、京成、西武、相鉄、すまい1、リアリエ、長谷工、アドキャスト、イエタン、健美家、東邦ハウジング）を対象に、一覧ページでの価格抽出（`ListItem(url, price)`）による差分スキップおよび、階層展開（`parseRootPage`）を持つサイトにおける並列展開・ストリーミングを導入する。

## 2. 対象コンポーネント
- `mitsuiParser.py`
- `smtrcParser.py`
- `sumirinParser.py`
- `odakyuParser.py`
- `keikyuParser.py`
- `keiseiParser.py`
- `seibuParser.py`
- `sotetsuParser.py`
- `sumai1Parser.py`
- `rearieParser.py`
- `hasekoParser.py`
- `adcastParser.py`
- `ietanParser.py`
- `kenbiyaParser.py`
- `tohoParser.py`

## 3. 受入基準 (Acceptance Criteria)
1. 対象15パーサーすべてにおいて、一覧ページ抽出時に `ListItem(url, price)` を返し、DBに登録済みの同一URL・同一価格の物件について詳細フェッチをスキップすること。
2. `parseRootPage` を持つパーサーにおいて、階層展開が適切に並列化（`Semaphore` 制御）され、クロール全体の完了時間が大幅に短縮されること。
3. 既存の単体テスト、インテグレーションテスト、スモークテストがすべて通過すること。
