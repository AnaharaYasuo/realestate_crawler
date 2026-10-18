# 内部設計書: 一覧から詳細ディスパッチのキューワーカー化（5000件）と住友1000件廃止・ページング対応 (#993)

## 1. `src/crawler/package/api/api.py` の改修
1. **`ParseMiddlePageAsyncBase`**:
   - `_detail_queue: asyncio.Queue` を保持（`maxsize=int(os.getenv("CRAWLER_DISPATCH_QUEUE_SIZE", "5000"))`）。
   - 一覧ページから詳細URLが取得された場合、キューに投入（`await _detail_queue.put(item)`）。
   - キューから取り出して処理するワーカーコルーチン群（`worker_count = self._getPararellLimit()`）を起動。
   - `_flush_middle_page_chunk` はキューへの投入のみを行い、詳細パースの完了を待機しない。
   - 全一覧ページの巡回完了後、センチネル（`None`）を投入し、`await _detail_queue.join()` でキュー内の全詳細パース完了を待機して正常終了する。

## 2. `src/crawler/package/parser/sumifuParser.py` の改修
1. **`getAreaDestUrl`**:
   - `limit=1000&mode=2` 付与コードを削除。
   - `urllib.parse.urljoin(self.BASE_URL, link_url)` のみ返却。
2. **`getPropertyListNextPageUrl`**:
   - 既存のセレクター `next_page`（`a.pagination-button--next`）および「次へ」テキストマッチで次ページURLを確実に生成。
