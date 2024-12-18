import sys
import threading
import time
from contextlib import contextmanager


class LiveCounter:
    def __init__(self, action: str, file=sys.stdout):
        self.action = action
        self.file = file
        self.is_running = False
        self.start_time = time.time()

    def run(self):
        self.start_time = time.time()
        while self.is_running:
            elapsed_time = time.time() - self.start_time
            print(
                f"\rWaiting for {self.action}... ({elapsed_time:.1f}s)",
                end="",
                file=self.file,
                flush=True,
            )
            time.sleep(1)

    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def stop(self):
        self.is_running = False
        self.thread.join()
        elapsed_time = time.time() - self.start_time
        print(
            f"\rWaiting for {self.action}... ok ({elapsed_time:.1f}s)",
            file=self.file,
            flush=True,
        )


@contextmanager
def waiting_for(action: str, file=sys.stdout):
    counter = LiveCounter(action, file)
    try:
        counter.start()
        yield
    finally:
        counter.stop()
