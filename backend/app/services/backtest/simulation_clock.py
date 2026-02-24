"""
SimulationClock: バックテスト用シミュレーション時計.
Reference: 09_バックテストシミュレーション Section 3-2
"""

from datetime import datetime, timezone


class SimulationClock:
    """バックテスト用シミュレーション時計.

    時刻を単調増加で管理し、Look-ahead Bias を物理的に防止する。
    advance_to() は昇順のみ許可し、逆方向の時刻移動を拒否する。
    """

    def __init__(self, start: datetime, end: datetime) -> None:
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if start > end:
            raise ValueError(f"start ({start}) must be <= end ({end})")
        self._current = start
        self._start = start
        self._end = end

    def now(self) -> datetime:
        """現在のシミュレーション時刻を返す."""
        return self._current

    @property
    def start(self) -> datetime:
        return self._start

    @property
    def end(self) -> datetime:
        return self._end

    def advance_to(self, timestamp: datetime) -> None:
        """指定時刻まで進める. 逆方向・範囲外は拒否."""
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        if timestamp < self._current:
            raise ValueError(
                f"Cannot go back in time: {timestamp} < current {self._current}"
            )
        if timestamp > self._end:
            raise ValueError(
                f"Cannot advance past end: {timestamp} > end {self._end}"
            )
        self._current = timestamp

    def is_finished(self) -> bool:
        """シミュレーション終了判定."""
        return self._current >= self._end

    def reset(self) -> None:
        """時計をスタート時刻にリセット."""
        self._current = self._start
