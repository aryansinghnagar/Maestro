# Plugin Architecture

```mermaid
graph LR
    Engine[Engine Coordinator] -->|Load| Loader[Plugin Loader]
    Loader -->|Sandbox| Plugin[Restricted Plugin]
```
