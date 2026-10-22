"""Probuzení SSE čtenářů: okamžitě po zápisu, bez ztraceného probuzení."""
import asyncio
import threading
import time

from backend.canvas.process_signal import ProcessSignal


def test_wait_returns_immediately_when_generation_moved():
    signal = ProcessSignal()
    generation = signal.generation
    signal.notify()
    assert asyncio.run(signal.wait(generation, 5)) is True


def test_notify_from_other_thread_wakes_waiter_fast():
    signal = ProcessSignal()

    async def run():
        generation = signal.generation
        threading.Timer(0.02, signal.notify).start()
        started = time.monotonic()
        woke = await signal.wait(generation, 5)
        return woke, time.monotonic() - started

    woke, elapsed = asyncio.run(run())
    assert woke and elapsed < 1
    assert signal.waiting() == 0


def test_wait_times_out():
    signal = ProcessSignal()
    assert asyncio.run(signal.wait(signal.generation, 0.01)) is False
