from unittest.mock import MagicMock, patch
import pytest

from package.utils.newrelic_helper import (
    collect_hardware_resource_metrics,
    record_container_sample,
    record_crawler_metrics,
)


def test_collect_hardware_resource_metrics_network_rates():
    """ネットワーク送受信レート (KB/sec) が正しく計算されること"""
    # 1回目のサンプリング
    with patch("package.utils.newrelic_helper._read_network_metrics") as mock_net:
        mock_net.return_value = {
            "netBytesRecv": 1000000,
            "netBytesSent": 200000,
            "netPacketsRecv": 1000,
            "netPacketsSent": 500,
            "tcpEstablishedCount": 5,
            "tcpSynSentCount": 0,
            "tcpCloseWaitCount": 0,
            "tcpTimeWaitCount": 0,
            "tcpTotalCount": 5,
            "remoteEndpoints": [],
        }
        with patch("time.monotonic", return_value=100.0):
            m1 = collect_hardware_resource_metrics()
            assert "netRecvRateKbps" in m1
            assert "netSentRateKbps" in m1
            assert m1["netRecvRateKbps"] == 0.0
            assert m1["netSentRateKbps"] == 0.0

        # 2回目のサンプリング (10秒後、受信100KB増、送信20KB増)
        mock_net.return_value = {
            "netBytesRecv": 1000000 + 102400,
            "netBytesSent": 200000 + 20480,
            "netPacketsRecv": 1100,
            "netPacketsSent": 550,
            "tcpEstablishedCount": 6,
            "tcpSynSentCount": 0,
            "tcpCloseWaitCount": 0,
            "tcpTimeWaitCount": 0,
            "tcpTotalCount": 6,
            "remoteEndpoints": [],
        }
        with patch("time.monotonic", return_value=110.0):
            m2 = collect_hardware_resource_metrics()
            # 102400 bytes / 10 sec = 10240 B/s = 10.0 KB/s
            assert m2["netRecvRateKbps"] == 10.0
            # 20480 bytes / 10 sec = 2048 B/s = 2.0 KB/s
            assert m2["netSentRateKbps"] == 2.0


def test_record_container_sample_concurrency_attributes():
    """ContainerSample に並列度属性 (parallel, playwright_parallel, detail_concurrency, active_jobs_count) が含まれること"""
    mock_agent = MagicMock()
    mock_module = MagicMock()
    mock_module.agent = mock_agent

    with patch.dict(
        "os.environ",
        {
            "NEW_RELIC_LICENSE_KEY": "test-key",
            "CRAWLER_PARALLEL": "7",
            "CRAWLER_PLAYWRIGHT_PARALLEL": "3",
            "DETAIL_CONCURRENCY": "12",
        },
    ):
        with patch.dict("sys.modules", {"newrelic": mock_module, "newrelic.agent": mock_agent}):
            record_container_sample()
            assert mock_agent.record_custom_event.called
            call_args = mock_agent.record_custom_event.call_args
            event_type = call_args[0][0]
            params = call_args[0][1]

            assert event_type == "ContainerSample"
            assert params["parallel"] == 7
            assert params["playwright_parallel"] == 3
            assert params["detail_concurrency"] == 12
            assert "active_jobs_count" in params
            assert "netRecvRateKbps" in params
            assert "netSentRateKbps" in params


def test_record_crawler_metrics_concurrency_attributes():
    """CrawlerExecution に並列度属性 (parallel, playwright_parallel, detail_concurrency) が含まれること"""
    mock_agent = MagicMock()
    mock_module = MagicMock()
    mock_module.agent = mock_agent

    with patch.dict(
        "os.environ",
        {
            "NEW_RELIC_LICENSE_KEY": "test-key",
            "CRAWLER_PARALLEL": "5",
            "CRAWLER_PLAYWRIGHT_PARALLEL": "2",
            "DETAIL_CONCURRENCY": "8",
        },
    ):
        with patch.dict("sys.modules", {"newrelic": mock_module, "newrelic.agent": mock_agent}):
            record_crawler_metrics(
                site_name="tokyu",
                property_type="mansion",
                count=100,
                duration_sec=50.0,
                status="success",
            )
            assert mock_agent.record_custom_event.called
            call_args = mock_agent.record_custom_event.call_args
            event_type = call_args[0][0]
            params = call_args[0][1]

            assert event_type == "CrawlerExecution"
            assert params["parallel"] == 5
            assert params["playwright_parallel"] == 2
            assert params["detail_concurrency"] == 8
            assert "active_jobs_count" in params
            assert params["items_per_sec"] == 2.0
