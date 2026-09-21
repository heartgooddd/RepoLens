"""No model, no third-party support claim: exercise runner lifecycle and boundaries."""
import json
from pathlib import Path
import subprocess
import sys
import time

scenario = sys.argv[1]
run = Path.cwd()
if scenario in ('child', 'timeout'):
    (run / 'model-data').mkdir(exist_ok=True)
    child = subprocess.Popen([sys.executable, '-B', '-c', 'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print("ready",flush=True); time.sleep(60)'], stdout=subprocess.PIPE)
    child.stdout.readline()
    (run / 'model-data/child.json').write_text(json.dumps({'pid': child.pid}))
    print('child ready', flush=True)
    time.sleep(60)
elif scenario == 'nonzero':
    raise SystemExit(37)
elif scenario == 'artifact_link':
    (run / 'output/project').mkdir(parents=True)
    (run / 'output/project/index.md').symlink_to(run / 'input/helper.py')
elif scenario == 'success':
    (run / 'output/project').mkdir(parents=True)
    (run / 'output/project/index.md').write_text(sys.argv[2])
elif scenario == 'metadata':
    metadata = json.load(sys.stdin)
    (run / 'output/project').mkdir(parents=True)
    (run / 'output/project/index.md').write_text(metadata['commit'])
else:
    raise AssertionError('Unknown test fixture scenario')
