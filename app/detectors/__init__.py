from .base import AnomalyResult, BaseDetector
from .robust_mad import RobustMADDetector
from .seasonal import SeasonalDetector
from .zscore import ZScoreDetector

REGISTRY: dict[str, type[BaseDetector]] = {
    ZScoreDetector.name: ZScoreDetector,
    RobustMADDetector.name: RobustMADDetector,
    SeasonalDetector.name: SeasonalDetector,
}


def build_detector(name: str, **params) -> BaseDetector:
    """Instantiate a detector by its registry name with the given params."""
    if name not in REGISTRY:
        raise ValueError(f"Unknown detector '{name}'. Available: {list(REGISTRY)}")
    return REGISTRY[name](**params)


__all__ = [
    "AnomalyResult",
    "BaseDetector",
    "ZScoreDetector",
    "RobustMADDetector",
    "SeasonalDetector",
    "REGISTRY",
    "build_detector",
]
