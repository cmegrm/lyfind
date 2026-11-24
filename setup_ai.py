"""Cross-platform one-time AI setup in an isolated project environment."""
import os
import subprocess
import sys
from pathlib import Path

root=Path(__file__).resolve().parent
if sys.version_info < (3,10):
    raise SystemExit('Install Python 3.10 or newer before preparing local AI.')
env=root/'.venv'
python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
if not python.exists():
    subprocess.run([sys.executable,'-m','venv',str(env)],check=True)
def run(*args):
    subprocess.run([str(python),*args],check=True,cwd=root)
os.environ['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'
print('Updating pip in the Reunite environment...', flush=True)
run('-m', 'pip', 'install', '--upgrade', 'pip')
print('Installing AI libraries...', flush=True)
if sys.platform=='darwin':
    # Resolve PyTorch, NumPy and downstream libraries together when repairing an existing install.
    run('-m','pip','install','--only-binary=:all:','-r','requirements-ai.txt')
    run('-m','pip','check')
else:
    run('-m','pip','install','torch','torchvision','--index-url','https://download.pytorch.org/whl/cpu')
    run('-m','pip','install','-r','requirements-ai.txt')
run('prepare_ai.py')
