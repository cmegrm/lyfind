"""Copy bundled code/runtime to stable, writable Mac application support storage."""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def install(source,runtime,home=None):
    source,runtime=Path(source).resolve(),Path(runtime).resolve()
    home=Path(home) if home else Path.home()/'Library/Application Support/Reunite'
    home.mkdir(parents=True,exist_ok=True)
    # Never copy or replace user state from an app bundle.
    excluded={'data','.env','.venv','models','__pycache__','.git'}
    for file in source.rglob('*'):
        rel=file.relative_to(source)
        if any(part in excluded for part in rel.parts) or not file.is_file():continue
        target=home/rel;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(file,target)
    arch=platform.machine()
    destination=home/'runtime'/arch/'python'
    executable=destination/'bin/python3.12'
    if not executable.exists():
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(runtime,destination,dirs_exist_ok=True,symlinks=True)
    executable.chmod(executable.stat().st_mode|0o755)
    return home,executable


if __name__=='__main__':
    try:
        home,python=install(sys.argv[1],sys.argv[2])
        subprocess.run([str(python),str(home/'desktop_launcher.py')],cwd=home,check=True)
    except Exception as error:
        print('Reunite could not start: '+str(error),file=sys.stderr)
        raise SystemExit(1)
