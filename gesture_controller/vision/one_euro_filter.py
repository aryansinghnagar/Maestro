import numpy as np
import structlog
from collections import deque
from typing import Any

logger = structlog.get_logger(__name__)


class OneEuroFilter:
    """Vectorized One-Euro filter for hand landmark smoothing.

    Reference: "1-Euro Filter: A Simple Speed-based Low-Pass Filter for Noisy Input"
    by Gery Casiez, Nicolas Roussel, Daniel Vogel. CHI 2012.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
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

        # Pre-allocated temporary calculation buffers to prevent per-frame memory allocation
        self._dx = np.zeros((21, 3), dtype=np.float64)
        self._hat_dx = np.zeros((21, 3), dtype=np.float64)
        self._hat_x = np.zeros((21, 3), dtype=np.float64)

        # Tremor auto-tuning history (using pre-allocated rolling numpy arrays instead of deque)
        self._tremor_history_len = 30
        self._tremor_history_x_arr = np.zeros(self._tremor_history_len, dtype=np.float64)
        self._tremor_history_t_arr = np.zeros(self._tremor_history_len, dtype=np.float64)
        self._tremor_sorted_x = np.zeros(self._tremor_history_len, dtype=np.float64)
        self._tremor_index = 0
        self._tremor_filled = False

    def filter(
        self,
        landmarks: np.ndarray,
        timestamp: float,
        lighting_metric: float | None = None,
        depth_metric: float | None = None,
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
            logger.warning(
                "NaN or Inf detected in landmarks input; resetting One-Euro filter state"
            )
            self.reset()
            self._velocity.fill(0.0)
            self._acceleration.fill(0.0)
            # Replace NaNs/Infs in the input landmarks in-place or into self._x_filt_prev
            np.copyto(self._x_filt_prev, np.where(np.isfinite(landmarks), landmarks, 0.0))
            return self._x_filt_prev, self._velocity, self._acceleration

        # Dynamic parameter adaptation
        oe_config = self._config.get("filtering", {}).get("one_euro", {})
        min_cutoff = oe_config.get("min_cutoff", self._min_cutoff)
        beta = oe_config.get("beta", self._beta)

        # Record x coordinate of wrist (index 0) and timestamp for tremor analysis
        self._tremor_history_x_arr[self._tremor_index] = float(landmarks[0, 0])
        self._tremor_history_t_arr[self._tremor_index] = timestamp
        self._tremor_index += 1
        if self._tremor_index >= self._tremor_history_len:
            self._tremor_index = 0
            self._tremor_filled = True

        tremor_enabled = self._config.get("filtering", {}).get("tremor", {}).get("enabled", False)

        # Detect Tremor via FFT if history is full and enabled
        if tremor_enabled and self._tremor_filled:
            np.copyto(self._tremor_sorted_x[:self._tremor_history_len - self._tremor_index], self._tremor_history_x_arr[self._tremor_index:])
            self._tremor_sorted_x[self._tremor_history_len - self._tremor_index:] = self._tremor_history_x_arr[:self._tremor_index]
            
            # Times
            sorted_t = np.zeros(self._tremor_history_len, dtype=np.float64)
            np.copyto(sorted_t[:self._tremor_history_len - self._tremor_index], self._tremor_history_t_arr[self._tremor_index:])
            sorted_t[self._tremor_history_len - self._tremor_index:] = self._tremor_history_t_arr[:self._tremor_index]
            
            dt = np.mean(np.diff(sorted_t))
            if dt > 0:
                x_detrend = self._tremor_sorted_x - np.mean(self._tremor_sorted_x)
                fft = np.fft.rfft(x_detrend)
                freqs = np.fft.rfftfreq(len(x_detrend), d=dt)
                magnitudes = np.abs(fft)
                
                tremor_cfg = self._config.get("filtering", {}).get("tremor", {})
                min_f = tremor_cfg.get("min_freq", 4.0)
                max_f = tremor_cfg.get("max_freq", 12.0)
                
                tremor_mask = (freqs >= min_f) & (freqs <= max_f)
                if tremor_mask.any():
                    peak_idx = magnitudes[tremor_mask].argmax()
                    peak_freq = freqs[tremor_mask][peak_idx]
                    peak_mag = magnitudes[tremor_mask][peak_idx]
                    total_energy = magnitudes.sum()
                    
                    if total_energy > 0 and (peak_mag / total_energy) > 0.20:
                        min_cutoff = 0.1
                        beta = 0.001

        if self._dynamic.get("lighting_enabled", False) and lighting_metric is not None:
            # Low light (smaller metric) -> more smoothing (lower min_cutoff)
            light_factor = np.clip(lighting_metric / 128.0, 0.3, 1.0)
            min_cutoff *= light_factor

        if self._dynamic.get("depth_scaling_enabled", False) and depth_metric is not None:
            # Far hand (smaller depth metric) -> more smoothing (smaller beta)
            depth_factor = np.clip(depth_metric * 5.0, 0.5, 2.0)
            beta *= depth_factor

        if not self._initialized:
            np.copyto(self._x_prev, landmarks)
            np.copyto(self._x_filt_prev, landmarks)
            self._prev_timestamp = timestamp
            self._initialized = True
            return self._x_filt_prev, self._velocity, self._acceleration

        dt = max(timestamp - self._prev_timestamp, 1e-6)

        # Vectorized computation for all 63 values simultaneously using in-place operations
        # Step 1: Derivative (velocity) with low-pass filtering
        # self._dx = (landmarks - self._x_prev) / dt
        np.subtract(landmarks, self._x_prev, out=self._dx)
        self._dx /= dt

        alpha_d = self._smoothing_factor(dt, self._derivate_cutoff)
        # self._hat_dx = alpha_d * self._dx + (1.0 - alpha_d) * self._dx_prev
        np.multiply(self._dx, alpha_d, out=self._hat_dx)
        self._dx_prev *= (1.0 - alpha_d)
        np.add(self._hat_dx, self._dx_prev, out=self._hat_dx)

        # Step 2: Adaptive cutoff based on velocity
        cutoff = min_cutoff + beta * np.abs(self._hat_dx)
        alpha = self._smoothing_factor(dt, cutoff)

        # Step 3: Filtered position
        # self._hat_x = alpha * landmarks + (1.0 - alpha) * self._x_filt_prev
        np.multiply(landmarks, alpha, out=self._hat_x)
        self._x_filt_prev *= (1.0 - alpha)
        np.add(self._hat_x, self._x_filt_prev, out=self._hat_x)

        # Update state
        np.copyto(self._prev_velocity, self._velocity)
        np.copyto(self._velocity, self._hat_dx)
        
        # self._acceleration = (self._velocity - self._prev_velocity) / dt
        np.subtract(self._velocity, self._prev_velocity, out=self._acceleration)
        self._acceleration /= dt

        np.copyto(self._x_prev, landmarks)
        np.copyto(self._dx_prev, self._hat_dx)
        np.copyto(self._x_filt_prev, self._hat_x)
        self._prev_timestamp = timestamp

        return self._x_filt_prev, self._velocity, self._acceleration

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
        self._tremor_history_x_arr.fill(0.0)
        self._tremor_history_t_arr.fill(0.0)
        self._tremor_sorted_x.fill(0.0)
        self._tremor_index = 0
        self._tremor_filled = False

    @property
    def _tremor_history_x(self) -> list[float]:
        if not self._tremor_filled:
            return [float(x) for x in self._tremor_history_x_arr[:self._tremor_index]]
        return [float(x) for x in np.concatenate((self._tremor_history_x_arr[self._tremor_index:], self._tremor_history_x_arr[:self._tremor_index]))]

    @property
    def _tremor_history_t(self) -> list[float]:
        if not self._tremor_filled:
            return [float(t) for t in self._tremor_history_t_arr[:self._tremor_index]]
        return [float(t) for t in np.concatenate((self._tremor_history_t_arr[self._tremor_index:], self._tremor_history_t_arr[:self._tremor_index]))]
