"""
Daily report tests.
Reference: Phase 4 Step 16
"""

from datetime import date, datetime, timezone

from app.services.notification.daily_report import DailyReportData, DailyReportGenerator


class TestReportPeriod:
    def test_japan_trading_day(self):
        start, end = DailyReportGenerator.get_report_period(date(2026, 2, 25))
        # JST 06:00 = UTC 21:00 prev day
        assert start == datetime(2026, 2, 24, 21, 0, tzinfo=timezone.utc)
        assert end == datetime(2026, 2, 25, 21, 0, tzinfo=timezone.utc)

    def test_period_is_24h(self):
        start, end = DailyReportGenerator.get_report_period(date(2026, 1, 1))
        diff = (end - start).total_seconds()
        assert diff == 86400


class TestReportGeneration:
    def test_basic_report(self):
        data = DailyReportData(
            report_date=date(2026, 2, 25),
            total_pnl=15000,
            trade_count=5,
            win_count=3,
            loss_count=2,
            guard_triggers=1,
            traders_summary=[],
        )
        html = DailyReportGenerator.generate_report(data)
        assert "15,000 JPY" in html
        assert "2026-02-25" in html
        assert "3W / 2L" in html
        assert "green" in html

    def test_empty_day(self):
        html = DailyReportGenerator.generate_empty_report(date(2026, 2, 25))
        assert "No trades" in html

    def test_negative_pnl_red(self):
        data = DailyReportData(
            report_date=date(2026, 2, 25),
            total_pnl=-5000,
            trade_count=2,
            win_count=0,
            loss_count=2,
            guard_triggers=0,
            traders_summary=[],
        )
        html = DailyReportGenerator.generate_report(data)
        assert "red" in html
