"""Post-install verification script.
Runs diagnostics to verify dependencies, camera connection, and config integrity.
"""
import sys
from pathlib import Path
import structlog

logger = structlog.get_logger(__name__)

def check_imports() -> bool:
    """Verify that all core libraries are importable."""
    try:
        import cv2
        import mediapipe
        import numpy
        import PyQt6
        import yaml
        import jsonschema
        import structlog
        import numba
        return True
    except ImportError as e:
        print(f"Missing dependency check: {e}")
        return False

def check_camera() -> bool:
    """Verify camera device accessibility."""
    try:
        import cv2
        # Try to open the default camera index
        cap = cv2.VideoCapture(0)
        ok = cap.isOpened()
        cap.release()
        return ok
    except Exception as e:
        print(f"Camera diagnostic check encountered error: {e}")
        return False

def check_mediapipe() -> bool:
    """Verify MediaPipe Hands Solutions interface is loaded."""
    try:
        import mediapipe as mp
        # Check tasks API or solutions
        return hasattr(mp, "tasks") or hasattr(mp, "solutions")
    except Exception as e:
        print(f"MediaPipe diagnostic check failed: {e}")
        return False

def check_config() -> bool:
    """Verify default configurations are present and valid YAML."""
    try:
        import yaml
        # Search for default_config.yaml relative to python path
        # In source tree, config is under gesture_controller/data/default_config.yaml
        # In PyInstaller, the sys._MEIPASS dir will contain "data/default_config.yaml"
        import sys
        if hasattr(sys, "_MEIPASS"):
            config_path = Path(sys._MEIPASS) / "data" / "default_config.yaml"
        else:
            config_path = Path(__file__).parent.parent / "gesture_controller" / "data" / "default_config.yaml"

        if not config_path.exists():
            print(f"Default config file path not found: {config_path}")
            return False

        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return isinstance(cfg, dict)
    except Exception as e:
        print(f"Config diagnostic check failed: {e}")
        return False

def main() -> int:
    """Run all verification tests."""
    checks = [
        ("Dependencies", check_imports),
        ("Camera Connection", check_camera),
        ("MediaPipe Engine", check_mediapipe),
        ("Configuration File Structure", check_config),
    ]
    all_ok = True
    print("Starting post-install diagnostic checks:")
    for name, fn in checks:
        try:
            ok = fn()
            status = "OK" if ok else "FAIL"
            if not ok:
                all_ok = False
            print(f"  [{status}] {name}")
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            all_ok = False
            
    if all_ok:
        print("All diagnostic checks passed successfully!")
        return 0
    else:
        print("Some diagnostic checks failed. Check output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
