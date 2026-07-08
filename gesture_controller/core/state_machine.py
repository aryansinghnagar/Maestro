import ast
import copy
import operator
import threading
import time
import structlog
from dataclasses import dataclass, field
from typing import Callable, Any, Optional

from gesture_controller.models.data_types import FeatureVector, GestureEvent
from gesture_controller.core.event_bus import EventBus

logger = structlog.get_logger(__name__)

# Operators allowed in FSM conditions for AST compilation
import numpy as np


def compile_condition(
    expr_str: str, thresholds: dict[str, float]
) -> Callable[[FeatureVector], bool]:
    """Parse a condition string into a safe callable. Raises ValueError on disallowed constructs."""
    from gesture_controller.core.config_manager import SafeExpressionEvaluator

    compiled_ast = SafeExpressionEvaluator.compile_expression(expr_str)

    def _execute(fv: FeatureVector) -> bool:
        context = dict(thresholds)
        for key in dir(fv):
            if key.startswith("_"):
                continue
            try:
                val = getattr(fv, key)
            except AttributeError:
                continue
            if callable(val):
                continue
            context[key] = val

            if isinstance(val, (tuple, list, np.ndarray)) and len(val) == 3:
                context[f"{key}_x"] = float(val[0])
                context[f"{key}_y"] = float(val[1])
                context[f"{key}_z"] = float(val[2])

        return SafeExpressionEvaluator.evaluate(compiled_ast, context)

    return _execute


@dataclass
class FSMTransition:
    target_state: str
    condition: str
    condition_fn: Callable[[FeatureVector], bool]
    is_abort: bool = False


@dataclass
class FSMState:
    id: str
    is_terminal: bool = False
    min_duration_ms: float = 0.0
    max_duration_ms: float = float("inf")
    transitions: list[FSMTransition] = field(default_factory=list)
    action: str | None = None
    cooldown_ms: float = 0.0


