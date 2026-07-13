---
title: "RFC-015: On-Device Transformer"
---

### RFC-015: On-Device Transformer

**Author:** Refactor Team
**Date:** 2026-07-09
**Status:** Draft (v0.4+)

#### Problem
DTW works for simple custom gestures but struggles with:
- Complex dynamic gestures (e.g., "rotate hand 90° clockwise")
- Pre-trained gesture library (no per-user recording)
- Continuous gesture spotting (not just isolated)

#### Proposed Solution

Small Transformer or TCN over 21-landmark sequence for dynamic gestures.

#### Architecture

```python
class TransformerGestureRecognizer(nn.Module):
    def __init__(self, num_classes: int, input_dim: int = 63, d_model: int = 128,
                 nhead: int = 4, num_layers: int = 3):
        super().__init__()
        self.embedding = nn.Linear(input_dim, d_model)
        self.pos_encoding = nn.Parameter(torch.randn(1, 60, d_model))
        encoder_layer = nn.TransformerEncoderLayer(d_model, nhead, batch_first=True)
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers)
        self.fc = nn.Linear(d_model, num_classes)
```

#### Constraints

- **On-device only** (ADR-030)
- **Small model**: <5MB (distilled)
- **Fast inference**: <5ms on CPU (INT8 quantized)
- **No fine-tuning on user data** (privacy)

#### Training Data

- Synthetic data (procedurally generated hand movements)
- Public datasets (e.g., [SHREC](http://www-rech.telecom-lille.fr/shrec2017-hand/))
- User-recorded gestures (opt-in, anonymized, for evaluation only — NOT for training)

#### Defer to v0.4+

DTW is sufficient for v0.2-v0.3. Transformer is research for v0.4+.

#### Risks

- Model may not generalize across users (different hand sizes, lighting)
- May require per-user calibration (defeats purpose of pre-trained)
- INT8 quantization may degrade accuracy below useful threshold

---