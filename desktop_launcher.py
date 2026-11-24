"""Start/open/stop this project from a desktop icon without terminal commands."""
import argparse
import hashlib
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def instance_id(root):
    return hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()[:24]


def health(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health',timeout=.6) as response:
            return json.load(response).get('data',{})
    except (OSError,ValueError,urllib.error.URLError):
        return {}


def state_path(root, demo=False):
    return Path(root) / 'data' / ('desktop-test-server.json' if demo else 'desktop-server.json')


def read_state(root, demo=False):
    try:
        return json.loads(state_path(root, demo).read_text(encoding='utf-8'))
    except (OSError,ValueError):
        return {}


def open_url(url):
    if sys.platform=='darwin':
        subprocess.run(['/usr/bin/open',url],check=True)
    else:
        webbrowser.open(url)


def choose_port():
    for port in range(8765,8790):
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1',port))
                return port
            except OSError:
                continue
    raise RuntimeError('No free local port is available. Close an older Reunite server and try again.')


def _remember_server(root, demo, record):
    path = state_path(root, demo)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(record, stream)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _open_workspace(port, current, state, browser):
    url = f'http://127.0.0.1:{port}/'
    if browser:
        key = state.get('setup_key') if current.get('setup_required') else None
        open_url(url + ('#setup=' + key if key else ''))
    return url


def start(root=ROOT,browser=True,timeout=120,demo=False):
    root=Path(root).resolve();data=root/'data';data.mkdir(parents=True,exist_ok=True)
    expected=instance_id(root);state=read_state(root,demo)
    mode = 'test' if demo else 'live'
    # Reopen the same running copy; never reuse a different project's data.
    for port in dict.fromkeys([state.get('port',8765),8765]):
        if not isinstance(port,int):
            continue
        current=health(port)
        if current.get('application')!='reunite' or current.get('instance')!=expected:
            continue
        owns_server = (state.get('port') == port and state.get('pid') == current.get('pid')
                       and state.get('launch_id') == current.get('launch_id'))
        if current.get('mode')==mode and (not current.get('setup_required') or (owns_server and state.get('setup_key'))):
            if not current.get('setup_required') and state.pop('setup_key', None):
                _remember_server(root, demo, state)
            return _open_workspace(port, current, state, browser)
        if not demo and not current.get('mode') and state.get('port')==port and state.get('pid')==current.get('pid'):
            stop(root)
    port=choose_port()
    venv=root/('.venv/Scripts/python.exe' if os.name=='nt' else '.venv/bin/python')
    python=venv if venv.is_file() else Path(sys.executable)
    options={'start_new_session':True} if os.name!='nt' else {'creationflags':subprocess.CREATE_NO_WINDOW}
    log=data/('desktop-test-launch.log' if demo else 'desktop-launch.log')
    setup_key = None if demo else secrets.token_urlsafe(32)
    # A Windows venv can run the server in a child of the executable we start.
    launch_id = secrets.token_hex(24)
    env = {**os.environ, 'COOKIE_SECURE': '0', 'REUNITE_DESKTOP_LAUNCH_ID': launch_id}
    env.pop('REUNITE_DESKTOP_SETUP_KEY', None)
    if setup_key:
        env['REUNITE_DESKTOP_SETUP_KEY'] = setup_key
    with log.open('ab') as output:
        process=subprocess.Popen([str(python),str(root/'main.py'),'--host','127.0.0.1','--port',str(port),
                                  '--demo' if demo else '--live'], cwd=root,env=env,
                                 stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,**options)
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        current=health(port)
        server_pid = current.get('pid')
        if (current.get('application') == 'reunite' and current.get('instance') == expected
                and current.get('mode') == mode and current.get('launch_id') == launch_id
                and type(server_pid) is int and server_pid > 0):
            record = dict(port=port, pid=server_pid, instance=expected, launch_id=launch_id)
            if current.get('setup_required'):
                record['setup_key'] = setup_key
            _remember_server(root, demo, record)
            return _open_workspace(port, current, record, browser)
        if process.poll() is not None:
            raise RuntimeError(f'Reunite could not start. See data/{log.name} for the reason.')
        time.sleep(.25)
    if process.poll() is None:
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:pass
    raise RuntimeError(f'Startup took too long. See data/{log.name} for the reason.')


def stop(root=ROOT,demo=False):
    root=Path(root).resolve();state=read_state(root,demo)
    port,pid=state.get('port'),state.get('pid')
    if not isinstance(port,int) or not isinstance(pid,int):return False
    current=health(port)
    if (current.get('application')!='reunite' or current.get('instance')!=instance_id(root)
            or current.get('pid')!=pid or current.get('mode') not in ('test' if demo else 'live', None)
            or current.get('launch_id') != state.get('launch_id')):
        return False
    os.kill(pid,signal.SIGTERM)
    for _ in range(40):
        if not health(port):break
        time.sleep(.1)
    state_path(root, demo).unlink(missing_ok=True)
    return True


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--stop',action='store_true')
    parser.add_argument('--demo',action='store_true')
    args=parser.parse_args()
    try:
        if args.stop:
            live_stopped = stop()
            test_stopped = stop(demo=True)
            print('Reunite stopped.' if live_stopped or test_stopped else 'No app-started Reunite server is running for this copy.')
        else:
            print(start(demo=args.demo))
    except Exception as error:
        print(str(error),file=sys.stderr)
        raise SystemExit(1)


if __name__=='__main__':main()
