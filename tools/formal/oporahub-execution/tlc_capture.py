"""Bounded output/deadline for one owned child; not a process-tree sandbox."""
import os
import queue
import subprocess
import threading
import time

MAX_OUTPUT = 2 * 1024 * 1024


def clean_environment():
    blocked = {'JAVA_TOOL_OPTIONS', 'JDK_JAVA_OPTIONS', '_JAVA_OPTIONS', 'CLASSPATH', 'JAVA_OPTIONS', 'JAVA_OPTS', 'JDK_JAVAC_OPTIONS'}
    return {key: value for key, value in os.environ.items() if key.upper() not in blocked}


def capture(command, cwd, timeout, *, limit=MAX_OUTPUT):
    process = subprocess.Popen(command, cwd=cwd, env=clean_environment(), stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
    chunks = queue.Queue(maxsize=8)
    stop = threading.Event()

    def drain():
        try:
            while not stop.is_set():
                data = process.stdout.read1(8192)
                while not stop.is_set():
                    try:
                        chunks.put(data, timeout=.1)
                        break
                    except queue.Full:
                        pass
                if not data:
                    return
        finally:
            process.stdout.close()

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    deadline, output, reason = time.monotonic() + timeout, bytearray(), None
    try:
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                reason = 'wall-timeout'
                break
            try:
                data = chunks.get(timeout=min(.1, left))
            except queue.Empty:
                continue
            if not data:
                break
            if len(output) + len(data) > limit:
                output.extend(data[:limit - len(output)])
                reason = 'output-limit; retained prefix is incomplete'
                break
            output.extend(data)
        if reason:
            process.kill()
        try:
            code = process.wait(timeout=max(.1, deadline - time.monotonic()) if not reason else 5)
        except subprocess.TimeoutExpired:
            reason = reason or 'wall-timeout'
            process.kill()
            code = process.wait(timeout=5)
    finally:
        stop.set()
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        reader.join(timeout=1)
    return code, bytes(output), reason
