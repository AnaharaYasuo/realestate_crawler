# 外部設計書: 一覧から詳細ディスパッチのキューワーカー化（5000件）と住友1000件廃止・ページング対応 (#993)

## 1. アーキテクチャ変更点

```
[従来の同期フロー]
MiddlePage -> URL抽出 -> _callApi -> asyncio.gather(全詳細ページ) -> _handle_local_execution (120秒タイムアウトで死亡)

[改修後のキューワーカーフロー]
MiddlePage -> URL抽出 -> _dispatch_to_queue (Queue maxsize=5000) -> 即座に次ページへ
                                   ↓ (バックグラウンド)
                            Worker Pools (Semaphore/DETAIL_PARALLEL_LIMIT拘束)
                                   ↓
                            DetailPageパース & DB保存
```

## 2. API & インターフェース設計
1. **環境変数**:
   - `CRAWLER_DISPATCH_QUEUE_SIZE`: デフォルト `5000`
2. **住友URLパラメータ**:
   - `getAreaDestUrl` から `limit=1000&mode=2` を削除。デフォルト表示件数（20〜30件）でのページングに対応。
