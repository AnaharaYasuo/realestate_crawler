from package.utils.job_metrics import (
    export_job_metrics,
    is_empty_result_marked,
    mark_empty_result,
    read_job_metrics,
    reset_metrics,
)

def test_job_metrics_empty_result(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reset_metrics()
    assert is_empty_result_marked() is False

    # Mark as empty result
    mark_empty_result()
    assert is_empty_result_marked() is True

    # Export job metrics
    export_path = export_job_metrics("tokyu", "invest_kodate", detail_cnt=0, skipped_cnt=0, run_date="20261017")
    assert export_path is not None
    assert export_path.exists()

    # Read job metrics
    res = read_job_metrics("tokyu", "invest_kodate", run_date="20261017")
    assert res is not None
    detail, skip, tot, is_empty = res
    assert detail == 0
    assert skip == 0
    assert tot == 0
    assert is_empty is True
