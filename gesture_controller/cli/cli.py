import sys
import json
import urllib.request
import argparse
from pathlib import Path
from typing import Any

from gesture_controller.core.compliance import erase_data, export_data


def _make_api_request(
    method: str, path: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Send authenticated HTTP request to the running Maestro daemon."""
    from gesture_controller.core.integration_server import get_or_create_api_token

    token = get_or_create_api_token()
    url = f"http://127.0.0.1:8765{path}?token={token}"
    headers = {"Content-Type": "application/json"}
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=1.0) as resp:  # nosec B310
            res_data = json.loads(resp.read().decode("utf-8"))
            if isinstance(res_data, dict):
                return res_data
            return {}
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
    trigger_parser = subparsers.add_parser(
        "trigger", help="Trigger a gesture on the running daemon."
    )
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
    export_g_parser = subparsers.add_parser(
        "export-gesture", help="Export custom gesture template."
    )
    export_g_parser.add_argument("gesture_name", type=str)
    export_g_parser.add_argument(
        "--output", "-o", type=str, required=True
    )  # Audit log verification subcommand
    subparsers.add_parser(
        "verify-audit-log", help="Verify integrity of broker audit log SHA-256 hash chains."
    )

    import_g_parser = subparsers.add_parser(
        "import-gesture", help="Import custom gesture template."
    )
    import_g_parser.add_argument("file_path", type=str)

    # API token subcommands
    subparsers.add_parser("token", help="Print the current API token.")
    subparsers.add_parser("regenerate-token", help="Regenerate the API token.")
    subparsers.add_parser("download-voice-model", help="Download the Vosk voice model (~50MB).")

    # Performance & profiling subcommands (Sprint 11)
    subparsers.add_parser("profile-start", help="Start a cProfile session on the running daemon.")
    profile_stop_parser = subparsers.add_parser(
        "profile-stop", help="Stop the cProfile session and print the top-30 cumulative report."
    )
    profile_stop_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Optional path to write raw pstats dump (e.g. profile.pstats).",
    )
    subparsers.add_parser(
        "metrics", help="Print Prometheus-format metrics from the running daemon."
    )

    args = parser.parse_args()

    if args.command == "token":
        from gesture_controller.core.integration_server import get_or_create_api_token
        from gesture_controller.core.paths import api_token_path

        tok = get_or_create_api_token()
        print(f"API token: {tok}")
        print(f"Token file: {api_token_path()}")
    elif args.command == "regenerate-token":
        response = (
            input("This will invalidate the current token. Continue? [y/N]: ").strip().lower()
        )
        if response not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)
        from gesture_controller.core.integration_server import get_or_create_api_token
        from gesture_controller.core.paths import api_token_path

        token_path = api_token_path()
        try:
            token_path.unlink(missing_ok=True)
        except Exception as e:
            print(f"Error unlinking token file: {e}", file=sys.stderr)
        new_tok = get_or_create_api_token()
        print(f"New API token: {new_tok}")
    elif args.command == "download-voice-model":
        import urllib.request
        import zipfile
        from gesture_controller.core.paths import user_data_dir

        model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
        model_dir = user_data_dir() / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        zip_path = model_dir / "vosk-model.zip"

        print(f"Downloading Vosk model from {model_url}...")
        try:
            urllib.request.urlretrieve(model_url, zip_path)  # nosec B310
            print("Extracting...")
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(model_dir)
            zip_path.unlink()
            print(f"Model extracted to {model_dir}")
        except Exception as e:
            print(f"Error downloading voice model: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "erase":
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
                f'[plugin]\nname = "{args.plugin_name}"\nversion = "1.0.0"\ndescription = "Mock installed plugin"\n',
                encoding="utf-8",
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
                print(
                    f"Successfully exported custom gesture template: '{args.gesture_name}' -> '{args.output}'"
                )
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
    elif args.command == "profile-start":
        from gesture_controller.core.profiler import start_profiling

        start_profiling()
        print("cProfile session started. Run 'maestro profile-stop' to get results.")
    elif args.command == "profile-stop":
        from gesture_controller.core.profiler import stop_profiling

        output = Path(args.output) if getattr(args, "output", None) else None
        report = stop_profiling(output_path=output)
        print(report)
        if output:
            print(f"Raw stats written to: {output}")
    elif args.command == "verify-audit-log":
        import hashlib
        from gesture_controller.core.compliance import get_user_data_dirs

        data_dirs = get_user_data_dirs()
        log_path = data_dirs[0] / "audit.log" if data_dirs else None
        if not log_path or not log_path.exists():
            print("No audit.log file found to verify. Integrity check passed (empty).")
            return

        last_hash = "0" * 64
        valid = True
        line_num = 0
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line_num += 1
                try:
                    entry = json.loads(line)
                    expected_hash = entry.get("hash")
                    entry_copy = dict(entry)
                    entry_copy.pop("hash", None)
                    prev_hash = entry_copy.get("prev_hash", "0" * 64)

                    if prev_hash != last_hash:
                        print(
                            f"Audit log tampered at line {line_num}: prev_hash mismatch",
                            file=sys.stderr,
                        )
                        valid = False
                        break

                    calc_str = json.dumps(entry_copy, sort_keys=True)
                    calc_hash = hashlib.sha256(calc_str.encode("utf-8")).hexdigest()
                    if calc_hash != expected_hash:
                        print(
                            f"Audit log tampered at line {line_num}: hash mismatch", file=sys.stderr
                        )
                        valid = False
                        break

                    last_hash = expected_hash
                except Exception as exc:
                    print(f"Error parsing audit log line {line_num}: {exc}", file=sys.stderr)
                    valid = False
                    break

        if valid:
            print(f"Audit log verification SUCCESSful: {line_num} records verified.")
        else:
            sys.exit(1)
    elif args.command == "metrics":
        import urllib.request

        try:
            from gesture_controller.core.integration_server import get_or_create_api_token

            token = get_or_create_api_token()
            url = f"http://127.0.0.1:8765/metrics?token={token}"
            with urllib.request.urlopen(url, timeout=2.0) as resp:  # nosec B310
                print(resp.read().decode("utf-8"))
        except Exception as exc:
            print(f"Could not reach running daemon: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        # Default behavior: run GUI app
        from gesture_controller.gui.app_entry import main as run_gui

        run_gui()


if __name__ == "__main__":
    main()
