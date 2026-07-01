import ast
import operator
import time
import structlog
from dataclasses import dataclass, field
from typing import Callable, Any, Optional

from gesture_controller.models.data_types import FeatureVector, GestureEvent
from gesture_controller.core.event_bus import EventBus

logger = structlog.get_logger(__name__)

# Operators allowed in FSM conditions for AST compilation
ALLOWED_OPS: dict[Any, Callable[..., Any]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.And: lambda a, b: a and b,
    ast.Or: lambda a, b: a or b,
    ast.Not: lambda a: not a,
}

def compile_condition(expr_str: str, thresholds: dict[str, float]) -> Callable[[FeatureVector], bool]:
    """Parse a condition string into a safe callable. Raises ValueError on disallowed constructs."""
    tree = ast.parse(expr_str, mode="eval")

    def _eval_node(node: Any) -> Any:
        if isinstance(node, ast.Name):
            if node.id == "True":
                return True
            if node.id == "False":
                return False
            if node.id in thresholds:
                return thresholds[node.id]
            return node.id  # Attribute name on FeatureVector
        elif isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Compare):
            left = _eval_node(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = _eval_node(comparator)
                op_fn = ALLOWED_OPS.get(type(op))
                if op_fn is None:
                    raise ValueError(f"Disallowed operator: {type(op).__name__}")
                left = ("_cmp", op_fn, left, right)
            return left
        elif isinstance(node, ast.BoolOp):
            values = [_eval_node(v) for v in node.values]
            op_fn = ALLOWED_OPS.get(type(node.op))
            if op_fn is None:
                raise ValueError(f"Disallowed boolean op: {type(node.op).__name__}")
            return ("_bool", op_fn, values)
        elif isinstance(node, ast.UnaryOp):
            operand = _eval_node(node.operand)
            op_fn = ALLOWED_OPS.get(type(node.op))
            if op_fn is None:
                raise ValueError(f"Disallowed unary op: {type(node.op).__name__}")
            return ("_unary", op_fn, operand)
        elif isinstance(node, ast.Call):
            # Safe support for abs() function calls
            if isinstance(node.func, ast.Name) and node.func.id == "abs":
                if len(node.args) != 1:
                    raise ValueError("abs() expects exactly 1 argument")
                arg = _eval_node(node.args[0])
                return ("_abs", arg)
            raise ValueError(f"Disallowed function call: {node.func.id if isinstance(node.func, ast.Name) else 'complex'}")
        else:
            raise ValueError(f"Disallowed AST node: {type(node).__name__}")

    compiled = _eval_node(tree.body)

    def _execute(fv: FeatureVector) -> bool:
        return bool(_resolve(compiled, fv))

    return _execute

def _resolve(node: Any, fv: FeatureVector) -> Any:
    if isinstance(node, (bool, int, float)):
        return node
    elif isinstance(node, str):
        # Attribute/component vector lookup (e.g. index_tip_velocity_y -> index_tip_velocity[1])
        if node.endswith("_x") or node.endswith("_y") or node.endswith("_z"):
            attr_name = node[:-2]
            if hasattr(fv, attr_name):
                vec = getattr(fv, attr_name)
                axis = {"x": 0, "y": 1, "z": 2}[node[-1]]
                return float(vec[axis])
        if hasattr(fv, node):
            return getattr(fv, node)
        raise AttributeError(f"Unknown feature or threshold in condition: {node}")
    elif isinstance(node, tuple):
        tag = node[0]
        if tag == "_cmp":
            _, op_fn, left, right = node
            return op_fn(_resolve(left, fv), _resolve(right, fv))
        elif tag == "_bool":
            _, op_fn, values = node
            resolved = [_resolve(v, fv) for v in values]
            # Custom boolean list reducer
            res = resolved[0]
            for val in resolved[1:]:
                res = op_fn(res, val)
            return res
        elif tag == "_unary":
            _, op_fn, operand = node
            return op_fn(_resolve(operand, fv))
        elif tag == "_abs":
            _, arg = node
            return abs(_resolve(arg, fv))
    raise ValueError(f"Cannot resolve node payload: {node}")


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
        initial_state: str = "Idle"
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

    def evaluate(self, features: FeatureVector, timestamp: float) -> GestureEvent | None:
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
            logger.debug("FSM state timeout", fsm=self.name, state=self.current_state, duration=duration_ms)
            self.current_state = self.initial_state
            self.state_entered_at = None
            self._features_at_state_entry = None
            return None

        # 3. Minimum duration check
        if duration_ms < state.min_duration_ms:
            return None

        # Populate delta values dynamically based on state entry features
        if self._features_at_state_entry is not None:
            features.index_tip_delta_y = features.index_tip[1] - self._features_at_state_entry.index_tip[1]
            features.palm_center_delta_x = features.palm_center[0] - self._features_at_state_entry.palm_center[0]
            features.palm_center_delta_y = features.palm_center[1] - self._features_at_state_entry.palm_center[1]
            features.palm_delta_y = features.palm_center[1] - self._features_at_state_entry.palm_center[1]

        # 4. Evaluate transitions
        for transition in state.transitions:
            try:
                condition_met = transition.condition_fn(features)
            except Exception as e:
                logger.error("Error evaluating condition", fsm=self.name, error=str(e), condition=transition.condition)
                condition_met = False

            if condition_met:
                if transition.is_abort:
                    self.current_state = self.initial_state
                    self.state_entered_at = None
                    self._features_at_state_entry = None
                    return None

                # Transition to new state
                self.current_state = transition.target_state
                self.state_entered_at = timestamp
                self._features_at_state_entry = features

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
        self._fsms: list[GestureFSM] = []
        self._event_bus = event_bus
        self._global_cooldown_until = 0.0
        
        engine_cfg = config.get("engine", {})
        self._global_cooldown_ms = float(engine_cfg.get("global_cooldown_ms", 200.0))
        self._thresholds = config.get("config", {}).get("default_thresholds", {})
        
        self._load_gestures(config)

    def reload_gestures(self, config: dict[str, Any]) -> None:
        """Clear and reload all gestures from config."""
        self._fsms = []
        self._load_gestures(config)
        logger.info("GestureFSMManager reloaded gestures", count=len(self._fsms))

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
                    transitions.append(FSMTransition(
                        target_state=to_state,
                        condition=cond_str,
                        condition_fn=compiled_fn,
                        is_abort=is_abort
                    ))

                states_dict[s_id] = FSMState(
                    id=s_id,
                    is_terminal=is_term,
                    min_duration_ms=min_dur,
                    max_duration_ms=max_dur,
                    transitions=transitions,
                    action=action,
                    cooldown_ms=cooldown
                )

            fsm = GestureFSM(name, priority, g_type, states_dict)
            self._fsms.append(fsm)
            
        # Sort FSMs by priority (lower priority values are executed first)
        self._fsms.sort(key=lambda x: x.priority)
        logger.info("Loaded and sorted gesture FSMs", count=len(self._fsms))

    def evaluate(self, features: FeatureVector) -> GestureEvent | None:
        """Evaluate all FSMs. Return best GestureEvent or None."""
        candidates = []
        for fsm in self._fsms:
            # Skip evaluation for discrete FSMs if in global cooldown, but allow active continuous scrolling to evaluate
            in_global_cooldown = features.timestamp < self._global_cooldown_until
            if in_global_cooldown and not (fsm.gesture_type == "continuous" and fsm.current_state == "ScrollingActive"):
                continue

            event = fsm.evaluate(features, features.timestamp)
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

    def reset_all(self) -> None:
        """Reset all state machines."""
        for fsm in self._fsms:
            fsm.reset()

    def get_states(self) -> dict[str, tuple[str, float]]:
        """Return a mapping of FSM name -> (current_state, progress_ratio)."""
        states = {}
        for fsm in self._fsms:
            progress = 0.0
            if fsm.state_entered_at is not None and fsm.current_state != "Idle":
                state_obj = fsm.states.get(fsm.current_state)
                if state_obj and state_obj.max_duration_ms < float("inf") and state_obj.max_duration_ms > 0:
                    elapsed = (time.monotonic() - fsm.state_entered_at) * 1000.0
                    progress = min(elapsed / state_obj.max_duration_ms, 1.0)
            states[fsm.name] = (fsm.current_state, progress)
        return states
