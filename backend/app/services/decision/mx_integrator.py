"""
MX: Integration judgment.

Reference: 04_判定パイプライン Section 7
"""

from __future__ import annotations

from app.services.decision.decision_types import JudgeOutput


class MXIntegrator:
    """
    MX: Integrates M1/M2/M3 outputs to make final trade decision.

    Reference: Section 7
    Modes: all, dir+setup (recommended), score
    """

    def __init__(
        self,
        mode: str = "dir+setup",
        weight_dir: float = 2.0,
        weight_setup: float = 1.0,
        weight_exec: float = 1.0,
        score_threshold: float = 3.0,
    ):
        self.mode = mode
        self.weight_dir = weight_dir
        self.weight_setup = weight_setup
        self.weight_exec = weight_exec
        self.score_threshold = score_threshold

    def should_execute_m3(self, m1_output: JudgeOutput, m2_output: JudgeOutput) -> bool:
        """Determine if M3 should be executed based on M1+M2 results."""
        if self.mode == "dir+setup":
            return (
                m1_output.result.get("tradeAllowed", False)
                and m2_output.result.get("setupValid", False)
            )
        elif self.mode == "all":
            return (
                m1_output.result.get("tradeAllowed", False)
                and m2_output.result.get("setupValid", False)
            )
        elif self.mode == "score":
            # In score mode, always execute M3 to get the score
            return m1_output.result.get("tradeAllowed", False)
        return False

    def should_trade(
        self,
        m1_output: JudgeOutput,
        m2_output: JudgeOutput,
        m3_output: JudgeOutput,
    ) -> tuple[bool, dict]:
        """
        Final trade decision based on integration mode.

        Returns:
            (should_trade, _debug)
        """
        if self.mode == "all":
            return self._mode_all(m1_output, m2_output, m3_output)
        elif self.mode == "dir+setup":
            return self._mode_dir_setup(m1_output, m2_output, m3_output)
        elif self.mode == "score":
            return self._mode_score(m1_output, m2_output, m3_output)
        return False, {"error": f"unknown mode: {self.mode}"}

    def _mode_all(self, m1: JudgeOutput, m2: JudgeOutput, m3: JudgeOutput) -> tuple[bool, dict]:
        """all mode: all three must pass. Reference: Section 7-2"""
        m1_pass = m1.result.get("tradeAllowed", False)
        m2_pass = m2.result.get("setupValid", False)
        m3_pass = m3.result.get("entry", "NO_TRADE") != "NO_TRADE"
        result = m1_pass and m2_pass and m3_pass
        return result, {"mode": "all", "m1_pass": m1_pass, "m2_pass": m2_pass, "m3_pass": m3_pass}

    def _mode_dir_setup(self, m1: JudgeOutput, m2: JudgeOutput, m3: JudgeOutput) -> tuple[bool, dict]:
        """dir+setup mode (recommended): M1+M2 gate, then M3 decides. Reference: Section 7-2"""
        m1_pass = m1.result.get("tradeAllowed", False)
        m2_pass = m2.result.get("setupValid", False)
        m3_pass = m3.result.get("entry", "NO_TRADE") != "NO_TRADE"
        result = m1_pass and m2_pass and m3_pass
        return result, {"mode": "dir+setup", "m1_pass": m1_pass, "m2_pass": m2_pass, "m3_pass": m3_pass}

    def _mode_score(self, m1: JudgeOutput, m2: JudgeOutput, m3: JudgeOutput) -> tuple[bool, dict]:
        """score mode: weighted score threshold. Reference: Section 7-2"""
        m1_pass = 1.0 if m1.result.get("tradeAllowed", False) else 0.0
        m2_pass = 1.0 if m2.result.get("setupValid", False) else 0.0
        m3_pass = 1.0 if m3.result.get("entry", "NO_TRADE") != "NO_TRADE" else 0.0

        score = (
            self.weight_dir * m1_pass * m1.confidence
            + self.weight_setup * m2_pass * m2.confidence
            + self.weight_exec * m3_pass * m3.confidence
        )
        result = score >= self.score_threshold
        return result, {
            "mode": "score", "score": score, "threshold": self.score_threshold,
            "m1_contrib": self.weight_dir * m1_pass * m1.confidence,
            "m2_contrib": self.weight_setup * m2_pass * m2.confidence,
            "m3_contrib": self.weight_exec * m3_pass * m3.confidence,
        }
