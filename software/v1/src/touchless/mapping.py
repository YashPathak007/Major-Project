"""Camera-to-screen mapping, smoothing, dead zone — PLAN.md §6, §9.

Pipeline order for every frame: raw hand point -> mirror (cursor
direction decision, §8 Phase 0: hand-right -> cursor-right as seen by
the user facing the screen, so the camera x-axis is mirrored) ->
1 Euro filter (REPORT.md basis) -> dead zone -> calibration affine
-> screen pixels, clamped to the screen.

The cursor itself is NEVER eased (§5): the filter smooths the hand
point, and the cursor follows the smoothed point 1:1 with no
additional animation.

Smoothing presets are starting values, not pilot results (PLAN.md
§6: budgets are TARGETS TO VALIDATE).
"""

from __future__ import annotations

import math

import numpy as np

# Default hand range: the comfortable hand area mapped to the screen
# when no calibration profile exists (skip-to-defaults path, §2 J3).
DEFAULT_HAND_MIN = 0.05
DEFAULT_HAND_MAX = 0.95

# 1 Euro filter presets: (min_cutoff, beta, d_cutoff).
# Higher min_cutoff = less lag, more jitter. Higher beta = steadier
# during fast moves. Values are starting points for pilot tuning.
SMOOTHING_PARAMS = {
    "steady": (0.7, 0.02, 1.0),
    "balanced": (1.0, 0.05, 1.0),
    "responsive": (1.7, 0.10, 1.0),
}


def _alpha(cutoff: float, dt: float) -> float:
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class _LowPass:
    def __init__(self) -> None:
        self.s: float | None = None

    def __call__(self, x: float, alpha: float) -> float:
        if self.s is None:
            self.s = x
        else:
            self.s = alpha * x + (1.0 - alpha) * self.s
        return self.s


class OneEuroFilter1D:
    """The 1 Euro filter (Casiez, Roussel & Vogel): adaptive low-pass.

    Cutoff rises with movement speed, so slow moves settle steadily
    while fast moves track fast — the velocity-aware behaviour §6
    requires. Falls back to a plain exponential average if the state
    ever becomes invalid (Kalman-style fallback role, simplified).
    """

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.05, d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x = _LowPass()
        self._dx = _LowPass()
        self._t_prev: float | None = None
        self._x_prev: float | None = None

    def __call__(self, x: float, t: float) -> float:
        if self._t_prev is None:
            dt = 1.0 / 60.0
        else:
            dt = max(t - self._t_prev, 1e-6)
        self._t_prev = t
        if self._x_prev is None:
            dx = 0.0
        else:
            dx = (x - self._x_prev) / dt
        self._x_prev = x
        dx_hat = self._dx(dx, _alpha(self.d_cutoff, dt))
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        out = self._x(x, _alpha(cutoff, dt))
        if not math.isfinite(out):  # fallback: hold last good value
            return self._x.s if self._x.s is not None else x
        return out

    def reset(self) -> None:
        self._x = _LowPass()
        self._dx = _LowPass()
        self._t_prev = None
        self._x_prev = None


class OneEuroFilter2D:
    """Two independent 1 Euro filters, one per axis."""

    def __init__(self, preset: str = "balanced"):
        params = SMOOTHING_PARAMS.get(preset, SMOOTHING_PARAMS["balanced"])
        self.fx = OneEuroFilter1D(*params)
        self.fy = OneEuroFilter1D(*params)

    def __call__(self, x: float, y: float, t: float) -> tuple[float, float]:
        return self.fx(x, t), self.fy(y, t)

    def reset(self) -> None:
        self.fx.reset()
        self.fy.reset()


def fit_affine(hand_points, screen_points):
    """Least-squares affine map hand -> screen.

    hand_points / screen_points: sequences of (x, y), same length,
    >= 3 non-collinear pairs. Returns a 2x3 matrix, or None when the
    fit is degenerate (caller falls back to the default map).
    """
    if len(hand_points) < 3 or len(hand_points) != len(screen_points):
        return None
    a = np.array([[x, y, 1.0] for x, y in hand_points], dtype=float)
    b = np.array(screen_points, dtype=float)
    try:
        sol, *_ = np.linalg.lstsq(a, b, rcond=None)
    except np.linalg.LinAlgError:
        return None
    if not np.all(np.isfinite(sol)):
        return None
    # Reject degenerate maps (a collapsed axis would fling the cursor).
    if abs(np.linalg.det(sol[:2, :2])) < 1e-6:
        return None
    return sol.T  # 2x3: [[a, b, c], [d, e, f]]


