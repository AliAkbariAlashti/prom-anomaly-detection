import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.detectors import RobustMADDetector, SeasonalDetector, ZScoreDetector
from app.durations import parse_duration


def test_zscore_detects_outlier():
    history = [10.0, 10.2, 9.8, 10.1, 9.9, 10.0, 10.3, 9.7, 10.0, 10.1]
    detector = ZScoreDetector(threshold=3.0, min_samples=10)

    normal = detector.evaluate(history, 10.05)
    assert not normal.is_anomaly

    spike = detector.evaluate(history, 50.0)
    assert spike.is_anomaly
    assert spike.score > 3.0


def test_zscore_insufficient_history():
    detector = ZScoreDetector(min_samples=10)
    result = detector.evaluate([1.0, 2.0], 5.0)
    assert not result.is_anomaly
    assert "insufficient" in result.reason


def test_robust_mad_handles_existing_outliers_better_than_zscore():
    # History with one big outlier already baked in.
    history = [10.0, 10.1, 9.9, 10.0, 9.8, 10.2, 9.9, 10.0, 100.0, 10.1]

    z = ZScoreDetector(threshold=3.0, min_samples=10)
    robust = RobustMADDetector(threshold=3.5, min_samples=10)

    # A value that's clearly off from the "real" cluster of ~10
    test_val = 30.0

    z_result = z.evaluate(history, test_val)
    robust_result = robust.evaluate(history, test_val)

    # Robust score should be more sensitive (larger magnitude / more likely
    # to flag) than z-score's, because the existing 100.0 outlier inflates
    # the stddev z relies on, while MAD stays small.
    assert abs(robust_result.score) > abs(z_result.score)


def test_seasonal_detector_uses_median_of_offsets():
    detector = SeasonalDetector(threshold=2.0, min_samples=3, seasonal_margin_pct=0.1)
    # Three previous weeks all around 100, one current value way off.
    history = [98.0, 101.0, 99.0]
    result = detector.evaluate(history, 100.5)
    assert not result.is_anomaly
    assert result.expected == 99.0  # median

    spike_result = detector.evaluate(history, 500.0)
    assert spike_result.is_anomaly


def test_seasonal_detector_insufficient_cycles():
    detector = SeasonalDetector(min_samples=3)
    result = detector.evaluate([100.0, 101.0], 102.0)
    assert not result.is_anomaly
    assert "insufficient" in result.reason


def test_parse_duration():
    assert parse_duration("30s") == 30
    assert parse_duration("5m") == 300
    assert parse_duration("2h") == 7200
    assert parse_duration("1d") == 86400
    assert parse_duration("1w") == 604800


def test_parse_duration_invalid():
    import pytest

    with pytest.raises(ValueError):
        parse_duration("nonsense")
