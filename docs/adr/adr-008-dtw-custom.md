# ADR-008: DTW and JIT-Compiled Numba Distance Matrix for Custom Gestures

## Status
Accepted

## Context
Custom gestures are recorded by users as sequences of 3D landmarks over time. Static FSM checks cannot parse these dynamic patterns. We need a sequence matching algorithm that can compare a real-time buffer of frame features against recorded templates:
1. **Dynamic Time Warping (DTW)**: A classic sequence alignment algorithm.
2. **Hidden Markov Models (HMM) or LSTMs**: Machine learning sequence classifiers.

## Decision
We choose Dynamic Time Warping (DTW) with Euclidean distance, accelerated by Numba JIT compilation (`@numba.jit(nopython=True)`). Real-time frames are stored in a rolling circular buffer of 60 frames. When the FSM falls through, this buffer is normalized and compared against registered templates in batch using JIT-compiled array operations.

## Consequences
- **Pros**:
  - Extremely fast execution (sub-millisecond alignment evaluation for dozens of templates).
  - No training required: users only need to record a single template sample to register a custom gesture.
  - Highly robust to variations in performance speed (time-dilation invariant).
- **Cons**:
  - Requires `numba` package which relies on LLVM compiler binaries.
  - Initial JIT compilation introduces a minor overhead on first execution (~600ms latency), which we manage by pre-compiling or configuring test runners to expect the delay.
