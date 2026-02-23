"""
Decision pipeline shared types.

Reference: 04_判定パイプライン Section 2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.services.pipeline.data_types import StateSnapshot
from app.services.safeguard.guard_types import AccountState, GuardState, ProposedOrder


@dataclass
class JudgeInput:
    """Judge input (content varies per stage). Reference: Section 2-1"""

    pair: str
    timestamp: datetime  # evaluation time (UTC)
    state: StateSnapshot
    guard_state: GuardState
    previous_stages: dict[str, Any] = field(default_factory=dict)  # e.g. {"m1": M1Output}
    positions: list[Any] = field(default_factory=list)  # current open positions
    account: AccountState | None = None
    trader_id: int | None = None
    user_id: int | None = None


@dataclass
class JudgeConfig:
    """Judge config (items vary per stage). Reference: Section 2-1"""

    enabled: bool = True
    mode: str = "rule"  # "rule" / "aiAssist" / "aiFull"
    timeframes: list[str] = field(default_factory=lambda: ["H1"])
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class JudgeOutput:
    """Judge output (content varies per stage). Reference: Section 2-1"""

    result: dict[str, Any]
    confidence: float  # 0.0~1.0
    reason_codes: list[str] = field(default_factory=list)
    _debug: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Overall pipeline execution result. Reference: Section 8"""

    action: str  # "ENTRY" / "NO_TRADE" / "HALTED" / "BLOCKED"
    execution_id: str = ""
    order: ProposedOrder | None = None
    m1_output: JudgeOutput | None = None
    m2_output: JudgeOutput | None = None
    m3_output: JudgeOutput | None = None
    m4_output: JudgeOutput | None = None
    guard_state: GuardState | None = None
    _debug: dict[str, Any] = field(default_factory=dict)
