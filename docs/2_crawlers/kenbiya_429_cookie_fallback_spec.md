# 健美家（kenbiya）429 応答時のブラウザ Cookie ウォームアップ＆Playwright フォールバック仕様

## 概要
`KenbiyaParser` において、HTTP 429 (Too Many Requests) が返された場合でも、403 と同様に Playwright フォールバックを起動し、事前に `https://www.kenbiya.com/` へアクセスして Cookie を生成・保持した状態で対象 URL を取得できるようにする。

## 関連 Issue
- Issue #1718, #1719, #1721, #1722, #1779

## 503 抑止・プロセス間レート制限および 503 検知時 PPPoE 自動復旧仕様 (Issue #1779)
- **プロセス間グローバル・レートリミッター**:
  - 複数種別プロセスを並列起動した際も同一IPからのバースト送信を防ぐため、OS一時ディレクトリ上の共有状態ファイル（`kenbiya_rate_limit.json` + ファイルロック）で全プロセス合算の送信間隔・直近60秒のRPM上限（`KENBIYA_GLOBAL_MAX_RPM`、既定 `20` req/min）・定期ロングポーズ（`KENBIYA_LONG_PAUSE_EVERY=40` ごとに `KENBIYA_LONG_PAUSE_SEC=15` 秒 + ランダムジッター）を制御する。
- **セッション内プロファイル固定**:
  - `curl_cffi` の `impersonate` / `Accept-Language` / `DNT` をプロセス内で固定し、リクエスト毎の急激なフィンガープリント切替を回避する。
- **HTTP 503 検知時のインプレース PPPoE 自動復旧**:
  - HTTP 503 を受信した際、プロセスを終了させず代表1プロセスが `ifdown wan_pppoe` を実行して `KENBIYA_PPPOE_ROTATE_WAIT_SEC`（既定 `1200` 秒 = 20分）スリープし、その後 `ifup wan_pppoe; sleep 5; /etc/init.d/vpn-policy-routing reload` で再接続する。
  - 他プロセスも共有状態ファイルの `rotating_until` を見て完了までスリープ待機し、取得済みの詳細ページ一覧およびページング位置を維持したまま同一 URL から自動再開する。
