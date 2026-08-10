"""Short real process used to exercise target-exit observation races."""

import threading
import time

# PRF-032: Real read-race fixture.


def _short_worker() -> None:
    time.sleep(0.0002)


_deadline = time.monotonic() + 1.0
_workers: list[threading.Thread] = []
while time.monotonic() < _deadline:
    _worker = threading.Thread(target=_short_worker)
    _worker.start()
    _workers.append(_worker)
    if len(_workers) > 8:
        _workers.pop(0).join()
for _worker in _workers:
    _worker.join()
