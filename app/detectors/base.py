"""
Pluggable anomaly detector interface.

Every detector takes a list of historical values (training window) plus the
current value(s) to evaluate, and returns an AnomalyResult. New detectors
(ML-based forecasting, etc.) just need to implement BaseDetector.evaluate().
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AnomalyResult:
    is_anomaly: bool
    score: float  # detector-specific score (z-score, robust z, deviation %, etc.)
    actual: float
    expected: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    detector: str = ""
    reason: str = ""
    details: dict = field(default_factory=dict)


class BaseDetector(ABC):
    """All detectors implement this. `name` is used in config and alerts."""

    name: str = "base"

    def __init__(self, **params):
        self.params = params

    @abstractmethod
    def evaluate(self, history: list[float], current: float) -> AnomalyResult:
        """
        history: past values used to establish a baseline (training window),
                 ordered oldest -> newest, NOT including `current`.
        current: the latest value being checked.
        """
        raise NotImplementedError
