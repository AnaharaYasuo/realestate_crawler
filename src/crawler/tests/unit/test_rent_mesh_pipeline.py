import json
from unittest.mock import MagicMock
from package.rag_ingest.rent_mesh_extractor import RentMeshChunk
from package.rag_ingest.rent_mesh_pipeline import RentMeshPipeline


def test_pipeline_streaming_and_kenbiya_guard():
    mock_storage = MagicMock()
    mock_storage.upload_bytes.return_value = "gs://test-bucket/rag/test.jsonl"
    
    pipeline = RentMeshPipeline(storage_mgr=mock_storage)
    
    # 健美家URLのスキップ確認
    kenbiya_result = pipeline.process_page(
        url="https://www.kenbiya.com/price/tokyo/",
        html_content="<html><body>健美家</body></html>",
        prefecture="東京都"
    )
    assert kenbiya_result is None
    mock_storage.upload_bytes.assert_not_called()
    
    # 正常系の処理とGCSアップロード確認
    sample_html = """
    <html>
      <head><title>新宿駅 家賃相場</title></head>
      <body>
        <main>
          <h1>新宿駅 家賃相場</h1>
          <p>新宿駅周辺のワンルーム相場は9.5万円です。単身者の需要が非常に高いエリアです。</p>
        </main>
      </body>
    </html>
    """
    chunk = pipeline.process_page(
        url="https://www.homes.co.jp/chintai/tokyo/shinjuku-st/price/",
        html_content=sample_html,
        prefecture="東京都",
        city="新宿区",
        station="新宿",
        source_id="homes_market"
    )
    assert chunk is not None
    assert chunk.metadata["station"] == "新宿"
    
    # GCSへのチャンクアップロード呼び出し確認（key 引数の使用と上書き防止プレフィックス検証）
    uploaded_path = pipeline.upload_chunk_to_gcs(chunk)
    assert uploaded_path == "gs://test-bucket/rag/test.jsonl"
    assert mock_storage.upload_bytes.call_count == 1
    call_kwargs = mock_storage.upload_bytes.call_args.kwargs
    assert "key" in call_kwargs
    assert f"rag/curated/statistics/pref=東京都/{chunk.id}.jsonl" == call_kwargs["key"]
