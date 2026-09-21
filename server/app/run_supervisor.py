"""Kill the whole job process group if the owning API process dies (POSIX)."""
import json
import os
import signal
import subprocess
import sys
import threading
import time

parent = int(sys.argv[1])
command = json.loads(sys.argv[2])


def watch_parent():
    while True:
        if os.getppid() != parent:
            os.killpg(os.getpgrp(), signal.SIGKILL)
        time.sleep(0.1)


threading.Thread(target=watch_parent, daemon=True).start()
process = subprocess.Popen(command, stdin=sys.stdin)
raise SystemExit(process.wait())
