"""Cache em memória limitado, seguro para uso concorrente."""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable, Hashable


class BoundedCache[KeyT: Hashable, ValueT]:
    """LRU simples baseado em ``OrderedDict``.

    A chave deve incluir mtime/tamanho do arquivo para que alterações no disco
    invalidem naturalmente a entrada.
    """

    def __init__(self, max_entries: int) -> None:
        self._max_entries = max(1, max_entries)
        self._entries: OrderedDict[KeyT, ValueT] = OrderedDict()
        self._lock = threading.Lock()

    def get_or_load(self, key: KeyT, loader: Callable[[], ValueT]) -> ValueT:
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
                return self._entries[key]

        value = loader()

        with self._lock:
            self._entries[key] = value
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
        return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
