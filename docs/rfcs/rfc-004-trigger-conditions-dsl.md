---
title: "RFC-004: Trigger Conditions DSL"
---

### RFC-004: Trigger Conditions DSL

**Author:** Refactor Team
**Date:** 2026-07-09
**Status:** Accepted (implementation in Sprint 10)

#### Problem
Current `app_profiles` only remap gesture → action based on foreground app name. Users want conditions based on time of day, display, audio state, etc. (feature parity with BetterTouchTool/Karabiner).

#### Proposed Solution

```yaml
# Gesture definition with triggers
gestures:
  - name: SwipeLeft
    type: dynamic
    triggers:
      - condition:
          app: "chrome.exe"
          time: "09:00-17:00"
        action: "KeyPress:Ctrl+Shift+Tab"
      - condition:
          app: "chrome.exe"
          time: "17:00-09:00"
        action: "Media:PlayPause"
      - condition:
          default: true
        action: "KeyPress:ArrowLeft"
```

#### Grammar

```
condition := { field: value, ... } | { default: true }
field := "app" | "time" | "display" | "audio_playing" | "modifier" |
         "microphone_active" | "fullscreen" | "battery_below" | "network" |
         "weekday"
trigger := { condition: condition, action: string }
triggers := [ trigger, ... ]
```

#### Evaluation
Conditions are evaluated in order. First match wins. `default: true` is the fallback.

#### Implementation
1. Extend `gesture_schema.json` to validate `triggers` array
2. Update `ActionDispatcher._resolve_action` to evaluate conditions
3. Add condition evaluator (§65.3)
4. Add context provider (§65.4)
5. Backward-compatible: if no `triggers` key, use existing `app_profiles` behavior

#### Backward Compatibility
Existing `app_profiles` config still works (deprecated). Migration:
```yaml
# Old
app_profiles:
  chrome:
    SwipeLeft: "KeyPress:Ctrl+Shift+Tab"

# New
triggers:
  - condition: { app: "chrome" }
    action: "KeyPress:Ctrl+Shift+Tab"
```

#### Tests
- `test_trigger_conditions.py` — each condition type
- `test_trigger_resolver.py` — first-match-wins, default fallback
- `test_context_provider.py` — each context field

---