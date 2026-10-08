# Issue #787: Auto-Heal 一括修復 内部設計書

## 1. 変更アーキテクチャ

### 1.1 NomuraKodate モデル拡張
- `NomuraKodate` モデルに `madori = models.TextField(blank=True, default="")` を追加
- Django Migration `0061_nomurakodate_madori.py` による `nomura_kodate` テーブルへの `madori` カラム追加
- `NomuraKodateParser._parsePropertyDetailPage` において、`item.madori = self._parseMadori(response)` を代入

### 1.2 Odakyu 投資カードの面積欠損スキップ
- `OdakyuInvestmentParser._parse_invest_list_card` において、`tatemonoMenseki` も `tochiMenseki` も存在しないカード物件は `SkipPropertyException` を送出
- 面積ゼロによる後続のバリデーション落ち・ノイズ登録を事前防止

### 1.3 PropertyDataValidator の適正化
- `_check_common_required(cls, item, ptype, reasons)` に変更
- `ptype` に `invest` / `apartment` が含まれる、または `_is_low_price_allowed` に合致する場合は交通欄未記載による `ERR_MISSING_TRAFFIC` 除外をスキップ
- `_is_low_price_allowed` のキーワードリストに `古家`, `空き家`, `空家`, `戸建` を追加し、過度な価格リジェクトを防止
