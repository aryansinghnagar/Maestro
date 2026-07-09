import sys
import argparse
from pathlib import Path

from gesture_controller.core.compliance import erase_data, export_data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Maestro: Cross-platform hand-gesture desktop controller."
    )
    subparsers = parser.add_subparsers(dest="command")

    # 'erase' subcommand
    subparsers.add_parser(
        "erase",
        help="Erase all Maestro configuration, log files, custom templates, and plugins from this system (Right to Erasure)."
    )

    # 'export' subcommand
    export_parser = subparsers.add_parser(
        "export",
        help="Export sanitized/redacted configurations, templates, logs, and plugin list to a ZIP file."
    )
    export_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="maestro-data.zip",
        help="Path where the output ZIP archive should be saved (default: maestro-data.zip)"
    )

    args = parser.parse_args()

    if args.command == "erase":
        print("Erasing all Maestro configuration, logs, and custom templates...")
        erase_data()
        print("Data erasure complete.")
    elif args.command == "export":
        zip_path = Path(args.output).resolve()
        print(f"Exporting sanitized/redacted Maestro diagnostics to: {zip_path}...")
        try:
            export_data(zip_path)
            print("Export complete.")
        except Exception as e:
            print(f"Error during export: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Default behavior: run GUI app
        from gesture_controller.gui.app_entry import main as run_gui
        run_gui()


if __name__ == "__main__":
    main()
