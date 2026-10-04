# -*- coding: utf-8 -*-
"""
バッチ処理標準メトリクス計測・整形ユーティリティ (Batch Metrics Utility)

世間一般のエンタープライズバッチ処理・ML/ETLパイプライン標準に基づく、
処理対象件数、処理時間、スループット、各内訳の計測・記録・Slack/ログ整形機能を提供します。
"""
import time
import datetime
import threading
from typing import Any


def format_batch_duration(seconds: float) -> str:
    """秒数を 'X時間Y分Z秒' または 'Z秒' に整形する。"""
    sec = max(0, int(seconds))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}時間{m}分{s}秒"
    if m > 0:
        return f"{m}分{s}秒"
    return f"{s}秒"


def format_throughput(count: int, seconds: float) -> tuple[float, float]:
    """
    スループット（件/秒）および平均レイテンシ（ms/件）を算出する。
    ゼロ除算ガード付き。
    """
    if seconds <= 0.0 or count <= 0:
        return 0.0, 0.0
    items_per_sec = count / seconds
    ms_per_item = (seconds * 1000.0) / count
    return round(items_per_sec, 1), round(ms_per_item, 1)


def format_timestamp_jst(ts: float | None) -> str:
    """UNIXタイムスタンプを 'YYYY-MM-DD HH:MM:SS' 形式（ローカル/JST）に整形する。"""
    if ts is None:
        return "-"
    try:
        dt = datetime.datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "-"


