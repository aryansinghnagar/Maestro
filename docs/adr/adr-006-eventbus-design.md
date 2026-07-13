# ADR-006: Threading vs IPC for the EventBus

## Status
Accepted

## Context
The application contains multiple threads and processes (e.g. GUI thread, Engine thread, Camera process). We need to decide how events (such as gesture triggers, camera disconnection, config updates) are communicated between them:
1. **In-process Synchronous EventBus**: A simple publish-subscribe broker running within the main process.
2. **Inter-Process Communication (IPC)**: Sockets, pipes, or message queues (like ZeroMQ or multiprocessing.Queue).

## Decision
We choose an in-process, synchronous EventBus for coordination between the GUI thread and the Engine thread. To handle multi-process camera frame updates, we bypass the EventBus and use dedicated `multiprocessing.shared_memory` to avoid serialization overhead. The in-process EventBus publishes events synchronously, and thread-safety is guaranteed by implementing thread-safe Qt Signal bridges (`GuiEventBridge`) to marshal updates to the GUI main thread.

## Consequences
- **Pros**:
  - Negligible latency and zero serialization overhead for internal state communication.
  - Simple API with standard subscriber callback registration.
- **Cons**:
  - Event publishing blocks the calling thread, requiring subscribers to keep handler execution extremely fast.
  - Requires thread bridges (e.g., `QObject` signals) to update PyQt widgets safely from the engine thread.
