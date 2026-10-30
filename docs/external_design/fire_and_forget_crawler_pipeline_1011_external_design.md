# 外部設計書: 全サイト巡回パイプラインの非同期投げっぱなし（Fire-and-Forget）化

## 1. システム構成・フロー設計

### 1.1 変更前（同期待機モデル）
```
StartPage (main)
   │
   ├─► RegionPage (Thread/Local) ───[親が最大120sブロック待機]
   │      │
   │      ├─► AreaPage (Thread/Local) ───[親が最大120sブロック待機]
   │      │      │
   │      │      ├─► ListPage ───[親が最大120sブロック待機]
   │      │      │      │
   │      │      │      └─► DetailPage (120sタイムアウト ➔ 504 LocalTimeout ➔ 中断)
```

### 1.2 変更後（Fire-and-Forget モデル）
```
StartPage (main)
   │
   ├─► Dispatch RegionPage ──► [Thread起動直後に 200 FireAndForgetLocal を返却]
   │                          親は即座に次の地域または処理へ前進
   ▼
RegionPage (Thread A)
   │
   ├─► Dispatch AreaPage ────► [Thread起動直後に 200 FireAndForgetLocal を返却]
   │                          親は即座に次のエリアへ前進
   ▼
AreaPage (Thread B)
   │
   ├─► Dispatch ListPage ────► [Thread起動直後に 200 FireAndForgetLocal を返却]
   │                          親は即座に次のリストへ前進
   ▼
ListPage (Thread C)
   │
   ├─► Dispatch DetailPage ──► [Thread起動直後/キュー投入直後に返却]
   │                          親は直ちに次ページネーション (page 2, 3...) へ前進
   ▼
DetailPage (Thread D)
   │
   └─► HTMLパース ➔ DB保存 ➔ コネクションクローズ ➔ 完了
```

## 2. インターフェース設計・環境変数

### 2.1 環境変数
- `CRAWLER_FIRE_AND_FORGET`:
  - 型: `boolean` (`true` / `false`, `1` / `0`)
  - デフォルト: `true`
  - 説明: `true` の場合、`_handle_local_execution` はスレッドの起動を確認した時点で `(detail_url, 200, "FireAndForgetLocal")` を返し、同期待機を行わない。
- `LOCAL_EXECUTION_TIMEOUT_SEC`:
  - 型: `float`
  - デフォルト: `120.0`
  - 説明: 同期モード（`CRAWLER_FIRE_AND_FORGET=false`）時の最大待機時間（秒）。

### 2.2 戻り値ステータス
- `200 "FireAndForgetLocal"`: ローカルスレッドが正常にディスパッチされバックグラウンド実行開始。
- `200 "FireAndForget"`: HTTPリクエストが送信完了しバックグラウンド受領。
- `200 "LocalSync"`: 同期モードで完了まで待機した場合のステータス。
- `504 "LocalTimeout"`: 同期モードでタイムアウトした場合のステータス。
- `500 "LocalDispatchError"`: スレッド生成・起動自体の失敗時。

## 3. サイト別影響評価
- **住友不動産 (sumifu)**: Start ➔ Region ➔ Area ➔ List ➔ Detail 全段で親が即座に前進可能となり、120秒タイムアウトによる中断が解消され、全件（数千〜1万件以上）の探索が完走する。
- **野村・三井・東急等**: 同様にリストおよび詳細ページのディスパッチで親がブロックされず高速巡回が実現。
