import numpy as np
import pytest
from gesture_controller.vision.one_euro_filter import OneEuroFilter


def test_one_euro_filter_nan_inf_recovery() -> None:
    config = {"filtering": {"one_euro": {"min_cutoff": 1.0, "beta": 0.007}}}
    oef = OneEuroFilter(config)

    landmarks = np.ones((21, 3), dtype=np.float64)
    filt, vel, acc = oef.filter(landmarks, timestamp=1.0)
    assert np.allclose(filt, landmarks)

    # Pass NaN array
    nan_landmarks = np.full((21, 3), np.nan, dtype=np.float64)
    filt_nan, vel_nan, acc_nan = oef.filter(nan_landmarks, timestamp=1.033)

    assert not np.isnan(filt_nan).any()
    assert np.all(vel_nan == 0.0)
    assert np.all(acc_nan == 0.0)


def test_one_euro_filter_zero_dt_handling() -> None:
    config = {"filtering": {"one_euro": {"min_cutoff": 1.0, "beta": 0.007}}}
    oef = OneEuroFilter(config)

    landmarks = np.ones((21, 3), dtype=np.float64)
    oef.filter(landmarks, timestamp=1.0)

    # Frame at identical timestamp
    filt, vel, acc = oef.filter(landmarks + 0.1, timestamp=1.0)
    assert not np.isnan(filt).any()
    assert not np.isnan(vel).any()


def test_one_euro_filter_tremor_fft_tuning() -> None:
    config = {
        "filtering": {
            "one_euro": {"min_cutoff": 1.0, "beta": 0.007},
            "tremor": {"enabled": True, "min_freq": 4.0, "max_freq": 12.0},
        }
    }
    oef = OneEuroFilter(config)

    # Feed 35 frames with 6 Hz sinusoidal tremor on wrist X
    t = 0.0
    for i in range(35):
        lm = np.zeros((21, 3), dtype=np.float64)
        lm[0, 0] = np.sin(2 * np.pi * 6.0 * t)
        filt, vel, acc = oef.filter(lm, timestamp=t)
        t += 0.033

    assert not np.isnan(filt).any()
