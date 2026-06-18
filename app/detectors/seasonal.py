"""
Seasonal detector.

Compares the current value not to a flat historical baseline, but to what
the metric looked like at the same time of day/week in previous cycles
(GitLab's "seasonality" approach: same weekday + a window around the same
time, offset by 1/2/3 weeks, then take the median of those as the
prediction). This handles metrics with strong daily/weekly patterns (request
rate, active users) where a flat z-score would constantly false-positive
during normal peaks and valleys.

This detector expects `history` to already be the set of values observed
around the same time-of-period in previous cycles (the caller/orchestrator
is responsible for fetching those offset windows from Prometheus — this
class only does the statistics). A `seasonal_margin_pct` provides a minimum
band width so very stable seasonal metrics don't get flagged on tiny noise.
"""
from __future__ import annotations

import statistics

from .base import AnomalyResult, BaseDetector


class SeasonalDetector(BaseDetector):
    name = "seasonal"

    def __init__(
        self,
        threshold: float = 2.0,
        min_samples: int = 3,
        seasonal_margin_pct: float = 0.1,
        **kwargs,
    ):
        super().__init__(
            threshold=threshold,
            min_samples=min_samples,
            seasonal_margin_pct=seasonal_margin_pct,
            **kwargs,
        )
        self.threshold = threshold
        self.min_samples = min_samples
        self.seasonal_margin_pct = seasonal_margin_pct

    def evaluate(self, history: list[float], current: float) -> AnomalyResult:
        """
        `history` here = values from the same time-of-day/week in previous
        cycles (e.g. [value_1w_ago, value_2w_ago, value_3w_ago]).
        """
        if len(history) < self.min_samples:
            return AnomalyResult(
                is_anomaly=False,
                score=0.0,
                actual=current,
                detector=self.name,
                reason=f"insufficient seasonal history ({len(history)} < {self.min_samples})",
            )

        # Median of prior cycles is the prediction — robust to a single
        # skewed week (e.g. a holiday), per GitLab's approach.
        predicted = statistics.median(history)

        try:
            spread = statistics.stdev(history)
        except statistics.StatisticsError:
            spread = 0.0

        # Enforce a minimum margin so near-zero variance doesn't make the
        # band unrealistically tight.
        margin = max(spread, abs(predicted) * self.seasonal_margin_pct)

        if margin == 0:
            score = 0.0 if current == predicted else (1e6 if current > predicted else -1e6)
        else:
            score = (current - predicted) / margin

        is_anomaly = abs(score) > self.threshold
        lower = predicted - self.threshold * margin
        upper = predicted + self.threshold * margin

        return AnomalyResult(
            is_anomaly=is_anomaly,
            score=score,
            actual=current,
            expected=predicted,
            lower_bound=lower,
            upper_bound=upper,
            detector=self.name,
            reason=(
                f"deviates {score:.2f}x margin from seasonal prediction"
                if is_anomaly
                else "within seasonal range"
            ),
            details={"predicted": predicted, "margin": margin, "cycles": len(history)},
        )
