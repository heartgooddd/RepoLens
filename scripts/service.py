"""Run Uvicorn on the launcher's reserved loopback socket; exit if owner dies."""
import os
from pathlib import Path
import signal
import sys
import threading
import time

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))


def watch_parent(parent):
    while os.getppid() == parent:
        time.sleep(.2)
    os.kill(os.getpid(), signal.SIGTERM)
    time.sleep(15)
    os.kill(os.getpid(), signal.SIGKILL)


if __name__ == '__main__':
    threading.Thread(target=watch_parent, args=(int(sys.argv[1]),), daemon=True).start()
    uvicorn.run('app.main:app', host='127.0.0.1', fd=int(sys.argv[2]), workers=1, timeout_graceful_shutdown=10)
