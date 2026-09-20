# 健美家 (Kenbiya) サイト構造および通信仕様仕様書

## 1. 概要
健美家（Kenbiya）は、一棟アパート・一棟マンション・区分マンション・戸建て・土地等の収益・投資用不動産を中心とした大手ポータルサイトである。
本ドキュメントでは、健美家のURL体系、F5 BIG-IP WAFによるレートリミット挙動（HTTP 429）、およびクローラー・価格推定APIでの耐障害性向上仕様を定義する。

## 2. URL体系
- 物件詳細URL: `https://www.kenbiya.com/pp2/s/<prefecture>/<city>/.../re_<property_id>/`
- メール通知URL: `https://www.kenbiya.com/.../?utm_source=newmail&utm_medium=email&utm_campaign=newmail`
- 追跡用クエリパラメータ（`utm_*`, `mail_*` 等）は物件特定には無関係であり、パースおよび保存前に `UrlMatcher.normalize()` により除去・正規化を行う。

## 3. WAF & レートリミット (HTTP 429) の挙動と対策
### 3.1 挙動
- 健美家のフロントには F5 BIG-IP WAF が配置されており、短時間の連続アクセスや特定User-Agentに対して `HTTP 429 Too Many Requests` を返却する。
- 429発生時は一時的なIP制限状態となり、極めて短いスリープ（2〜4秒）では解除されない。

### 3.2 回避・ハンドリング仕様
1. **User-Agent ローテーション**:
   - 古いハードコードUA（Chrome 123等）を廃止し、最新のモダンブラウザUA（Chrome 130+, Safari 17+, Firefox 132+）をリクエスト毎にローテーション適用する。
2. **RateLimitedException の導入**:
   - HTTP 429 を単なるタイムアウト（504）や一般的パース失敗（422）と混同せず、`RateLimitedException` として明示的に捕捉・分類する。
3. **API レスポンスマッピング**:
   - `/api/evaluation/predict-by-url` において `RateLimitedException` を検知した場合、HTTP 429 `TARGET_SITE_RATE_LIMITED` を返却し、呼び出し元に適切な待機・再試行を促す。
