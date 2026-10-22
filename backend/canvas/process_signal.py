"""Probuzení čtenářů živého procesu (docs/zivy-proces.md §5).

Zápis (příjem z kanceláře, záznam činnosti) volá `notify()` z libovolného vlákna; každý
otevřený SSE proud čeká v `wait(generation, timeout)` na svém event loopu. Čítač generací
brání ztracenému probuzení: když se od přečtení `generation` něco zapsalo, `wait` se vrátí
hned. Timeout je pojistka (poll), ne hlavní cesta.
"""
import asyncio
import threading


class ProcessSignal:
    def __init__(self):
        self._lock = threading.Lock()
        self._generation = 0
        self._waiters = set()

    @property
    def generation(self):
        return self._generation

    def notify(self):
        with self._lock:
            self._generation += 1
            waiters = list(self._waiters)
        for loop, event in waiters:
            try:
                loop.call_soon_threadsafe(event.set)
            except RuntimeError:  # loop už skončil; čekatel zmizí ve svém finally
                continue

    async def wait(self, generation, timeout):
        """Vrátí True, když přišel zápis; False po timeoutu."""
        loop = asyncio.get_running_loop()
        event = asyncio.Event()
        key = (loop, event)
        with self._lock:
            if self._generation != generation:
                return True
            self._waiters.add(key)
        try:
            await asyncio.wait_for(event.wait(), timeout)
            return True
        except TimeoutError:
            return False
        finally:
            with self._lock:
                self._waiters.discard(key)

    def waiting(self):
        with self._lock:
            return len(self._waiters)


# Jeden signál na proces: emit_event volají služby bez kontextu aplikace (docs/zivy-proces.md).
PROCESS_SIGNAL = ProcessSignal()