class BatchMetrics:
    """
    バッチジョブの実行メトリクス（件数・時間・スループット・内訳）を管理・整形するクラス。
    マルチスレッド実行時のスレッドセーフなカウント更新をサポート。
    """

    def __init__(self, job_name: str, total_count: int = 0):
        self.job_name = job_name
        self.start_time = time.time()
        self.end_time: float | None = None
        self.total_count = total_count
        self.processed_count = 0
        self.skipped_count = 0
        self.failed_count = 0
        self.custom_metrics: dict[str, Any] = {}
        self._lock = threading.Lock()

    def record_processed(self, n: int = 1) -> None:
        """処理完了件数を加算 (Thread-Safe)"""
        with self._lock:
            self.processed_count += n

    def record_skipped(self, n: int = 1) -> None:
        """スキップ件数を加算 (Thread-Safe)"""
        with self._lock:
            self.skipped_count += n

    def record_failed(self, n: int = 1) -> None:
        """エラー/失敗件数を加算 (Thread-Safe)"""
        with self._lock:
            self.failed_count += n

    def set_metric(self, key: str, value: Any) -> None:
        """カスタムメトリクスを保存"""
        with self._lock:
            self.custom_metrics[key] = value

    def get_metric(self, key: str, default: Any = None) -> Any:
        """カスタムメトリクスを取得"""
        with self._lock:
            return self.custom_metrics.get(key, default)

    @property
    def remaining_count(self) -> int:
        """未処理残件数"""
        done = self.processed_count + self.skipped_count + self.failed_count
        return max(0, self.total_count - done)

    def finish(self, fixed_end_time: float | None = None) -> float:
        """
        バッチ終了を記録し、総所要秒数を返す。
        テスト用に fixed_end_time の直接指定も可能。
        """
        self.end_time = fixed_end_time if fixed_end_time is not None else time.time()
        return self.elapsed_seconds

    @property
    def elapsed_seconds(self) -> float:
        """経過秒数または完了までの所要秒数"""
        end = self.end_time if self.end_time is not None else time.time()
        return max(0.0, end - self.start_time)

    @property
    def duration_str(self) -> str:
        """整形された所要時間文字列"""
        return format_batch_duration(self.elapsed_seconds)

    @property
    def throughput(self) -> float:
        """処理スループット (件/秒)"""
        tp, _ = format_throughput(self.processed_count, self.elapsed_seconds)
        return tp

    @property
    def latency_ms(self) -> float:
        """1件あたり平均処理時間 (ms/件)"""
        _, lat = format_throughput(self.processed_count, self.elapsed_seconds)
        return lat

    def build_slack_summary(
        self,
        title: str,
        custom_lines: list[str] | None = None,
        emoji: str = "✅",
    ) -> str:
        """
        Slack通知用の構造化サマリーメッセージを生成する。
        """
        st_str = format_timestamp_jst(self.start_time)
        et_str = format_timestamp_jst(self.end_time)
        dur = self.duration_str
        tp = self.throughput
        lat = self.latency_ms

        lines = [
            f"{emoji} *【{title}】*",
            f"• *実行時間*: {st_str} 〜 {et_str} (所要: {dur})",
            f"• *処理件数*: 対象総数 {self.total_count:,} 件 | 評価完了: {self.processed_count:,} 件 | スキップ: {self.skipped_count:,} 件",
        ]
        if tp > 0.0:
            lines.append(f"• *スループット*: {tp} 件/秒 (平均 {lat} ms/件)")
        if custom_lines:
            lines.extend(custom_lines)
        if self.failed_count > 0:
            lines.append(f"⚠️ *エラー/失敗*: {self.failed_count:,} 件")

        return "\n".join(lines)

    def build_recommendation_slack_summary(
        self,
        channel_counts: dict[str, int],
        matched_count: int,
        quota: int = 15,
        emoji: str = "✅",
    ) -> str:
        """
        割安物件配信完了時の構造化Slackサマリーメッセージを生成する。
        """
        st_str = format_timestamp_jst(self.start_time)
        et_str = format_timestamp_jst(self.end_time)
        dur = self.duration_str

        channel_labels = {
            "mansion": "マンション",
            "kodate": "戸建",
            "tochi": "土地",
            "invest_apartment": "投資アパート",
            "investmentapartment": "投資アパート",
            "invest_kodate": "投資戸建",
            "investmentkodate": "投資戸建",
        }

        channel_lines = []
        for ch_key, ch_name in channel_labels.items():
            cnt = channel_counts.get(ch_key, 0)
            if cnt > 0:
                channel_lines.append(f"  - {ch_name}: {cnt} 件")

        lines = [
            f"{emoji} 【お宝物件配信完了】 計 {self.processed_count}/{quota} 件のお宝物件カードを配信完了しました。",
            f"• *実行時間*: {st_str} 〜 {et_str} (所要: {dur})",
            f"• *処理件数*: 対象候補 {self.total_count:,} 件 | 基準合致 {matched_count:,} 件 | 配信完了 {self.processed_count:,} 件 (上限枠: {quota}件)",
        ]
        if channel_lines:
            lines.append("• *チャンネル別配信内訳*:")
            lines.extend(channel_lines)
        if self.failed_count > 0:
            lines.append(f"⚠️ *配信失敗*: {self.failed_count:,} 件")

        return "\n".join(lines)

    def build_log_banner(
        self,
        title: str | None = None,
        custom_sections: list[str] | None = None,
    ) -> str:
        """
        ログ・コンソール出力用の標準バッチバナーを生成する。
        """
        job_title = title or self.job_name
        st_str = format_timestamp_jst(self.start_time)
        et_str = format_timestamp_jst(self.end_time)
        dur = self.duration_str
        tp = self.throughput
        lat = self.latency_ms

        sep = "=" * 80
        lines = [
            sep,
            f"【バッチ実行サマリー: {job_title}】",
            f"• 実行時間      : {st_str} 〜 {et_str} (所要時間: {dur})",
            f"• 処理件数      : 対象総数 {self.total_count:,} 件 | 処理完了 {self.processed_count:,} 件 | スキップ {self.skipped_count:,} 件 | エラー {self.failed_count:,} 件",
        ]
        if tp > 0.0:
            lines.append(f"• スループット  : {tp} 件/秒 (平均レイテンシ: {lat} ms/件)")
        if custom_sections:
            for sec in custom_sections:
                lines.append(sec)
        lines.append(sep)

        return "\n".join(lines)
