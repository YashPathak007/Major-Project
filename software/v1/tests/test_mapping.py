"""Mapping tests — PLAN.md §6 (smoothing, dead zone, calibration)."""

import math

from touchless.mapping import (
    CalibrationMap, CursorMapper, OneEuroFilter1D, fit_affine,
)


def test_default_map_corners_and_centre():
    mapping = CalibrationMap.default(1920, 1080)
    x, y = mapping(0.05, 0.05)
    assert x == 0.0 and y == 0.0
    x, y = mapping(0.95, 0.95)
    assert x == 1919.0 or abs(x - 1920.0) < 1.0
    x, y = mapping(0.5, 0.5)
    assert abs(x - 960.0) < 2.0 and abs(y - 540.0) < 2.0


def test_map_raw_is_unfiltered_mirror_plus_calibration():
    """Movement decisions use the raw anchor: identical on repeat
    calls (no filter state) and equal to mirror + calibration."""
    mapping = CalibrationMap.default(1920, 1080)
    mapper = CursorMapper(mapping, mirror_x=True, dead_zone_px=0)
    first = mapper.map_raw(0.20, 0.5)
    second = mapper.map_raw(0.20, 0.5)
    assert first == second
    expected = mapping(0.80, 0.5)  # mirrored x
    assert abs(first[0] - expected[0]) < 1.0 and abs(first[1] - expected[1]) < 1.0


def test_mirror_direction():
    mapping = CalibrationMap.default(1920, 1080)
    mirrored = CursorMapper(mapping, mirror_x=True, dead_zone_px=0)
    plain = CursorMapper(mapping, mirror_x=False, dead_zone_px=0)
    # A hand on the user's right (raw image x small, camera faces user)
    # must drive the cursor to the right side of the screen.
    mx, _ = mirrored.update(0.20, 0.5, 1000.0)
    px, _ = plain.update(0.20, 0.5, 1000.0)
    assert mx > 960.0 > px


def test_affine_fit_recovers_known_map():
    # A known affine map, sampled at 5 calibration points, must be
    # recovered by the least-squares fit.
    def truth(hx, hy):
        return 1500 * hx + 100, 900 * hy + 50
    pairs = [((hx, hy), truth(hx, hy)) for hx, hy in
             [(0.1, 0.1), (0.9, 0.1), (0.1, 0.9), (0.9, 0.9), (0.5, 0.5)]]
    mapping = CalibrationMap.from_points(pairs, 1920, 1080)
    for hx, hy in [(0.2, 0.3), (0.7, 0.8), (0.5, 0.5)]:
        gx, gy = mapping(hx, hy)
        tx, ty = truth(hx, hy)
        assert abs(gx - tx) < 1.0 and abs(gy - ty) < 1.0


def test_degenerate_fit_falls_back_to_default():
    pairs = [((0.5, 0.5), (960, 540)), ((0.5, 0.5), (960, 540)),
             ((0.5, 0.5), (960, 540))]
    mapping = CalibrationMap.from_points(pairs, 1920, 1080)
    x, y = mapping(0.05, 0.05)
    assert x == 0.0 and y == 0.0  # default map, not a collapsed fit


def test_dead_zone_holds_micro_tremor():
    mapping = CalibrationMap.default(1920, 1080)
    cursor = CursorMapper(mapping, mirror_x=False, dead_zone_px=3)
    first = cursor.update(0.5, 0.5, 1000.0)
    # A 1 px move must not move the cursor.
    second = cursor.update(0.5005, 0.5, 1000.05)
    assert second == first
    # A 50 px move must pass the dead zone.
    third = cursor.update(0.53, 0.5, 1000.10)
    assert third != first


def test_one_euro_filter_steadies_jitter():
    filt = OneEuroFilter1D(min_cutoff=1.0, beta=0.05)
    noisy = [100.0 + (5.0 if i % 2 else -5.0) for i in range(60)]
    outs = [filt(v, 1000.0 + i / 60.0) for i, v in enumerate(noisy)]
    assert all(math.isfinite(v) for v in outs)
    late = outs[30:]
    assert max(late) - min(late) < 5.0  # jitter attenuated, not amplified


def test_cursor_clamped_to_screen():
    mapping = CalibrationMap.default(1920, 1080)
    cursor = CursorMapper(mapping, mirror_x=False, dead_zone_px=0, sensitivity=1.0)
    x, y = cursor.update(-1.0, 5.0, 1000.0)
    assert 0.0 <= x <= 1919.0 and 0.0 <= y <= 1079.0


def test_sensitivity_scales_around_centre():
    mapping = CalibrationMap.default(1920, 1080)
    normal = CursorMapper(mapping, mirror_x=False, dead_zone_px=0, sensitivity=1.0)
    boosted = CursorMapper(mapping, mirror_x=False, dead_zone_px=0, sensitivity=2.0)
    nx, _ = normal.update(0.6, 0.5, 1000.0)
    bx, _ = boosted.update(0.6, 0.5, 1000.0)
    assert bx - 960.0 > nx - 960.0  # displacement from centre doubles
