"""Services package — business logic that lives outside routers.

- events.py: event persistence + rule fan-out (N5)
- pubsub.py: in-process per-user SSE queues (N5, used by N6)
"""