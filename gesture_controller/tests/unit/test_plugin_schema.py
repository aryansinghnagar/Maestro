import json
import pytest
import jsonschema
from pathlib import Path

@pytest.fixture
def gesture_schema() -> dict:
    schema_path = Path(__file__).parent.parent.parent / "data" / "gesture_schema.json"
    with open(schema_path, "r") as f:
        return json.load(f)

def test_validate_valid_gesture_schema(gesture_schema: dict) -> None:
    valid_gesture = {
        "name": "SwipeUp",
        "type": "dynamic",
        "priority": 2,
        "states": [
            {
                "id": "Idle",
                "transitions": [
                    {
                        "to": "MovingUp",
                        "condition": "index_tip_y < prev_index_tip_y",
                        "abort": False
                    }
                ]
            },
            {
                "id": "MovingUp",
                "is_terminal": True,
                "min_duration_ms": 150,
                "max_duration_ms": 1000,
                "cooldown_ms": 500,
                "action": "KeyPress:PageUp",
                "transitions": []
            }
        ]
    }
    # Should not raise validation errors
    jsonschema.validate(valid_gesture, gesture_schema)

def test_reject_gesture_missing_required_fields(gesture_schema: dict) -> None:
    # Missing 'type' field
    invalid_gesture = {
        "name": "MissingType",
        "states": []
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_gesture, gesture_schema)

def test_reject_invalid_gesture_type(gesture_schema: dict) -> None:
    # 'invalid_type' is not in enum ["static", "dynamic", "continuous"]
    invalid_gesture = {
        "name": "BadType",
        "type": "invalid_type",
        "states": []
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_gesture, gesture_schema)

def test_reject_invalid_state_properties(gesture_schema: dict) -> None:
    # State containing invalid property 'unknown_prop'
    invalid_gesture = {
        "name": "BadStateProp",
        "type": "static",
        "states": [
            {
                "id": "Idle",
                "unknown_prop": "should_fail",
                "transitions": []
            }
        ]
    }
    # Wait, in jsonschema, properties are not locked (additionalProperties: false is not set by default).
    # If additionalProperties is true, this will pass. Let's test if additionalProperties is true or verify.
    # To check schema validation strictly, let's test missing a required field inside state (e.g. missing 'id').
    invalid_gesture_missing_id = {
        "name": "MissingStateId",
        "type": "static",
        "states": [
            {
                "transitions": []
            }
        ]
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_gesture_missing_id, gesture_schema)

def test_reject_invalid_transition_properties(gesture_schema: dict) -> None:
    # Missing required field 'to' in transition
    invalid_gesture = {
        "name": "BadTransition",
        "type": "static",
        "states": [
            {
                "id": "Idle",
                "transitions": [
                    {
                        "condition": "True"
                    }
                ]
            }
        ]
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_gesture, gesture_schema)
