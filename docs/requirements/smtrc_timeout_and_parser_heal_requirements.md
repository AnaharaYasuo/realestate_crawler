# smtrcクローラータイムアウト延長・所在階パースおよびバリデータ誤検知解消 要件定義書

## 1. 背景と課題
- **課題1: smtrcクローラーのタイムアウト頻発**
  - `src/crawler/package/api/smtrc.py` における一覧巡回クラス（`ParseSmtrcMansionStartAsync`, `ParseSmtrcKodateStartAsync`, `ParseSmtrcTochiStartAsync`, `ParseSmtrcInvestmentStartAsync`）の `_getTimeOutSecond()` が600秒（10分）となっており、他社標準（2400秒）と比較して極端に短く、物件多数時やネットワーク遅延時に `Exit Code 1` で異常終了していた。
- **課題2: SmtrcMansionParserの複合ヘッダー所在階未抽出**
  - 三井住友トラスト不動産の一部詳細ページで「所在階/階建」などの複合テーブルヘッダーが使われている場合、`specs.get("所在階")` だけでは階数文字列が取得できず未設定となっていた。
- **課題3: PropertyDataValidatorの所在階誤検知**
  - `PropertyDataValidator._check_mansion_specs` が `getattr(item, "shozaikai", None) or getattr(item, "kaisu", None)` のみを検査していた。
  - `SmtrcMansion` をはじめとする多数のモデル（`MitsuiMansion`, `Sumai1Mansion` 等）では、階数情報は `floorType_kai`（数値）および `kaisuStr`（文字列）に格納されており、属性 `shozaikai` や `kaisu` を持たないため、正常に階数が抽出されていても「所在階が未抽出 (ERR_MISSING_FLOOR)」として誤検知されていた。

## 2. 機能要件 (FR)
- **FR-SMTRC-001 (タイムアウト延長)**:
  - `ParseSmtrc*StartAsync`（Mansion, Kodate, Tochi, Investment）のタイムアウト時間を 600 秒から 2400 秒へ延長する。
- **FR-SMTRC-002 (所在階表記揺れ対応)**:
  - `SmtrcMansionParser` において、`所在階` だけでなく `所在階/階建`、`所在階／階建`、`階数` からも `kaisuStr` を抽出し、`floorType_kai` を算出可能にする。
- **FR-VAL-001 (バリデータ階数判定フォールバック)**:
  - `PropertyDataValidator._check_mansion_specs` において、`shozaikai`、`kaisu` に加え、`floorType_kai`、`kaisuStr` も有効な階数情報として認識し、誤検知を防止する。

## 3. 非機能要件 (NFR)
- **NFR-001**: 既存の単体テストおよび回帰テストに破壊的影響を与えないこと。
- **NFR-002**: 所在階が完全に空文字または未抽出である不正データは、従来通り `ERR_MISSING_FLOOR` として確実に検知すること。
