# Configuration Guide

Maestro's settings are defined in a YAML configuration file.

## Configuration Schema

The following options are supported:

| Key | Type | Default | Description |
|---|---|---|---|
| `camera_id` | int | `0` | Camera device index |
| `max_hands` | int | `2` | Maximum hands to track (1-2) |
| `min_detection_confidence` | float | `0.7` | MediaPipe detection threshold |
| `min_tracking_confidence` | float | `0.5` | MediaPipe tracking threshold |
| `one_euro_filter.beta` | float | `0.05` | Filter beta coefficient |
| `one_euro_filter.d_cutoff` | float | `1.0` | Filter derivative cutoff |
| `one_euro_filter.min_cutoff` | float | `1.0` | Filter minimum cutoff frequency |
