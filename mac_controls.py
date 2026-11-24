"""Small native controls menu; AI preparation uses a browser progress window."""
import subprocess
import sys
from pathlib import Path
from desktop_launcher import start,stop

ROOT=Path(__file__).resolve().parent


def alert(message):
    subprocess.run(['/usr/bin/osascript','-e','on run argv\ndisplay dialog (item 1 of argv) with title "Reunite" buttons {"OK"} default button "OK"\nend run',message])


if __name__=='__main__':
    menu='choose from list {"Open website", "Open testing workspace", "Stop servers", "Open saved files", "Set up local AI"} with title "Reunite controls" with prompt "What would you like to do?" default items {"Open website"}'
    result=subprocess.run(['/usr/bin/osascript','-e',menu],capture_output=True,text=True)
    selected=result.stdout.strip()
    try:
        if selected=='Open website':start()
        elif selected=='Open testing workspace':start(demo=True)
        elif selected=='Stop servers':
            live_stopped = stop()
            test_stopped = stop(demo=True)
            alert('Reunite stopped.' if live_stopped or test_stopped else 'No server started by this app is currently running.')
        elif selected=='Open saved files':
            (ROOT/'data').mkdir(exist_ok=True)
            subprocess.run(['/usr/bin/open',str(ROOT/'data')],check=True)
        elif selected=='Set up local AI':
            log=ROOT/'data/ai-setup-launch.log';log.parent.mkdir(exist_ok=True)
            with log.open('ab') as output:
                subprocess.Popen([sys.executable,str(ROOT/'desktop_ai_setup.py')],cwd=ROOT,
                                 stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
    except Exception as error:alert(str(error))
