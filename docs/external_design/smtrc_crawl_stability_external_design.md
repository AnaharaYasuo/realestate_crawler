# SMTRCクローリング安定化・全物件種別0件取得防止外部設計書 (Issue #827)

## 1. 概要
本設計書は、三井住友トラスト不動産（`smtrc`）における WAF 対策・0件取得防止および全物件種別（マンション・戸建・土地・投資用）の取得安定化に関する外部仕様・インターフェースを定義する。

## 2. システム構成・フロー
```
[Start API: /api/smtrc/<type>/start]
                 ↓
      一覧ページ GET (_getContent)
      ├─ 正常レスポンス (>=1000 bytes) ➔ BeautifulSoupパース
      └─ WAF 403 / 微小レスポンス (<1000 bytes)
                 ↓ (自動フォールバック)
         Playwright Stealth Browser 起動
         (Chromium, User-Agent, navigator.webdriver隠蔽)
                 ↓
         一覧HTML取得 (DOM Content Loaded + networkidle)
                 ↓
   parseRootPage (CompareDetailsリンク抽出)
                 ↓
[Detail API: /api/smtrc/<type>/detail]
                 ↓
      各物件詳細パース & DB保存 (SmtrcMansion / Kodate / Tochi / Investment)
```

## 3. 対象エンドポイント・種別
| 会社名 | 種別 (`--type`) | Start API エンドポイント | 詳細パーサークラス | エンティティモデル |
|---|---|---|---|---|
| `smtrc` | `mansion` | `/api/smtrc/mansion/start` | `SmtrcMansionParser` | `SmtrcMansion` |
| `smtrc` | `kodate` | `/api/smtrc/kodate/start` | `SmtrcKodateParser` | `SmtrcKodate` |
| `smtrc` | `tochi` | `/api/smtrc/tochi/start` | `SmtrcTochiParser` | `SmtrcTochi` |
| `smtrc` | `investment` | `/api/smtrc/investment/start` | `SmtrcInvestmentParser` | `SmtrcInvestment` |

## 4. エラーハンドリング仕様
- **WAF 403 Forbidden**: `ParserBase._getContent` で 403 が発生した場合、警告ログを出力し即座に `_smtrc_fetch_with_playwright` を実行。
- **微小レスポンス (<1000 bytes)**: 200 OK であっても HTML 本体が空、または JS チャレンジ画面の場合、Playwright ステルス取得へフォールバック。
- **フォールバック後の検証**: 取得したバイト数が 1000 bytes 以上であることを確認。不足時は 1 回リトライし、なお不足する場合は `RuntimeError` を送出。
