"""
Z-score detector.

Classic approach (GitLab's Prometheus anomaly detection post, also used in
the Prometheus blog's "practical anomaly detection" article): assumes the
metric is roughly normally distributed. Flags a value as anomalous if it's
more than `threshold` standard deviations away from the historical mean.

Good for: metrics with a fairly stable, normal-ish distribution (request
rates, latency averages over a large enough window, resource usage %).
Bad for: spiky / heavy-tailed metrics (use the robust/MAD detector instead).
"""
from __future__ import annotations

import statistics

from .base import AnomalyResult, BaseDetector


class ZScoreDetector(BaseDetector):
    name = "zscore"

    def __init__(self, threshold: float = 3.0, min_samples: int = 10, **kwargs):
        super().__init__(threshold=threshold, min_samples=min_samples, **kwargs)
        self.threshold = threshold
        self.min_samples = min_samples

    def evaluate(self, history: list[float], current: float) -> AnomalyResult:
        if len(history) < self.min_samples:
            return AnomalyResult(
                is_anomaly=False,
                score=0.0,
                actual=current,
                detector=self.name,
                reason=f"insufficient history ({len(history)} < {self.min_samples})",
            )

        mean = statistics.fmean(history)
        try:
            stddev = statistics.stdev(history)
        except statistics.StatisticsError:
            stddev = 0.0

        if stddev == 0:
            # Flat history: any deviation at all is notable, but avoid
            # division by zero. Treat exact match as normal, anything else
            # as a large-but-finite score (avoids inf, which breaks strict
            # JSON consumers downstream).
            z = 0.0 if current == mean else (1e6 if current > mean else -1e6)
        else:
            z = (current - mean) / stddev

        is_anomaly = abs(z) > self.threshold
        lower = mean - self.threshold * stddev
        upper = mean + self.threshold * stddev

        return AnomalyResult(
            is_anomaly=is_anomaly,
            score=z,
            actual=current,
            expected=mean,
            lower_bound=lower,
            upper_bound=upper,
            detector=self.name,
            reason=(
                f"z-score {z:.2f} exceeds threshold ±{self.threshold}"
                if is_anomaly
                else "within normal range"
            ),
            details={"mean": mean, "stddev": stddev, "n": len(history)},
        )