class GestureFSM:
    """Finite State Machine for identifying single static, dynamic, or continuous gestures."""

    def __init__(
        self,
        name: str,
        priority: int,
        gesture_type: str,
        states: dict[str, FSMState],
        initial_state: str = "Idle",
    ) -> None:
        self.name = name
        self.priority = priority
        self.gesture_type = gesture_type
        self.states = states
        self.initial_state = initial_state

        self.current_state = initial_state
        self.state_entered_at: float | None = None
        self.last_triggered_at: float | None = None
        self.is_in_cooldown = False
        self._cooldown_until = 0.0
        self._features_at_state_entry: FeatureVector | None = None

    def evaluate(
        self, features: FeatureVector, timestamp: float, correlation_id: str = ""
    ) -> GestureEvent | None:
        """Evaluate one frame against this FSM. Returns GestureEvent or None."""
        state = self.states.get(self.current_state)
        if not state:
            logger.error("FSM in invalid state", fsm=self.name, state=self.current_state)
            self.reset()
            return None

        # 1. Cooldown evaluation
        if self.is_in_cooldown:
            if timestamp >= self._cooldown_until:
                self.is_in_cooldown = False
                self.current_state = self.initial_state
                self.state_entered_at = None
                self._features_at_state_entry = None
            else:
                return None

        # Initialize start time if this is the first frame
        if self.state_entered_at is None:
            self.state_entered_at = timestamp
            self._features_at_state_entry = features

        duration_ms = (timestamp - self.state_entered_at) * 1000.0

        # 2. Timeout check (max_duration)
        if duration_ms > state.max_duration_ms and not state.is_terminal:
            logger.debug(
                "FSM state timeout", fsm=self.name, state=self.current_state, duration=duration_ms
            )
            self.current_state = self.initial_state
            self.state_entered_at = None
            self._features_at_state_entry = None
            return None

        # 3. Minimum duration check
        if duration_ms < state.min_duration_ms:
            return None

        # Populate delta values dynamically based on state entry features
        if self._features_at_state_entry is not None:
            features = copy.copy(features)
            features.index_tip_delta_y = (
                features.index_tip[1] - self._features_at_state_entry.index_tip[1]
            )
            features.palm_center_delta_x = (
                features.palm_center[0] - self._features_at_state_entry.palm_center[0]
            )
            features.palm_center_delta_y = (
                features.palm_center[1] - self._features_at_state_entry.palm_center[1]
            )
            features.palm_delta_y = (
                features.palm_center[1] - self._features_at_state_entry.palm_center[1]
            )

        # 4. Evaluate transitions
        for transition in state.transitions:
            try:
                condition_met = transition.condition_fn(features)
            except Exception as e:
                logger.error(
                    "Error evaluating condition",
                    fsm=self.name,
                    error=str(e),
                    condition=transition.condition,
                )
                condition_met = False

            if condition_met:
                if transition.is_abort:
                    self.current_state = self.initial_state
                    self.state_entered_at = None
                    self._features_at_state_entry = None
                    return None

                # Transition to new state
                old_state = self.current_state
                self.current_state = transition.target_state
                self.state_entered_at = timestamp
                self._features_at_state_entry = features
                logger.info(
                    "metric_fsm_transition",
                    fsm=self.name,
                    from_state=old_state,
                    to_state=transition.target_state,
                    correlation_id=correlation_id,
                )

                new_state = self.states.get(transition.target_state)
                if not new_state:
                    self.reset()
                    return None

                # 5. Terminal (Trigger) state checks
                if new_state.is_terminal:
                    event = GestureEvent(
                        gesture_name=self.name,
                        gesture_type=self.gesture_type,
                        action=new_state.action or "",
                        confidence=features.confidence,
                        hand=features.handedness,
                        timestamp=timestamp,
                        gesture_source="fsm",
                        metadata={"correlation_id": correlation_id},
                    )
                    self.last_triggered_at = timestamp
                    self.is_in_cooldown = True
                    self._cooldown_until = timestamp + (new_state.cooldown_ms / 1000.0)
                    self.current_state = self.initial_state
                    self.state_entered_at = None
                    self._features_at_state_entry = None
                    return event
                break

        # 6. Continuous gesture evaluation (always run action while active)
        if self.gesture_type == "continuous" and self.current_state == "ScrollingActive":
            # Retrieve active action from Trigger definition
            trigger_state = self.states.get("Trigger")
            action_str = trigger_state.action if trigger_state else None

            if action_str:
                if "delta" in action_str and self._features_at_state_entry is not None:
                    # Scroll amount scale (approx. 0.1 relative translation is 3 scroll units)
                    raw_delta = features.palm_center_delta_y
                    scroll_val = int(raw_delta * 30.0)
                    action_str = f"MouseScroll:{scroll_val}"

                return GestureEvent(
                    gesture_name=self.name,
                    gesture_type=self.gesture_type,
                    action=action_str,
                    confidence=features.confidence,
                    hand=features.handedness,
                    timestamp=timestamp,
                    gesture_source="fsm",
                    metadata={"correlation_id": correlation_id},
                )

        return None

    def reset(self) -> None:
        """Reset state machine."""
        self.current_state = self.initial_state
        self.state_entered_at = None
        self.last_triggered_at = None
        self.is_in_cooldown = False
        self._cooldown_until = 0.0
        self._features_at_state_entry = None


