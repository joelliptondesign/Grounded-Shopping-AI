#!/usr/bin/env python3
"""Run unit tests and deterministic evaluations in a temporary source snapshot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def source_snapshot(root, target):
    names = subprocess.check_output(['git', 'ls-files', '-c', '-o', '--exclude-standard', '-z'], cwd=root).decode().split('\0')
    hashes = {}
    for name in sorted(set(names) - {''}):
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError('Invalid source path')
        if any(part.startswith('.env') for part in rel.parts) or rel.parts[0] in {'.git', '.kilo', '.venv', '.vercel', 'artifacts', 'logs', 'telemetry', '__pycache__'}:
            continue
        src = root / rel
        if src.is_symlink() or any(p.is_symlink() for p in src.parents if p != root and root in p.parents):
            raise ValueError('Source symlink requires explicit handling: ' + name)
        if not src.exists():
            continue  # tracked deletion
        if not src.is_file():
            raise ValueError('Unsupported source entry: ' + name)
        data = src.read_bytes()
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    return hashes

def result_code(results):
    return 1 if any(code != 0 for code in results.values()) else 0

# Runs trusted repository tests, not a sandbox for hostile code. Network denial
# applies to this Python process; test-spawned subprocesses are not sandboxed.
CHILD = r'''
import os,sys,runpy,socket,unittest
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import dotenv
dotenv.load_dotenv=lambda *a,**k:False
os.environ.pop('OPENAI_API_KEY',None)
def blocked(*a,**k): raise RuntimeError('Network disabled for Groundwork offline verification')
socket.socket.connect=blocked
socket.socket.connect_ex=blocked
socket.create_connection=blocked
mode=sys.argv[1]
if mode=='unit':
 result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests'))
 raise SystemExit(0 if result.wasSuccessful() else 1)
sys.argv=['evals/runner.py','--deterministic-only']
runpy.run_path('evals/runner.py',run_name='__main__')
'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', choices=['unit', 'eval', 'all'], default='all')
    args = parser.parse_args()
    output = Path(tempfile.mkdtemp(prefix='groundwork-offline-'))
    source = output / 'source'
    source.mkdir()
    hashes = source_snapshot(ROOT, source)
    (output / 'run.py').write_text(CHILD)
    # An explicit small environment avoids passing model keys and other secrets.
    env = {key: os.environ[key] for key in ('PATH','SYSTEMROOT','WINDIR','LANG','LC_ALL','TMPDIR') if key in os.environ}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    results = {}
    modes = ['unit','eval'] if args.only == 'all' else [args.only]
    for mode in modes:
        with (output / (mode + '.log')).open('w') as log:
            try:
                result = subprocess.run([sys.executable, str(output/'run.py'), mode], cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=300)
                results[mode] = result.returncode
            except subprocess.TimeoutExpired:
                results[mode] = 124
        print(mode + ': ' + ('PASS' if results[mode] == 0 else 'FAIL (see log)'))
    record = {'source_root':str(ROOT),'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'source_hashes':hashes,'results':results,'mode':'offline; no live model calls','output_directory':str(output)}
    (output/'summary.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Evidence: ' + str(output))
    if result_code(results):
        print('Offline verification is not green. Known baseline failures remain failures; inspect the generated report for new regressions.')
    return result_code(results)

if __name__ == '__main__':
    raise SystemExit(main())
