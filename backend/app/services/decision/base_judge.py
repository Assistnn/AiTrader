"""
BaseJudge abstract base class.

Reference: 04_判定パイプライン Section 2-1
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.services.decision.decision_types import JudgeConfig, JudgeInput, JudgeOutput


class BaseJudge(ABC):
    """Base class for all pipeline judgment modules. Reference: Section 2-1"""

    @abstractmethod
    async def judge(self, input: JudgeInput, config: JudgeConfig) -> JudgeOutput:
        """Execute judgment and return result."""
        ...

    @abstractmethod
    def describe_config(self) -> dict:
        """Return config description for UI/documentation."""
        ...
