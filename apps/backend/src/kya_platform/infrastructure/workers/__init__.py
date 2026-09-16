"""Worker persistence adapters."""

from kya_platform.infrastructure.workers.outbox_queue import DatabaseOutboxQueue

__all__ = ["DatabaseOutboxQueue"]
