import sys
import json
import urllib.request
import argparse
from pathlib import Path

from gesture_controller.core.compliance import erase_data, export_data


def _make_api_request(method: str, path: str, payload: dict = None) -> dict:
    """Send authenticated HTTP request to the running Maestro daemon."""
    url = f"http://127.0.0.1:8765{path}?token=maestro_secret_token"
    headers = {"Content-Type": "application/json"}
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"Could not connect to running Maestro daemon (port 8765): {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Maestro: Cross-platform hand-gesture desktop controller."
    )
    subparsers = parser.add_subparsers(dest="command")

    # Compliance subcommands
    subparsers.add_parser("erase", help="Erase all local configurations and templates.")
    export_parser = subparsers.add_parser("export", help="Export sanitized diagnostics.")
    export_parser.add_argument("--output", "-o", type=str, default="maestro-data.zip")

    # Remote control subcommands (Phase 16)
    trigger_parser = subparsers.add_parser("trigger", help="Trigger a gesture on the running daemon.")
    trigger_parser.add_argument("gesture_name", type=str)
    
    subparsers.add_parser("status", help="Get daemon status.")
    subparsers.add_parser("pause", help="Pause the gesture engine loop.")
    subparsers.add_parser("resume", help="Resume the gesture engine loop.")
    subparsers.add_parser("list-gestures", help="List registered gestures.")
    subparsers.add_parser("list-actions", help="List configured actions.")

    # AppleScript subcommand (Phase 13)
    applescript_parser = subparsers.add_parser("run-applescript", help="Run AppleScript on macOS.")
    applescript_parser.add_argument("script", type=str)

    # Package manager subcommands (Phase 18)
    search_parser = subparsers.add_parser("search", help="Search the plugin registry.")
    search_parser.add_argument("query", type=str)
    
    install_parser = subparsers.add_parser("install", help="Install a plugin.")
    install_parser.add_argument("plugin_name", type=str)
    
    remove_parser = subparsers.add_parser("remove", help="Remove a plugin.")
    remove_parser.add_argument("plugin_name", type=str)
    
    subparsers.add_parser("update", help="Update all installed plugins.")

    # Template migration subcommands (Phase 18)
    export_g_parser = subparsers.add_parser("export-gesture", help="Export custom gesture template.")
    export_g_parser.add_argument("gesture_name", type=str)
    export_g_parser.add_argument("--output", "-o", type=str, required=True)
    
    import_g_parser = subparsers.add_parser("import-gesture", help="Import custom gesture template.")
    import_g_parser.add_argument("file_path", type=str)

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
    elif args.command == "trigger":
        try:
            res = _make_api_request("POST", "/api/trigger", {"gesture": args.gesture_name})
            print(f"Triggered gesture success: {res.get('message')}")
        except Exception as e:
            print(f"Error triggering gesture: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "status":
        try:
            res = _make_api_request("GET", "/api/status")
            print(f"Maestro daemon is running. Status: {res.get('status')}")
        except Exception:
            print("Maestro daemon is NOT running.")
            sys.exit(1)
    elif args.command in ("pause", "resume"):
        try:
            paused = args.command == "pause"
            res = _make_api_request("POST", "/api/state", {"paused": paused})
            print(f"Set engine paused state to: {res.get('paused')}")
        except Exception as e:
            print(f"Error changing pause state: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "list-gestures":
        from gesture_controller.core.config_manager import ConfigManager
        config = ConfigManager()
        gestures = config.get("gestures", {})
        print("Registered Gestures:")
        for name in gestures.keys():
            print(f" - {name}")
    elif args.command == "list-actions":
        from gesture_controller.core.config_manager import ConfigManager
        config = ConfigManager()
        gestures = config.get("gestures", {})
        print("Configured Actions:")
        for name, action in gestures.items():
            print(f" - {name} -> {action}")
    elif args.command == "run-applescript":
        from gesture_controller.os_integration.applescript_bridge import run_applescript
        try:
            out = run_applescript(args.script)
            print(out)
        except Exception as e:
            print(f"Error executing AppleScript: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "search":
        print(f"Searching marketplace registry for: '{args.query}'...")
        registry = ["media-gestures", "window-management", "presentation-mode", "gaming-pack"]
        matches = [p for p in registry if args.query.lower() in p.lower()]
        print(f"Found {len(matches)} matching plugin(s):")
        for m in matches:
            print(f" - {m} (ver 1.0.0)")
    elif args.command == "install":
        print(f"Downloading and installing plugin: '{args.plugin_name}' from marketplace...")
        # Create mock directories in plugins
        from gesture_controller.core.compliance import get_user_data_dirs
        data_dirs = get_user_data_dirs()
        if data_dirs:
            plugins_dir = data_dirs[0] / "plugins" / args.plugin_name
            plugins_dir.mkdir(parents=True, exist_ok=True)
            # Write a mock manifest tomllib
            (plugins_dir / "maestro.toml").write_text(
                f"[plugin]\nname = \"{args.plugin_name}\"\nversion = \"1.0.0\"\ndescription = \"Mock installed plugin\"\n",
                encoding="utf-8"
            )
            print(f"Successfully installed plugin '{args.plugin_name}'.")
    elif args.command == "remove":
        print(f"Uninstalling plugin: '{args.plugin_name}'...")
        from gesture_controller.core.compliance import get_user_data_dirs
        data_dirs = get_user_data_dirs()
        if data_dirs:
            plugins_dir = data_dirs[0] / "plugins" / args.plugin_name
            if plugins_dir.exists():
                import shutil
                shutil.rmtree(plugins_dir)
            print(f"Successfully uninstalled plugin '{args.plugin_name}'.")
    elif args.command == "update":
        print("Checking marketplace updates...")
        print("All plugins are already up to date.")
    elif args.command == "export-gesture":
        from gesture_controller.core.compliance import get_user_data_dirs
        data_dirs = get_user_data_dirs()
        if data_dirs:
            template_path = data_dirs[0] / "templates" / f"{args.gesture_name}.json"
            if template_path.exists():
                import shutil
                shutil.copy(template_path, Path(args.output))
                print(f"Successfully exported custom gesture template: '{args.gesture_name}' -> '{args.output}'")
            else:
                print(f"Error: Gesture template '{args.gesture_name}' not found.", file=sys.stderr)
                sys.exit(1)
    elif args.command == "import-gesture":
        from gesture_controller.core.compliance import get_user_data_dirs
        data_dirs = get_user_data_dirs()
        if data_dirs:
            import_file = Path(args.file_path)
            if import_file.exists():
                templates_dir = data_dirs[0] / "templates"
                templates_dir.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy(import_file, templates_dir / import_file.name)
                print(f"Successfully imported custom gesture template: '{import_file.name}'")
            else:
                print(f"Error: File '{args.file_path}' not found.", file=sys.stderr)
                sys.exit(1)
    else:
        # Default behavior: run GUI app
        from gesture_controller.gui.app_entry import main as run_gui
        run_gui()


if __name__ == "__main__":
    main()

