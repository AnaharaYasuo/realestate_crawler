# 外部設計書: 継続実行時のパース・モデル不整合解消及びサーキットブレイカー誤爆防止 (Issue #898)

## 1. 概要
本設計書は、パイプラインの常時稼働性を阻害している「サーキットブレイカー誤判定」および「Djangoモデルバリデーション不整合」を解消するためのインターフェース・モデル仕様を定義する。

## 2. インターフェース・モデル仕様変更

### 2.1 Django モデル仕様改修 (`package/models/`)
* **`SumifuKodate`**:
  * `chiikiChiku = models.TextField(blank=True, default="")`
  * `boukaChiiki = models.TextField(blank=True, default="")`
  * `saikenchiku = models.TextField(blank=True, default="")`
  * `sonotaChiiki = models.TextField(blank=True, default="")`
* **`MitsuiMansion`**:
  * `kanrihi = models.IntegerField(null=True, blank=True)`
  * `syuzenTsumitate = models.IntegerField(null=True, blank=True)`
* **`MitsuiInvestmentApartment`**:
  * `soukosuStr = models.TextField(blank=True, default="")`
  * `soukosu = models.IntegerField(null=True, blank=True)`
  * `chikunengetsuStr = models.TextField(blank=True, default="")`

### 2.2 タイムアウト・サーキットブレイカー仕様
* ページ個別取得試行（同一URLに対する最大3回のリトライ）:
  * 3回試行すべてタイムアウトした場合は当該ページを `LoadPropertyPageException`（物件取得失敗）として記録し、他物件の取得を続行。
* サイト全体の連続タイムアウト（サーキットブレイカー）:
  * 異なるURL間で連続してタイムアウトが発生し、成功応答（HTTP 200）が一切挟まれない状態が `MAX_CONSECUTIVE_TIMEOUTS`（通常3回以上）続いた場合のみ `ServerDownException` を送出。
  * 1件でも成功レスポンスを受信すれば連続タイムアウトカウンタは直ちに 0 にリセットされる。
