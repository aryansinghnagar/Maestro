import os
import re
import json
import yaml
import shutil
import zipfile
import platform
import structlog
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = structlog.get_logger(__name__)


def get_user_data_dirs() -> List[Path]:
    """Get list of platform-specific data and config directories for Maestro."""
    dirs = []
    
    # 1. Config directory (cross-platform equivalent)
    if platform.system() == "Windows":
        base_config = Path(os.environ.get("APPDATA", "")) / "gesture_controller"
    elif platform.system() == "Darwin":
        base_config = Path.home() / "Library" / "Application Support" / "gesture_controller"
    else:
        base_config = Path.home() / ".config" / "gesture_controller"
    dirs.append(base_config)
    
    # 2. Local share directory (Linux specific)
    if platform.system() == "Linux":
        dirs.append(Path.home() / ".local" / "share" / "gesture_controller")
        
    return dirs


def erase_data() -> None:
    """Delete all local files and configuration directories associated with Maestro (Right to Erasure)."""
    target_dirs = get_user_data_dirs()
    for d in target_dirs:
        if d.exists():
            try:
                shutil.rmtree(d)
                logger.info("Successfully erased directory", path=str(d))
            except Exception as e:
                logger.error("Failed to erase directory", path=str(d), error=str(e))


def sanitize_config_text(content: str) -> str:
    """Sanitize config YAML content, redacting hotkeys and simulated actions."""
    try:
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            return content
            
        def redact_rec(obj: Any) -> Any:
            if isinstance(obj, dict):
                new_dict = {}
                for k, v in obj.items():
                    # Redact hotkeys or action values
                    if k in ("actions", "hotkey", "key", "keys") or (isinstance(v, str) and any(
                        v.startswith(prefix) for prefix in ("KeyPress:", "OS:", "MouseClick:", "MouseScroll:", "Media:")
                    )):
                        new_dict[k] = "[REDACTED]"
                    else:
                        new_dict[k] = redact_rec(v)
                return new_dict
            elif isinstance(obj, list):
                return [redact_rec(item) for item in obj]
            return obj
            
        redacted_data = redact_rec(data)
        return yaml.dump(redacted_data, default_flow_style=False)
    except Exception:
        # Fallback to regex replacement if YAML parsing fails
        lines = []
        for line in content.splitlines():
            if re.search(r'(KeyPress:|OS:|MouseClick:|MouseScroll:|Media:)', line):
                line = re.sub(r'(:["\']?)(KeyPress:|OS:|MouseClick:|MouseScroll:|Media:)[^"\']*', r'\1[REDACTED]', line)
            lines.append(line)
        return "\n".join(lines)


def redact_logs_text(content: str) -> str:
    """Redact logs to strip application names, gesture names, and action simulations."""
    app_pattern = re.compile(r'\b[a-zA-Z0-9_\-]+\.exe\b|\b(chrome|firefox|safari|finder|explorer|notepad|cmd|powershell)\b', re.IGNORECASE)
    gesture_pattern = re.compile(r'\b(SwipeLeft|SwipeRight|SwipeUp|SwipeDown|Fist|HoldFist|MinimizeWindow|CustomCopy)\b', re.IGNORECASE)
    
    redacted_lines = []
    for line in content.splitlines():
        try:
            data = json.loads(line)
            if isinstance(data, dict):
                for key in list(data.keys()):
                    if key in ("app", "gesture", "action", "details", "message"):
                        val = data[key]
                        if isinstance(val, str):
                            val = app_pattern.sub("[REDACTED]", val)
                            val = gesture_pattern.sub("[REDACTED]", val)
                            if key == "action" or any(p in val for p in ("KeyPress:", "OS:", "MouseClick:", "MouseScroll:", "Media:")):
                                val = "[REDACTED]"
                            data[key] = val
                        elif isinstance(val, dict):
                            for subk, subv in val.items():
                                if isinstance(subv, str):
                                    subv = app_pattern.sub("[REDACTED]", subv)
                                    subv = gesture_pattern.sub("[REDACTED]", subv)
                                    if any(p in subv for p in ("KeyPress:", "OS:", "MouseClick:", "MouseScroll:", "Media:")):
                                        subv = "[REDACTED]"
                                    val[subk] = subv
                redacted_lines.append(json.dumps(data))
                continue
        except json.JSONDecodeError:
            pass
            
        # Plaintext redactions
        line = app_pattern.sub("[REDACTED]", line)
        line = gesture_pattern.sub("[REDACTED]", line)
        line = re.sub(r'action=["\'].*?["\']', 'action="[REDACTED]"', line)
        line = re.sub(r'(KeyPress:|OS:|MouseClick:|MouseScroll:|Media:)[^ "\']*', '[REDACTED]', line)
        redacted_lines.append(line)
        
    return "\n".join(redacted_lines)


