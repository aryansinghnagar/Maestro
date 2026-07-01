# ADR-003: Finite State Machine (FSM) over Machine Learning Classification

## Status
Approved

## Context
Standard hand tracking frameworks (like MediaPipe) provide static hand posture classification (e.g., "Fist", "Open Palm"). However, desktop actions require temporal gesture sequences (e.g., holding a pinch and moving, or swiping index finger). 

Relying purely on a machine learning model to classify dynamic gestures introduces non-deterministic behavior, requires huge training datasets, and struggles with time-based constraints (such as minimum hold durations or cooldowns).

## Decision
We implement a deterministic Finite State Machine (FSM) engine with configurable states, transitions, timeouts, and condition evaluations. 

## Consequences
- **High Reliability:** Avoids false positives by enforcing timing constraints (e.g., must stay in "Pinch" state for 150ms before triggering "PinchActive").
- **Customizability:** Allows users to define custom transition behaviors and conditions directly in yaml configuration files.
- **Predictable Behavior:** Easier to debug, test, and trace exact state transition paths compared to black-box ML sequence models.
