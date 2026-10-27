"""Watchdog probe (run in its own process by test_app_core.py).

Builds an AppCore whose pipeline thread hangs forever (never checks
the stop event), then calls shutdown(). The requirement (PLAN.md
§2 J6): the process must die anyway (join timeout -> os._exit).
Exit code 0 means the process died on time; exit code 1 means
shutdown() returned without killing the process (a defect).
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.environ["TOUCHLESS_SRC"])

import numpy as np

from touchless.app import AppCore
from touchless.camera import Camera, FakeCapture
from touchless.injection import FakeBackend, Injector
from touchless.logging import EventLogger
from touchless.model import FakeLandmarker
from touchless.settings import Settings
from touchless.state import State


class HungCore(AppCore):
    def _pipeline_loop(self):
        time.sleep(3600)  # hung: never checks the stop event


def main() -> int:
    settings = Settings()
    logger = EventLogger(directory="/tmp/touchless-probe-logs", enabled=False)
    camera = Camera(FakeCapture(frames=[np.zeros((480, 640, 3), dtype=np.uint8)]))
    backend = FakeBackend()
    core = HungCore(settings, logger, camera, lambda p: FakeLandmarker([]),
                    Injector(backend), clock=time.monotonic)
    core.state.transition(State.PAUSED)
    core._pipeline_thread = threading.Thread(target=core._pipeline_loop, daemon=True)
    core._pipeline_thread.start()
    time.sleep(0.2)
    core.shutdown()  # must force-exit via os._exit(0) within ~3 s
    print("ERROR: shutdown returned without exiting", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
