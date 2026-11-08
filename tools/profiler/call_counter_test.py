from __future__ import annotations

import sys
import typing

from tools.profiler import call_counter

if typing.TYPE_CHECKING:
    from pathlib import Path


def test_counts_every_call_on_every_thread(tmp_path: Path):
    script = tmp_path / "target.py"
    _ = script.write_text(
        "import sys\n"
        + "import threading\n"
        + "def work():\n"
        + "    pass\n"
        + "def run_twice():\n"
        + "    work()\n"
        + "    work()\n"
        + "threads = [threading.Thread(target=run_twice) for _ in range(3)]\n"
        + "for thread in threads:\n"
        + "    thread.start()\n"
        + "for thread in threads:\n"
        + "    thread.join()\n"
        + "sys.exit(3)\n",
        encoding="utf-8",
        newline="\n",
    )
    counts_path = tmp_path / "calls.json"

    exit_status = call_counter.capture(
        command=(sys.executable, str(script)),
        counts_path=counts_path,
        working_directory=tmp_path,
        environment={},
        stdin=None,
    )

    assert exit_status == 3
    counts = call_counter.load(counts_path)
    assert counts["work"] == 6
    assert counts["run_twice"] == 3
    assert counts["<module target.py>"] == 1
