import pytest
import yaml
import json
import jsonschema
from pathlib import Path
from gesture_controller.core.config_manager import ConfigManager, SafeExpressionEvaluator

def test_safe_evaluator_valid_expressions() -> None:
    # Test compilation
    code = SafeExpressionEvaluator.compile_expression("index_extended == True and middle_extended == False")
    
    # Test evaluation
    context = {"index_extended": True, "middle_extended": False}
    assert SafeExpressionEvaluator.evaluate(code, context) is True
    
    context2 = {"index_extended": True, "middle_extended": True}
    assert SafeExpressionEvaluator.evaluate(code, context2) is False

def test_safe_evaluator_operator_precedence() -> None:
    code = SafeExpressionEvaluator.compile_expression("x > 5 and y < 10 or z == True")
    assert SafeExpressionEvaluator.evaluate(code, {"x": 6, "y": 8, "z": False}) is True
    assert SafeExpressionEvaluator.evaluate(code, {"x": 4, "y": 8, "z": True}) is True

def test_safe_evaluator_invalid_node_types_raises() -> None:
    # Function calls are prohibited
    with pytest.raises(ValueError, match="is not allowed"):
        SafeExpressionEvaluator.compile_expression("print('hello')")
        
    # Attribute access is prohibited
    with pytest.raises(ValueError, match="is not allowed"):
        SafeExpressionEvaluator.compile_expression("index.extended == True")

def test_config_manager_get_and_set() -> None:
    # Simple instantiation without validation error since we mock default config
    cm = ConfigManager()
    
    # Test setting and getting using dot notation
    cm.set("camera.device_id", 99)
    assert cm.get("camera.device_id") == 99
    
    # Test nested dict creation via set
    cm.set("nested.very.deep.value", "hello")
    assert cm.get("nested.very.deep.value") == "hello"
    
    # Test default fallback
    assert cm.get("nonexistent.key", "fallback") == "fallback"

def test_config_manager_deep_merge() -> None:
    cm = ConfigManager()
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"d": 4, "e": 5}, "f": 6}
    
    cm._deep_merge(base, override)
    assert base == {"a": 1, "b": {"c": 2, "d": 4, "e": 5}, "f": 6}

def test_config_manager_validation_raises_on_invalid_type(tmp_path: Path) -> None:
    # Write an invalid schema and invalid config to temp files
    schema_file = tmp_path / "config_schema.json"
    config_file = tmp_path / "default_config.yaml"
    
    schema_data = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "device_id": {"type": "integer"}
        }
    }
    
    # device_id must be integer, we provide string
    config_data = {
        "device_id": "not-an-integer"
    }
    
    with open(schema_file, "w") as f:
        json.dump(schema_data, f)
        
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
        
    # Temporarily monkeypatch standard schema & config path
    import gesture_controller.core.config_manager as cm_mod
    original_schema = cm_mod.Path(__file__).parent.parent / "data" / "config_schema.json"
    original_default = cm_mod.DEFAULT_CONFIG_PATH
    
    try:
        # Override module variables to point to temp files
        cm_mod.DEFAULT_CONFIG_PATH = config_file
        
        # Monkeypatch _load_schema to load from our temp schema file
        def mock_load_schema(self: ConfigManager) -> None:
            with open(schema_file, "r") as sf:
                self._schema = json.load(sf)
                
        # Apply patch
        original_load_schema = ConfigManager._load_schema
        ConfigManager._load_schema = mock_load_schema  # type: ignore
        
        with pytest.raises(jsonschema.ValidationError):
            ConfigManager(config_path=config_file)
            
        # Restore _load_schema
        ConfigManager._load_schema = original_load_schema
    finally:
        cm_mod.DEFAULT_CONFIG_PATH = original_default