class CalibrationMap:
    """A fitted (or default) camera-to-screen mapping for one profile."""

    def __init__(self, matrix=None, screen_width: int = 1920, screen_height: int = 1080):
        self.matrix = matrix
        self.screen_width = screen_width
        self.screen_height = screen_height

    @classmethod
    def default(cls, screen_width: int, screen_height: int) -> "CalibrationMap":
        span = DEFAULT_HAND_MAX - DEFAULT_HAND_MIN
        # Offset derived from the same scale factor (not recomputed as
        # (-MIN * width) / span) so the min corner maps to exactly 0.0:
        # IEEE multiplication commutes, so a*MIN - MIN*a == 0 exactly.
        a_x = screen_width / span
        a_y = screen_height / span
        matrix = np.array([
            [a_x, 0.0, -DEFAULT_HAND_MIN * a_x],
            [0.0, a_y, -DEFAULT_HAND_MIN * a_y],
        ])
        return cls(matrix, screen_width, screen_height)

    @classmethod
    def from_points(cls, pairs, screen_width: int, screen_height: int) -> "CalibrationMap":
        """pairs: iterable of ((hand_x, hand_y), (screen_x, screen_y))."""
        hand = [p[0] for p in pairs]
        screen = [p[1] for p in pairs]
        matrix = fit_affine(hand, screen)
        if matrix is None:
            return cls.default(screen_width, screen_height)
        return cls(matrix, screen_width, screen_height)

    def __call__(self, hand_x: float, hand_y: float) -> tuple[float, float]:
        vec = np.array([hand_x, hand_y, 1.0])
        sx, sy = self.matrix @ vec
        return float(sx), float(sy)


class CursorMapper:
    """Full cursor path: mirror -> smooth -> dead zone -> map -> clamp.

    The mirror step implements the §8 cursor-direction decision:
    hand-right -> cursor-right as seen by the user facing the screen.
    A laptop webcam faces the user, so raw image x runs opposite to
    the user's right; mirroring first makes the cursor follow the
    hand as the user perceives it (mirror convention).
    """

    def __init__(self, calibration: CalibrationMap, mirror_x: bool = True,
                 preset: str = "balanced", dead_zone_px: int = 3,
                 sensitivity: float = 1.0):
        self.calibration = calibration
        self.mirror_x = mirror_x
        self.filter = OneEuroFilter2D(preset)
        self.dead_zone_px = dead_zone_px
        self.sensitivity = sensitivity
        self._last_output: tuple[float, float] | None = None

    def reset(self) -> None:
        self.filter.reset()
        self._last_output = None

    def mirror_point(self, hand_x: float, hand_y: float) -> tuple[float, float]:
        """Apply the mirror step only (used by calibration capture so
        stored points live in the same space the mapper fits)."""
        return (1.0 - hand_x if self.mirror_x else hand_x), hand_y

    def map_raw(self, hand_x: float, hand_y: float) -> tuple[float, float]:
        """Mirror + calibration only: no filter, dead zone, sensitivity
        or clamping. Used for movement decisions (drag/scroll) so a
        filter settling after a pose change cannot masquerade as hand
        movement — the displayed cursor still uses update()."""
        mx = 1.0 - hand_x if self.mirror_x else hand_x
        return self.calibration(mx, hand_y)

    def update(self, hand_x: float, hand_y: float, t: float) -> tuple[float, float]:
        """Map one hand point to screen pixels. Never eases the cursor."""
        mx = 1.0 - hand_x if self.mirror_x else hand_x
        sx, sy = self.filter(mx, hand_y, t)
        px, py = self.calibration(sx, sy)
        # Sensitivity scales displacement around the screen centre.
        if self.sensitivity != 1.0:
            cx = self.calibration.screen_width / 2.0
            cy = self.calibration.screen_height / 2.0
            px = cx + (px - cx) * self.sensitivity
            py = cy + (py - cy) * self.sensitivity
        px = min(max(px, 0.0), float(self.calibration.screen_width - 1))
        py = min(max(py, 0.0), float(self.calibration.screen_height - 1))
        if self._last_output is not None and self.dead_zone_px > 0:
            lx, ly = self._last_output
            if math.hypot(px - lx, py - ly) < self.dead_zone_px:
                return self._last_output  # micro-tremor held, not injected
        self._last_output = (px, py)
        return px, py
