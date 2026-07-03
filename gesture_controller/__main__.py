"""
Support invocation of the package using `python -m gesture_controller`.
"""
import sys
from gesture_controller.gui.app_entry import main

if __name__ == "__main__":
    sys.exit(main())
