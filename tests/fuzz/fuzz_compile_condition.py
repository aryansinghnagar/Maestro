try:
    import atheris
except ImportError:
    import sys
    print("Atheris not installed. Skipping fuzz target execution.")
    sys.exit(0)

# Import the module to fuzz
with atheris.instrument_imports():
    from gesture_controller.core.config_manager import SafeExpressionEvaluator
    from gesture_controller.core.state_machine import compile_condition

def TestOneInput(data):
    """Atheris entry point."""
    fdp = atheris.FuzzedDataProvider(data)
    try:
        expr_str = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 1024))
    except Exception:
        return

    try:
        # We expect SafeExpressionEvaluator.compile_expression to raise ValueError for unsafe/invalid inputs,
        # but it should NEVER crash with unexpected exceptions (e.g. TypeError, KeyError, etc.)
        SafeExpressionEvaluator.compile_expression(expr_str)
    except ValueError:
        pass
    except Exception as e:
        print(f"Unexpected exception in compile_expression: {type(e).__name__}: {e} for input {repr(expr_str)}")
        raise e

    try:
        compile_condition(expr_str, {})
    except ValueError:
        pass
    except Exception as e:
        print(f"Unexpected exception in compile_condition: {type(e).__name__}: {e} for input {repr(expr_str)}")
        raise e

def main():
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()

if __name__ == "__main__":
    main()
