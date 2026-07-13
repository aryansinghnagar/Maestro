# ADR-010: Hot-Reloading and Synchronization Constraints

## Status
Accepted

## Context
Custom plugins and gestures can be modified by the user or third-party packages at runtime. Restarting the master gesture engine process to apply updates is disruptive. We need a way to hot-reload config files and plugin modules without dropping the main camera or FSM tracking loop.

## Decision
We implement a file watcher watchdog thread (`watchdog.observers.Observer`) monitoring the user's plugin directories. When a file modification is detected:
1. The modified file is pre-validated for safety using AST parsing (checking `PLUGIN_META` headers).
2. The plugin is re-imported dynamically.
3. The master `GestureEngine` is notified. FSM lists and configurations are swapped atomically using a shared `threading.RLock()` to prevent race conditions during engine loop iteration.

## Consequences
- **Pros**:
  - Seamless UX: users can edit plugin scripts or YAML configs and see the changes apply instantly without restarting.
  - Robust thread safety, preventing race-condition segfaults.
- **Cons**:
  - Hot reloading requires filesystem write-permission monitoring.
  - AST pre-validation adds slightly more load complexity but prevents syntax errors from crashing the daemon.
