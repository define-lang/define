"""Short real process used to exercise target-exit observation races."""

import threading
import time

# PRF-032: Real read-race fixture.


def _short_worker() -> None:
    time.sleep(0.0002)


# PRF-032: Real read-race fixture. Process CPU time excludes profiler pauses so
# the short-lived threads remain available across several observations.
_deadline = time.process_time() + 0.2
_workers: list[threading.Thread] = []
while time.process_time() < _deadline:
    _worker = threading.Thread(target=_short_worker)
    _worker.start()
    _workers.append(_worker)
    if len(_workers) > 64:
        _workers.pop(0).join()
for _worker in _workers:
    _worker.join()
