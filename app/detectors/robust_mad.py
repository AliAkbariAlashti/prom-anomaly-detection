"""
Robust (median + MAD) detector.

Same idea as z-score, but uses median and Median Absolute Deviation instead
of mean/stddev. This is much less sensitive to outliers already present in
the training window, which makes it a better fit for spiky, non-normally
distributed metrics like error counts, queue lengths, or burst-y traffic
(this is exactly the "robust" strategy in Grafana's promql-anomaly-detection
framework).

The 0.6745 scale factor converts MAD into an estimate that's comparable to
standard deviation under a normal distribution, so the same threshold
intuition (~3 = anomalous) still roughly applies.
"""
from __future__ import annotations

import statistics

from .base import AnomalyResult, BaseDetector

_MAD_SCALE = 0.6745


class RobustMADDetector(BaseDetector):
    name = "robust_mad"

    def __init__(self, threshold: float = 3.5, min_samples: int = 10, **kwargs):
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

        median = statistics.median(history)
        abs_devs = [abs(x - median) for x in history]
        mad = statistics.median(abs_devs)

        if mad == 0:
            robust_z = 0.0 if current == median else (1e6 if current > median else -1e6)
        else:
            robust_z = _MAD_SCALE * (current - median) / mad

        is_anomaly = abs(robust_z) > self.threshold

        # Bounds expressed back in original units for readability.
        if mad > 0:
            spread = (self.threshold * mad) / _MAD_SCALE
            lower, upper = median - spread, median + spread
        else:
            lower, upper = median, median

        return AnomalyResult(
            is_anomaly=is_anomaly,
            score=robust_z,
            actual=current,
            expected=median,
            lower_bound=lower,
            upper_bound=upper,
            detector=self.name,
            reason=(
                f"robust z-score {robust_z:.2f} exceeds threshold ±{self.threshold}"
                if is_anomaly
                else "within normal range"
            ),
            details={"median": median, "mad": mad, "n": len(history)},
        )
