# Threading Model

```mermaid
graph TD
    Main[Main GUI Thread] -->|Spawns| Cam[Camera Process]
    Main -->|Spawns| Broker[IPC Broker Process]
    Main -->|Spawns| Engine[Engine Thread]
```
