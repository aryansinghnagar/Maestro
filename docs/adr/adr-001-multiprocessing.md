# ADR-001: Multiprocessing over Threading for Engine Orchestration

## Status
Approved

## Context
The Gesture Control app needs to continuously capture video frames from the webcam, run MediaPipe hand landmark extraction inference, filter coordinates, evaluate gesture transitions via a state machine, and trigger OS input simulation commands (key presses, mouse moves). 

Running these operations sequentially in a single thread introduces severe frame drops (low FPS) and lagging tracking (high latency) because MediaPipe inference blocks execution. 

Attempting to split these tasks using Python threads is constrained by the Global Interpreter Lock (GIL), where CPU-bound threads (MediaPipe inference, One-Euro filtering, and PyQt GUI rendering) compete for the same execution thread, resulting in performance degradation.

## Decision
We utilize Python's `multiprocessing` module to isolate the camera stream capture and MediaPipe landmark extraction into a dedicated worker process. 

A high-performance shared memory segment (`multiprocessing.shared_memory.SharedMemory`) acts as a single-slot zero-copy ring buffer to share the raw RGB video frames between the camera worker and the main application coordinator process. 

## Consequences
- **GIL Bypass:** Isolates heavy MediaPipe CPU/GPU landmark inference from the main Qt event loop and state machine, maintaining high frame rates.
- **Latency Control:** The main process reads the most recent frame directly from shared memory, dropping stale frames if inference runs slower than the camera rate.
- **Complexity:** Requires careful lifecycle management of the shared memory segments (allocation, cleanup, attachment, detachment) to prevent resource leaks and memory crashes.
