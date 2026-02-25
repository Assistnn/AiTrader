"""
BudgetTracker: daily/monthly AI usage budget management.

Reference: 14_コスト管理 Section 2-2【監査4】
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum


class BudgetStatus(str, Enum):
    OK = "ok"
    WARNING = "warning"
    EXCEEDED = "exceeded"


@dataclass
class DailyUsageSummary:
    """Daily AI usage summary."""

    date: date
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    total_tokens: int = 0
    total_calls: int = 0
    estimated_cost_usd: float = 0.0
    by_stage: dict[str, int] = field(default_factory=dict)  # stage -> call count
    by_provider: dict[str, int] = field(default_factory=dict)  # provider -> call count


@dataclass
class UsageRecord:
    """Single AI usage record."""

    trader_id: int
    stage: str
    provider: str
    model: str
    tokens_input: int
    tokens_output: int
    estimated_cost_usd: float
    timestamp: datetime


class BudgetTracker:
    """Track AI usage against daily/monthly budgets.

    Reference: 14_コスト管理 Section 2-2

    - Daily token budget: 1,000,000 tokens (input + output)
    - Warning at 80% usage
    - Exceeded: all AI calls stopped
    """

    def __init__(
        self,
        daily_token_limit: int = 1_000_000,
        warning_threshold_pct: int = 80,
    ) -> None:
        self._daily_limit = daily_token_limit
        self._warning_pct = warning_threshold_pct
        self._records: list[UsageRecord] = []

    def record_usage(self, record: UsageRecord) -> None:
        """Record a single AI usage."""
        self._records.append(record)

    def get_daily_usage(self, target_date: date | None = None) -> DailyUsageSummary:
        """Get aggregated usage for a specific date."""
        if target_date is None:
            target_date = datetime.now(timezone.utc).date()

        summary = DailyUsageSummary(date=target_date)

        for r in self._records:
            if r.timestamp.date() != target_date:
                continue
            summary.total_tokens_input += r.tokens_input
            summary.total_tokens_output += r.tokens_output
            summary.total_tokens += r.tokens_input + r.tokens_output
            summary.total_calls += 1
            summary.estimated_cost_usd += r.estimated_cost_usd

            summary.by_stage[r.stage] = summary.by_stage.get(r.stage, 0) + 1
            summary.by_provider[r.provider] = summary.by_provider.get(r.provider, 0) + 1

        return summary

    def check_budget(self, target_date: date | None = None) -> BudgetStatus:
        """Check current budget status.

        Returns:
            BudgetStatus.OK: Under 80% of daily limit
            BudgetStatus.WARNING: Between 80% and 100% of daily limit
            BudgetStatus.EXCEEDED: Over 100% of daily limit
        """
        usage = self.get_daily_usage(target_date)
        ratio = usage.total_tokens / self._daily_limit if self._daily_limit > 0 else 0

        if ratio >= 1.0:
            return BudgetStatus.EXCEEDED
        if ratio >= self._warning_pct / 100.0:
            return BudgetStatus.WARNING
        return BudgetStatus.OK

    def get_remaining_tokens(self, target_date: date | None = None) -> int:
        """Get remaining token budget for today."""
        usage = self.get_daily_usage(target_date)
        return max(0, self._daily_limit - usage.total_tokens)

    def get_usage_pct(self, target_date: date | None = None) -> float:
        """Get current usage as percentage of daily limit."""
        usage = self.get_daily_usage(target_date)
        if self._daily_limit <= 0:
            return 0.0
        return (usage.total_tokens / self._daily_limit) * 100
