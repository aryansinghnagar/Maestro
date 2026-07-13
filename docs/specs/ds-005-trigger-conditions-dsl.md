---
title: "DS-005: Trigger Conditions DSL Spec"
---

## DS-005: Trigger Conditions DSL Spec

### 100.1 Grammar (EBNF)

```ebnf
trigger      = "{", "condition:", condition, ",", "action:", string, "}"
condition    = "{", [field_value, { ",", field_value }], "}"
              | "{", "default:", "true", "}"
field_value  = field, ":", value
field        = "app" | "time" | "display" | "audio_playing" | "modifier"
              | "microphone_active" | "fullscreen" | "battery_below"
              | "network" | "weekday"
value        = string | boolean | integer
```

### 100.2 YAML representation

```yaml
triggers:
  - condition:
      app: "chrome"
      time: "09:00-17:00"
      weekday: "mon-fri"
    action: "KeyPress:Ctrl+Shift+Tab"
  - condition:
      default: true
    action: "KeyPress:ArrowLeft"
```

### 100.3 Field reference

| Field | Type | Example | Description |
|---|---|---|---|
| `app` | regex string | `"chrome.*"` | Foreground app name (regex) |
| `time` | string | `"09:00-17:00"` | Time range (HH:MM-HH:MM, supports wraparound) |
| `display` | string | `"primary"`, `"0"` | Display name or index |
| `audio_playing` | boolean | `true` | Is audio currently playing? |
| `modifier` | string | `"ctrl+shift"` | Keyboard modifier held |
| `microphone_active` | boolean | `false` | Is mic in use (call)? |
| `fullscreen` | boolean | `true` | Is foreground app fullscreen? |
| `battery_below` | integer | `20` | Battery percentage threshold |
| `network` | enum | `"wifi"` | Network state: online, offline, wifi, ethernet |
| `weekday` | string | `"mon-fri"` | Day of week: mon, tue, wed, thu, fri, sat, sun |
| `default` | boolean | `true` | Always matches (fallback) |

### 100.4 Evaluation algorithm

```python
def resolve(triggers: list[dict], context: ContextProvider) -> str | None:
    """Resolve triggers to an action."""
    for trigger in triggers:
        condition = trigger.get("condition", {})
        if evaluate(condition, context):
            return trigger.get("action")
    return None

def evaluate(condition: dict, context: ContextProvider) -> bool:
    """Evaluate a condition against current context."""
    if condition.get("default"):
        return True

    for field, expected in condition.items():
        actual = context.get(field)
        if not match(field, expected, actual):
            return False
    return True
```

### 100.5 Schema (JSON Schema)

See §65.5 for full schema.

### 100.6 Examples

**Example 1: Work hours vs off hours**
```yaml
triggers:
  - condition: { app: "chrome", time: "09:00-17:00" }
    action: "KeyPress:Ctrl+Shift+Tab"
  - condition: { app: "chrome" }
    action: "Media:PlayPause"
  - condition: { default: true }
    action: "KeyPress:ArrowLeft"
```

**Example 2: Battery saver**
```yaml
triggers:
  - condition: { battery_below: 20 }
    action: "OS:MinimizeWindow"  # Less CPU-intensive action
  - condition: { default: true }
    action: "KeyPress:Alt+Tab"
```

**Example 3: Meeting mode**
```yaml
triggers:
  - condition: { microphone_active: true, app: "zoom" }
    action: "KeyPress:Cmd+Shift+M"  # Mute in Zoom
  - condition: { default: true }
    action: "Media:PlayPause"
```

---