def get_plugins_metadata(plugins_dir: Path) -> List[Dict[str, Any]]:
    """Scan the plugins directory and return list of metadata instead of source code."""
    from gesture_controller.plugins.plugin_loader import PluginLoader
    loader = PluginLoader(None)
    
    plugins_meta = []
    if not plugins_dir.exists():
        return []
        
    # Discover python plugins
    for py_file in plugins_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        try:
            meta = loader._extract_meta_without_exec(py_file)
            if meta:
                plugins_meta.append({
                    "name": meta.get("name", py_file.stem),
                    "version": meta.get("version", "unknown"),
                    "description": meta.get("description", ""),
                    "author": meta.get("author", "")
                })
        except Exception:
            pass
            
    # Discover WASM plugins
    for sub_dir in plugins_dir.iterdir():
        manifest_path = sub_dir / "maestro.toml"
        if sub_dir.is_dir() and manifest_path.exists():
            try:
                # Try tomllib
                tomllib_mod = None
                try:
                    import tomllib
                    tomllib_mod = tomllib
                except ImportError:
                    pass
                    
                if tomllib_mod:
                    with open(manifest_path, "rb") as f:
                        config = tomllib_mod.load(f)
                    plugins_meta.append({
                        "name": config["plugin"]["name"],
                        "version": config["plugin"]["version"],
                        "description": config["plugin"].get("description", ""),
                        "author": config["plugin"].get("author", "")
                    })
            except Exception:
                pass
                
    return plugins_meta


def export_data(output_zip_path: Path) -> None:
    """Create a sanitized/redacted ZIP archive of Maestro configuration and data."""
    target_dirs = get_user_data_dirs()
    if not target_dirs:
        raise RuntimeError("Could not determine config directory")
        
    config_dir = target_dirs[0]
    
    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # 1. Sanitize and write config.yaml
        config_path = config_dir / "config.yaml"
        if config_path.exists():
            try:
                config_content = config_path.read_text(encoding="utf-8")
                sanitized_config = sanitize_config_text(config_content)
                zipf.writestr("config.yaml", sanitized_config)
            except Exception as e:
                logger.error("Failed to export sanitized config", error=str(e))
                
        # 2. Redact and write logs
        logs_dir = config_dir / "logs"
        if logs_dir.exists():
            for log_file in logs_dir.glob("*.log"):
                if log_file.is_file():
                    try:
                        log_content = log_file.read_text(encoding="utf-8")
                        redacted_logs = redact_logs_text(log_content)
                        zipf.writestr(f"logs/{log_file.name}", redacted_logs)
                    except Exception as e:
                        logger.error("Failed to export redacted logs", path=str(log_file), error=str(e))
                        
        # 3. Write custom templates (no sensitive data)
        templates_dir = config_dir / "templates"
        if templates_dir.exists():
            for t_file in templates_dir.glob("**/*"):
                if t_file.is_file():
                    zipf.write(t_file, arcname=f"templates/{t_file.relative_to(templates_dir)}")
                    
        # 4. Write plugins metadata list (not actual source code)
        plugins_dir = config_dir / "plugins"
        if plugins_dir.exists():
            try:
                plugins_list = get_plugins_metadata(plugins_dir)
                zipf.writestr("plugins/plugins_list.json", json.dumps(plugins_list, indent=2))
            except Exception as e:
                logger.error("Failed to export plugins list", error=str(e))
