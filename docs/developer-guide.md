# Developer Guide

Guide to setting up and contributing to Maestro.

## Local Setup

We use `uv` to manage environments:

```bash
uv sync
```

## Running Verification

```bash
uv run ruff check .
uv run mypy gesture_controller
uv run pytest
```
