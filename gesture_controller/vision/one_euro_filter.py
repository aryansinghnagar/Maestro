import numpy as np
import structlog
logger = structlog.get_logger(__name__)
from typing import Any

class OneEuroFilter:
    """Vectorized One-Euro filter for hand landmark smoothing.
    
    Reference: "1-Euro Filter: A Simple Speed-based Low-Pass Filter for Noisy Input"
    by Gery Casiez, Nicolas Roussel, Daniel Vogel. CHI 2012.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        oe_config = config.get("filtering", {}).get("one_euro", {})
        self._min_cutoff = oe_config.get("min_cutoff", 1.0)
        self._beta = oe_config.get("beta", 0.007)
        self._derivate_cutoff = oe_config.get("derivate_cutoff", 1.0)
        self._dynamic = config.get("filtering", {}).get("dynamic_adaptation", {})

        # Pre-allocate state arrays for 21 landmarks x 3 axes
        # Shape: (21, 3)
        self._x_prev = np.zeros((21, 3), dtype=np.float64)
        self._x_filt_prev = np.zeros((21, 3), dtype=np.float64)
        self._dx_prev = np.zeros((21, 3), dtype=np.float64)
        self._initialized = False

        # Velocity output (attached to filtered landmarks)
        self._velocity = np.zeros((21, 3), dtype=np.float64)
        self._acceleration = np.zeros((21, 3), dtype=np.float64)
        self._prev_velocity = np.zeros((21, 3), dtype=np.float64)
        self._prev_timestamp = 0.0

    def filter(
        self, 
        landmarks: np.ndarray, 
        timestamp: float,
        lighting_metric: float | None = None, 
        depth_metric: float | None = None
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Filter landmarks and return (filtered, velocity, acceleration).
        
        Args:
            landmarks: (21, 3) array of [x, y, z] per landmark
            timestamp: current time in seconds
            lighting_metric: avg pixel intensity [0, 255] for dynamic adaptation
            depth_metric: wrist-to-MCP distance for dynamic adaptation
            
        Returns:
            (filtered_landmarks, velocity, acceleration) each (21, 3)
        """
        # NaN or Inf input recovery: reset filter state and return zero vectors
        if not np.isfinite(landmarks).all():
            logger.warning("NaN or Inf detected in landmarks input; resetting One-Euro filter state")
            self.reset()
            landmarks = np.where(np.isfinite(landmarks), landmarks, 0.0)
            return landmarks, np.zeros_like(landmarks), np.zeros_like(landmarks)

        # Dynamic parameter adaptation
        min_cutoff = self._min_cutoff
        beta = self._beta
        
        if self._dynamic.get("lighting_enabled", False) and lighting_metric is not None:
            # Low light (smaller metric) -> more smoothing (lower min_cutoff)
            light_factor = np.clip(lighting_metric / 128.0, 0.3, 1.0)
            min_cutoff *= light_factor
            
        if self._dynamic.get("depth_scaling_enabled", False) and depth_metric is not None:
            # Far hand (smaller depth metric) -> more smoothing (smaller beta)
            depth_factor = np.clip(depth_metric * 5.0, 0.5, 2.0)
            beta *= depth_factor

        if not self._initialized:
            self._x_prev = landmarks.copy()
            self._x_filt_prev = landmarks.copy()
            self._prev_timestamp = timestamp
            self._initialized = True
            return landmarks.copy(), self._velocity.copy(), self._acceleration.copy()

        dt = max(timestamp - self._prev_timestamp, 1e-6)

        # Vectorized computation for all 63 values simultaneously
        # Step 1: Derivative (velocity) with low-pass filtering
        dx = (landmarks - self._x_prev) / dt
        alpha_d = self._smoothing_factor(dt, self._derivate_cutoff)
        hat_dx = alpha_d * dx + (1.0 - alpha_d) * self._dx_prev

        # Step 2: Adaptive cutoff based on velocity
        cutoff = min_cutoff + beta * np.abs(hat_dx)
        alpha = self._smoothing_factor(dt, cutoff)

        # Step 3: Filtered position
        hat_x = alpha * landmarks + (1.0 - alpha) * self._x_filt_prev

        # Update state
        self._prev_velocity = self._velocity.copy()
        self._velocity = hat_dx.copy()
        self._acceleration = (self._velocity - self._prev_velocity) / dt
        self._x_prev = landmarks.copy()
        self._dx_prev = hat_dx.copy()
        self._x_filt_prev = hat_x.copy()
        self._prev_timestamp = timestamp

        return hat_x.copy(), self._velocity.copy(), self._acceleration.copy()

    @staticmethod
    def _smoothing_factor(te: float, cutoff: float | np.ndarray) -> float | np.ndarray:
        """Compute smoothing factor alpha from sampling period and cutoff frequency.
        alpha = te / (te + (1 / (2 * pi * cutoff)))"""
        tau = 1.0 / (2.0 * np.pi * cutoff)
        return te / (te + tau)

    def reset(self) -> None:
        """Reset filter state. Call on camera reconnect or hand lost."""
        self._x_prev.fill(0)
        self._x_filt_prev.fill(0)
        self._dx_prev.fill(0)
        self._velocity.fill(0)
        self._acceleration.fill(0)
        self._prev_velocity.fill(0)
        self._prev_timestamp = 0.0
        self._initialized = False
