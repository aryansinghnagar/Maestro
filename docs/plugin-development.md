# Plugin Development

Learn how to write custom plugins for Maestro.

## Sandbox Restrictions

Plugins are executed in a RestrictedPython sandbox (or WASM sandboxed runner) with limited capabilities:
- No network access allowed.
- No direct file system modification.
- Communication with the main application is limited to input events.
