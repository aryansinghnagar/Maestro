---
title: "DS-006: Telemetry Schema Spec"
---

## DS-006: Telemetry Schema Spec

### 101.1 Metrics

| Metric | Type | Tags | Description |
|---|---|---|---|
| `maestro.frames.processed` | counter | `backend` | Number of frames processed |
| `maestro.gestures.triggered` | counter | `backend` | Number of gestures triggered (NOT gesture names) |
| `maestro.latency.e2e_ms` | histogram | `backend` | E2E latency in ms |
| `maestro.latency.inference_ms` | histogram | `backend` | Inference latency in ms |
| `maestro.backend.active` | gauge | `backend` | Currently active backend (1=active, 0=inactive) |
| `maestro.plugins.loaded` | gauge | | Number of plugins loaded |
| `maestro.errors.count` | counter | `component` | Number of errors per component |
| `maestro.session.duration_s` | histogram | | Session duration in seconds |

### 101.2 NOT collected (privacy-critical)

- Camera frames
- Hand landmarks
- Voice audio
- Gesture names (only aggregate count)
- App names (foreground apps)
- URLs
- File paths
- User identifiers (no user ID, no machine ID, no IP, no MAC)
- Geolocation
- Hardware serial numbers

### 101.3 OpenTelemetry export

```python
# Export via OTLP (gRPC)
endpoint = "https://telemetry.maestro.example.com:4317"
exporter = OTLPMetricExporter(endpoint=endpoint)
reader = PeriodicExportingMetricReader(exporter, export_interval_millis=60000)
```

### 101.4 Privacy review

Telemetry schema is reviewed quarterly. Any addition requires:
1. ADR update
2. Privacy review (does it leak user data?)
3. Documentation in PRIVACY.md
4. User notification (in-app)

### 101.5 Opt-out

```yaml
# config.yaml (default)
telemetry:
  enabled: false
```

Users can preview what's sent:

```bash
maestro telemetry preview
# Output:
# Metrics that would be sent (sample):
#   maestro.frames.processed: 1234
#   maestro.gestures.triggered: 56
#   maestro.latency.e2e_ms: 14.2
#   maestro.backend.active: coreml (1)
#   maestro.session.duration_s: 600
```

### 101.6 Tests

```python
def test_telemetry_no_user_data():
    """Verify telemetry does NOT include user data."""
    telemetry = TelemetryManager({"telemetry.enabled": True})
    telemetry.record_gesture("Minimize")  # Pass gesture name

    # Verify gesture name is NOT in metrics
    metrics = telemetry.get_pending_metrics()
    for metric in metrics:
        assert "Minimize" not in str(metric)
        assert "gesture" not in metric.tags  # No gesture tag

def test_telemetry_disabled_by_default():
    """Telemetry should be disabled by default."""
    telemetry = TelemetryManager({})
    assert telemetry._enabled is False
    # No network calls should be made
```

---