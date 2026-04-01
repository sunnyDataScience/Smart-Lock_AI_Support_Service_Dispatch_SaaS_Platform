"""Structured trace emitter for graph nodes.

Stub -- Phase 1 implementation.
"""

import functools
from datetime import datetime


def traced(node_name: str):
    """Decorator that emits structured trace events for any graph node.

    Phase 1: replaces scattered print() with JSON-structured logging.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(state, *args, **kwargs):
            start = datetime.now()
            try:
                result = await func(state, *args, **kwargs)
                duration_ms = (datetime.now() - start).total_seconds() * 1000
                # Phase 1: emit to structured logger / harness_traces table
                print(f"  [trace] {node_name} ok ({duration_ms:.0f}ms)")
                return result
            except Exception as e:
                duration_ms = (datetime.now() - start).total_seconds() * 1000
                print(f"  [trace] {node_name} error ({duration_ms:.0f}ms): {e}")
                raise
        return wrapper
    return decorator
