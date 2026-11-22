# 健美家（kenbiya）429 応答時のブラウザ Cookie ウォームアップ＆Playwright フォールバック仕様

## 概要
`KenbiyaParser` において、HTTP 429 (Too Many Requests) が返された場合でも、403 と同様に Playwright フォールバックを起動し、事前に `https://www.kenbiya.com/` へアクセスして Cookie を生成・保持した状態で対象 URL を取得できるようにする。

## 関連 Issue
- Issue #1718, #1719, #1721, #1722