class GestureFSMManager:
    """Loads and manages all gesture FSMs, evaluating candidates and resolving conflicts."""

    def __init__(self, config: dict[str, Any], event_bus: EventBus) -> None:
        self._fsms_prototypes: list[GestureFSM] = []
        self._hand_fsms: dict[int, list[GestureFSM]] = {}
        self._event_bus = event_bus
        self._global_cooldown_until = 0.0
        self._lock = threading.RLock()

        engine_cfg = config.get("engine", {})
        self._global_cooldown_ms = float(engine_cfg.get("global_cooldown_ms", 200.0))
        self._thresholds = config.get("config", {}).get("default_thresholds", {})

        self._load_gestures(config)

    def reload_gestures(self, config: dict[str, Any]) -> None:
        """Clear and reload all gestures from config."""
        with self._lock:
            prev_prototypes = self._fsms_prototypes
            self._fsms_prototypes = []
            try:
                self._load_gestures(config)
                self._hand_fsms.clear()
            except Exception:
                self._fsms_prototypes = prev_prototypes
                logger.exception("Gesture reload failed; keeping previous FSM set")
                return
            logger.info("GestureFSMManager reloaded gestures", count=len(self._fsms_prototypes))

    def _load_gestures(self, config: dict[str, Any]) -> None:
        """Load gestures from config yaml."""
        gestures_list = config.get("gestures", [])
        for g in gestures_list:
            name = g.get("name", "Unknown")
            g_type = g.get("type", "static")
            priority = g.get("priority", 999)

            # Combine default thresholds with gesture-specific overrides
            g_thresholds = self._thresholds.copy()
            g_thresholds.update(g.get("thresholds", {}))

            states_dict = {}
            for s in g.get("states", []):
                s_id = s.get("id")
                is_term = s.get("is_terminal", s_id == "Trigger")

                min_dur = float(s.get("min_duration_ms", 0.0))
                # Support both timeout_ms and max_duration_ms
                max_dur = float(s.get("max_duration_ms") or s.get("timeout_ms") or float("inf"))
                action = s.get("action")
                cooldown = float(s.get("cooldown_ms", 0.0))

                transitions = []
                for t in s.get("transitions", []):
                    to_state = t.get("to")
                    cond_str = t.get("condition", "True")
                    is_abort = t.get("abort", False)

                    compiled_fn = compile_condition(cond_str, g_thresholds)
                    transitions.append(
                        FSMTransition(
                            target_state=to_state,
                            condition=cond_str,
                            condition_fn=compiled_fn,
                            is_abort=is_abort,
                        )
                    )

                states_dict[s_id] = FSMState(
                    id=s_id,
                    is_terminal=is_term,
                    min_duration_ms=min_dur,
                    max_duration_ms=max_dur,
                    transitions=transitions,
                    action=action,
                    cooldown_ms=cooldown,
                )

            fsm = GestureFSM(name, priority, g_type, states_dict)
            self._fsms_prototypes.append(fsm)

        # Sort FSMs by priority (lower priority values are executed first)
        self._fsms_prototypes.sort(key=lambda x: x.priority)
        logger.info("Loaded and sorted gesture FSM prototypes", count=len(self._fsms_prototypes))

    def evaluate(
        self, features: FeatureVector, correlation_id: str = "", track_id: int = 0
    ) -> GestureEvent | None:
        """Evaluate FSMs for a specific hand track ID. Return best GestureEvent or None."""
        import copy

        candidates = []
        with self._lock:
            if track_id not in self._hand_fsms:
                self._hand_fsms[track_id] = copy.deepcopy(self._fsms_prototypes)
            fsms_snapshot = list(self._hand_fsms[track_id])

        for fsm in fsms_snapshot:
            # Skip evaluation for discrete FSMs if in global cooldown, but allow active continuous scrolling to evaluate
            in_global_cooldown = features.timestamp < self._global_cooldown_until
            if in_global_cooldown and not (
                fsm.gesture_type == "continuous" and fsm.current_state == "ScrollingActive"
            ):
                continue

            event = fsm.evaluate(features, features.timestamp, correlation_id)
            if event:
                # Store priority as metadata for conflict resolution
                event.metadata["priority"] = fsm.priority
                candidates.append(event)

        if not candidates:
            return None

        # Resolve conflict
        best_event = self._resolve_conflict(candidates)

        # Only set global cooldown for discrete triggers (continuous scroll does not trigger it)
        if best_event.gesture_type != "continuous":
            self._global_cooldown_until = features.timestamp + (self._global_cooldown_ms / 1000.0)
        return best_event

    def _resolve_conflict(self, candidates: list[GestureEvent]) -> GestureEvent:
        """Priority conflict resolution:
        1. Highest confidence
        2. Lowest priority number (Priority 1 > Priority 2)
        3. YAML definition order (which is preserved in our sorted _fsms list)
        """
        # Sort by: confidence desc, priority asc
        candidates.sort(key=lambda e: (-e.confidence, e.metadata.get("priority", 999)))
        return candidates[0]

    def remove_hand(self, track_id: int) -> None:
        """Clean up FSM state for a retired hand track ID."""
        with self._lock:
            self._hand_fsms.pop(track_id, None)

    def reset_all(self) -> None:
        """Reset all state machines across all tracked hands."""
        with self._lock:
            self._hand_fsms.clear()
            self._global_cooldown_until = 0.0

    def get_states(self) -> dict[str, tuple[str, float]]:
        """Return a mapping of FSM name -> (current_state, progress_ratio) for the first active hand."""
        states = {}
        with self._lock:
            if not self._hand_fsms:
                for fsm in self._fsms_prototypes:
                    states[fsm.name] = ("Idle", 0.0)
                return states
            first_track_id = min(self._hand_fsms.keys())
            fsms = self._hand_fsms[first_track_id]

        for fsm in fsms:
            progress = 0.0
            if fsm.state_entered_at is not None and fsm.current_state != "Idle":
                state_obj = fsm.states.get(fsm.current_state)
                if (
                    state_obj
                    and state_obj.max_duration_ms < float("inf")
                    and state_obj.max_duration_ms > 0
                ):
                    elapsed = (time.monotonic() - fsm.state_entered_at) * 1000.0
                    progress = min(elapsed / state_obj.max_duration_ms, 1.0)
            states[fsm.name] = (fsm.current_state, progress)
        return states
