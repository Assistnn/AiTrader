"""
SimulationClock tests.
Reference: 09_バックテストシミュレーション Section 3-2
"""

import pytest
from datetime import datetime, timezone

from app.services.backtest.simulation_clock import SimulationClock


class TestSimulationClock:
    def test_initial_now(self):
        """初期時刻は start と同じ."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 12, 31, tzinfo=timezone.utc)
        clock = SimulationClock(start, end)
        assert clock.now() == start

    def test_advance_to(self):
        """advance_to で時刻が進む."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 12, 31, tzinfo=timezone.utc)
        clock = SimulationClock(start, end)

        mid = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        clock.advance_to(mid)
        assert clock.now() == mid

    def test_advance_backwards_raises(self):
        """逆方向の advance_to は ValueError."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 12, 31, tzinfo=timezone.utc)
        clock = SimulationClock(start, end)

        clock.advance_to(datetime(2025, 6, 1, tzinfo=timezone.utc))
        with pytest.raises(ValueError, match="Cannot go back"):
            clock.advance_to(datetime(2025, 3, 1, tzinfo=timezone.utc))

    def test_advance_past_end_raises(self):
        """end を超える advance_to は ValueError."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 12, 31, tzinfo=timezone.utc)
        clock = SimulationClock(start, end)

        with pytest.raises(ValueError, match="Cannot advance past end"):
            clock.advance_to(datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_is_finished_at_end(self):
        """end に到達すると is_finished() = True."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 12, 31, tzinfo=timezone.utc)
        clock = SimulationClock(start, end)

        assert clock.is_finished() is False
        clock.advance_to(end)
        assert clock.is_finished() is True

    def test_start_gt_end_raises(self):
        """start > end で ValueError."""
        with pytest.raises(ValueError, match="must be <="):
            SimulationClock(
                datetime(2025, 12, 31, tzinfo=timezone.utc),
                datetime(2025, 1, 1, tzinfo=timezone.utc),
            )

    def test_naive_datetime_gets_utc(self):
        """timezone なし datetime は UTC が自動付与される."""
        clock = SimulationClock(
            datetime(2025, 1, 1),
            datetime(2025, 12, 31),
        )
        assert clock.now().tzinfo == timezone.utc
        assert clock.start.tzinfo == timezone.utc
        assert clock.end.tzinfo == timezone.utc

    def test_reset(self):
        """reset() で開始時刻に戻る."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 12, 31, tzinfo=timezone.utc)
        clock = SimulationClock(start, end)
        clock.advance_to(datetime(2025, 6, 1, tzinfo=timezone.utc))
        clock.reset()
        assert clock.now() == start
