"""
Daily report generation service.

Reference: 08_API仕様, 07_データベーススキーマ
Generates daily trading summary reports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone


@dataclass
class DailyReportData:
    """Daily report data."""
    report_date: date
    total_pnl: float
    trade_count: int
    win_count: int
    loss_count: int
    guard_triggers: int
    traders_summary: list[dict]


class DailyReportGenerator:
    """Generate daily trading reports."""

    @staticmethod
    def get_report_period(report_date: date) -> tuple[datetime, datetime]:
        """Get UTC start/end for a report date (Japan trading day).

        Japan trading day: 06:00 JST (21:00 UTC prev day) to 06:00 JST next day.
        """
        jst_start = datetime.combine(report_date, time(6, 0))
        utc_start = jst_start - timedelta(hours=9)  # JST → UTC
        utc_end = utc_start + timedelta(days=1)
        return (
            utc_start.replace(tzinfo=timezone.utc),
            utc_end.replace(tzinfo=timezone.utc),
        )

    @staticmethod
    def generate_report(data: DailyReportData) -> str:
        """Generate HTML report body."""
        win_rate = (data.win_count / data.trade_count * 100) if data.trade_count > 0 else 0
        pnl_color = "green" if data.total_pnl >= 0 else "red"

        return f"""
        <h2>Daily Trading Report - {data.report_date}</h2>
        <table style="border-collapse: collapse; width: 100%;">
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">Total P&L</td>
                <td style="padding: 8px; border: 1px solid #ddd; color: {pnl_color};">
                    {data.total_pnl:,.0f} JPY
                </td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">Trades</td>
                <td style="padding: 8px; border: 1px solid #ddd;">
                    {data.trade_count} ({data.win_count}W / {data.loss_count}L, {win_rate:.1f}%)
                </td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">Guard Triggers</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{data.guard_triggers}</td>
            </tr>
        </table>
        """

    @staticmethod
    def generate_empty_report(report_date: date) -> str:
        """Generate report for days with no trades."""
        return f"""
        <h2>Daily Trading Report - {report_date}</h2>
        <p>No trades executed on this day.</p>
        """
