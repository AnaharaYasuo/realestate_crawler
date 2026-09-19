# -*- coding: utf-8 -*-
import time
import threading
import collections
from typing import Tuple, Dict, List


class SlidingWindowRateLimiter:
    """
    スライディングウィンドウ方式によるIP / APIキー単位のインメモリ流量制限
    """
    def __init__(self, limit_per_minute: int = 60, burst_per_second: int = 5):
        self.limit_per_minute = limit_per_minute
        self.burst_per_second = burst_per_second
        self._requests: Dict[str, List[float]] = collections.defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, identifier: str) -> Tuple[bool, int]:
        """
        リクエスト可否判定
        Returns:
            (allowed: bool, retry_after_seconds: int)
        """
        now = time.time()
        with self._lock:
            timestamps = self._requests[identifier]
            
            # 1分以前の古いタイムスタンプを除去
            cutoff_1m = now - 60.0
            timestamps = [t for t in timestamps if t > cutoff_1m]
            self._requests[identifier] = timestamps

            # 1. 1秒あたりのバーストチェック
            recent_1s = sum(1 for t in timestamps if now - t < 1.0)
            if recent_1s >= self.burst_per_second:
                return False, 1

            # 2. 1分あたりの上限チェック
            if len(timestamps) >= self.limit_per_minute:
                oldest = timestamps[0]
                retry_after = int(60.0 - (now - oldest)) + 1
                return False, max(retry_after, 1)

            timestamps.append(now)
            return True, 0


class LockoutManager:
    """
    悪質接続元（SSRF攻撃、レートリミット連続違反等）の一時的アクセス遮断（ロックアウト）
    """
    def __init__(self, lockout_seconds: int = 900, strike_threshold: int = 3):
        self.lockout_seconds = lockout_seconds
        self.strike_threshold = strike_threshold
        self._strikes: Dict[str, List[float]] = collections.defaultdict(list)  # { ip: [timestamp, ...] }
        self._banned: Dict[str, float] = {}  # { ip: unban_timestamp }
        self._lock = threading.Lock()

    def is_locked_out(self, ip: str) -> Tuple[bool, int]:
        """
        IPがロックアウト中か確認
        Returns:
            (is_locked: bool, remaining_seconds: int)
        """
        now = time.time()
        with self._lock:
            if ip in self._banned:
                unban_time = self._banned[ip]
                if now < unban_time:
                    remaining = int(unban_time - now) + 1
                    return True, remaining
                else:
                    # ロック解除
                    del self._banned[ip]
                    self._strikes.pop(ip, None)
            return False, 0

    def record_strike(self, ip: str, instant_ban: bool = False) -> Tuple[bool, int]:
        """
        違反ストライクを記録し、条件到達時にBAN
        Returns:
            (banned: bool, ban_duration_seconds: int)
        """
        now = time.time()
        with self._lock:
            if instant_ban:
                self._banned[ip] = now + self.lockout_seconds
                return True, self.lockout_seconds

            # 過去5分以内のストライクを集計
            strikes = [t for t in self._strikes[ip] if now - t < 300.0]
            strikes.append(now)
            self._strikes[ip] = strikes

            if len(strikes) >= self.strike_threshold:
                self._banned[ip] = now + self.lockout_seconds
                return True, self.lockout_seconds

            return False, 0
