# ADR-004: AST-Based Condition Parsing

## Status
Approved

## Context
Gestures are defined in YAML config files where transition triggers require checking mathematical constraints on coordinates and distances (e.g., `index_mcp_y > wrist_y` or `thumb_tip_distance < 0.05`). 

Evaluating these dynamic expression strings at runtime in Python commonly uses `eval()`, which opens a critical security vulnerability (allowing arbitrary code execution if a configuration file is tampered with).

## Decision
We implement a safe expression compiler that parses the string with Python's built-in `ast.parse()`, validates the syntax tree against a strict allow-list of nodes (boolean operators, comparison operators, variables, constants), and compiles it to a python callable.

## Consequences
- **Secure Evaluation:** Disallows arbitrary function execution, attribute access, or system calls, making the app immune to config-injection security exploits.
- **Performance:** Pre-compiling the validated AST node into a Python code object ensures that subsequent evaluations run with minimal CPU overhead.
