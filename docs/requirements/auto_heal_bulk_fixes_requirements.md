# Issue #787: Auto-Heal 一括修復仕様書（野村戸建間取り・小田急投資面積・バリデータ適正化）

## 1. 概要 / ユーザーストーリー
* **ユーザーとして**、不動産クローラー運用管理者として
* **Auto-Heal指示書（優先50件）およびデータ整合性検証で検出された主要エラー群を一括修復** したい
* **なぜなら**、間取り未保存によるバリデーション落ち、面積欠損カード物件による異常値リジェクト、元サイト交通未記載による除外を解消し、データ収集の完全性と健全性を確保するため

## 2. アクセプタンスクライテリア (受入基準)
* [x] `NomuraKodate` モデルに `madori` カラムが追加され、パーサーから抽出された間取りが正常に保存されること
* [x] `OdakyuInvestmentParser._parse_invest_list_card` において、建物面積・土地面積が一切取得できないカード物件は `SkipPropertyException` で適切に破棄されること
* [x] `PropertyDataValidator` において、投資物件等で交通欄が空欄の場合にリジェクトされず正常物件として許容されること
* [x] `PropertyDataValidator` において、「古家」「空き家」等のキーワードを持つ低価格物件（100万円未満）が正常データとして許容されること
* [x] 関連単体テスト（`test_nomura_parser.py`, `test_odakyu_investment_detail_url.py`, `test_strict_required_fields_741.py`, `test_validate_data.py`）が全件合格すること
