from collections import deque
from typing import Iterable, Optional

class RequestQueue:
    def __init__(self, seed_items: Optional[Iterable[str]] = None):
        self._dq = deque(seed_items or [])

    @property
    def size(self) -> int:
        return len(self._dq)

    def is_empty(self) -> bool:
        return not self._dq

    def push(self, item: str):
        self._dq.append(item)

    def pop(self) -> str:
        return self._dq.popleft()