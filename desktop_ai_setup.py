"""Local browser progress page for one-time model preparation; no Terminal UI."""
import json
import secrets
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from desktop_launcher import open_url,start,stop

ROOT=Path(__file__).resolve().parent
HTML='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Reunite / AI setup</title><style>body{margin:0;background:#f7f5ef;color:#553442;font:16px/1.7 system-ui}main{max-width:760px;margin:7vh auto;padding:30px}h1{font:42px Georgia}p{color:#79666b}.tag{color:#a78a58;letter-spacing:2px;font-size:11px}pre{background:#fffdf8;border:1px solid #e2d4be;border-radius:12px;padding:22px;white-space:pre-wrap;max-height:340px;overflow:auto;font:12px/1.6 monospace}a{color:#800020}.spinner{width:26px;height:26px;border:2px solid #dbc8a4;border-top-color:#800020;border-radius:50%;animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){.spinner{animation:none}}</style><main><span class="tag">REUNITE / ONE-TIME PREPARATION</span><h1 id="heading">Preparing local AI.</h1><div class="spinner" id="spinner"></div><p id="message">Downloading the AI dependencies and public model. This can take several minutes. Your photos and reports are not uploaded. You can keep using the website with typed matching while this finishes.</p><pre id="log">Starting setup...</pre><p><a id="open" hidden>Open Reunite</a></p></main><script>async function check(){try{const r=await fetch(location.pathname+'/status');const s=await r.json();document.querySelector('#log').textContent=s.log||'Preparing...';if(s.state!=='working'){document.querySelector('#spinner').hidden=true;document.querySelector('#heading').textContent=s.state==='ready'?'Ready for a little more.':'Setup needs attention.';document.querySelector('#message').textContent=s.state==='ready'?'Local AI is prepared and Reunite has restarted. Future matching runs on this Mac.':(s.error || 'Check the installation log below.');if(s.url){const a=document.querySelector('#open');a.href=s.url;a.hidden=false}return}}catch(e){}setTimeout(check,1200)}check()</script></html>'''


def main():
    token=secrets.token_urlsafe(24);state={'state':'working','url':''}
    folder=ROOT/'data';folder.mkdir(exist_ok=True);log=folder/'ai-setup.log'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.headers.get('Host','').split(':')[0] not in ('127.0.0.1','localhost'):
                self.send_error(403);return
            if self.path=='/'+token:
                raw=HTML.encode();mime='text/html; charset=utf-8'
            elif self.path=='/'+token+'/status':
                try:tail=log.read_text(encoding='utf-8',errors='replace')[-10000:]
                except OSError:tail='Starting...'
                raw=json.dumps(dict(state,log=tail)).encode();mime='application/json'
            else:self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Cache-Control','no-store')
            self.send_header('X-Frame-Options','DENY');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    def work():
        try:
            with log.open('w',encoding='utf-8') as output:
                result=subprocess.run([sys.executable,str(ROOT/'setup_ai.py')],cwd=ROOT,
                                      stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT)
            if result.returncode:
                lines = log.read_text(encoding='utf-8', errors='replace').splitlines()
                reason = next((line for line in reversed(lines) if line.startswith('ERROR:')), '')
                raise RuntimeError(reason or 'Setup failed. See the error in the installation log.')
            stop(ROOT)
            state['url']=start(ROOT,browser=False);state['state']='ready'
        except Exception as error:
            state['error'] = str(error)
            with log.open('a',encoding='utf-8') as output:output.write('\n'+str(error)+'\n')
            state['state']='failed'
        finally:
            timer=threading.Timer(300,server.shutdown);timer.daemon=True;timer.start()
    threading.Thread(target=work,daemon=True).start()
    open_url('http://127.0.0.1:'+str(server.server_port)+'/'+token)
    try:server.serve_forever()
    finally:server.server_close()


if __name__=='__main__':main()
