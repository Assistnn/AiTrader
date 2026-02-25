"""
BudgetTracker tests: daily token budget management.
Reference: 14_コスト管理 Section 2-2【監査4】
"""

from datetime import date, datetime, timezone

from app.services.ai.budget_tracker import (
    BudgetStatus,
    BudgetTracker,
    DailyUsageSummary,
    UsageRecord,
)


def _record(
    tokens_input: int = 500,
    tokens_output: int = 200,
    trader_id: int = 1,
    stage: str = "m1",
    target_date: date | None = None,
) -> UsageRecord:
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()
    return UsageRecord(
        trader_id=trader_id,
        stage=stage,
        provider="mock",
        model="mock-model",
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        estimated_cost_usd=0.01,
        timestamp=datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc),
    )


class TestUsageRecording:
    def test_record_and_get_daily(self):
        tracker = BudgetTracker(daily_token_limit=1_000_000)
        tracker.record_usage(_record(tokens_input=1000, tokens_output=500))
        usage = tracker.get_daily_usage()
        assert usage.total_tokens == 1500
        assert usage.total_calls == 1
        assert usage.total_tokens_input == 1000
        assert usage.total_tokens_output == 500

    def test_multiple_records_aggregate(self):
        tracker = BudgetTracker()
        tracker.record_usage(_record(tokens_input=100, tokens_output=50))
        tracker.record_usage(_record(tokens_input=200, tokens_output=100))
        usage = tracker.get_daily_usage()
        assert usage.total_tokens == 450
        assert usage.total_calls == 2

    def test_records_grouped_by_stage_and_provider(self):
        tracker = BudgetTracker()
        tracker.record_usage(_record(stage="m1"))
        tracker.record_usage(_record(stage="m2"))
        tracker.record_usage(_record(stage="m1"))
        usage = tracker.get_daily_usage()
        assert usage.by_stage["m1"] == 2
        assert usage.by_stage["m2"] == 1
        assert usage.by_provider["mock"] == 3


class TestBudgetCheck:
    def test_ok_under_threshold(self):
        tracker = BudgetTracker(daily_token_limit=1_000_000, warning_threshold_pct=80)
        # 50K tokens = 5% → OK
        tracker.record_usage(_record(tokens_input=25000, tokens_output=25000))
        assert tracker.check_budget() == BudgetStatus.OK

    def test_warning_at_80_percent(self):
        tracker = BudgetTracker(daily_token_limit=1000, warning_threshold_pct=80)
        # 800 tokens = 80% → WARNING
        tracker.record_usage(_record(tokens_input=400, tokens_output=400))
        assert tracker.check_budget() == BudgetStatus.WARNING

    def test_exceeded_at_100_percent(self):
        tracker = BudgetTracker(daily_token_limit=1000)
        # 1200 tokens > 1000 → EXCEEDED
        tracker.record_usage(_record(tokens_input=600, tokens_output=600))
        assert tracker.check_budget() == BudgetStatus.EXCEEDED


class TestRemainingTokens:
    def test_remaining_tokens(self):
        tracker = BudgetTracker(daily_token_limit=10000)
        tracker.record_usage(_record(tokens_input=3000, tokens_output=2000))
        assert tracker.get_remaining_tokens() == 5000

    def test_remaining_tokens_zero_when_exceeded(self):
        tracker = BudgetTracker(daily_token_limit=100)
        tracker.record_usage(_record(tokens_input=200, tokens_output=200))
        assert tracker.get_remaining_tokens() == 0

    def test_usage_percentage(self):
        tracker = BudgetTracker(daily_token_limit=10000)
        tracker.record_usage(_record(tokens_input=2500, tokens_output=2500))
        assert tracker.get_usage_pct() == 50.0


class TestDateIsolation:
    def test_different_date_not_counted(self):
        tracker = BudgetTracker(daily_token_limit=1000)
        yesterday = date(2024, 1, 1)
        today = date(2024, 1, 2)
        tracker.record_usage(_record(tokens_input=500, tokens_output=500, target_date=yesterday))
        # Today's usage should be 0
        usage = tracker.get_daily_usage(today)
        assert usage.total_tokens == 0
        assert tracker.check_budget(today) == BudgetStatus.OK
