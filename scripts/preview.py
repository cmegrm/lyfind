"""Serve the isolated CSA interface demo, without loading the main application.

Run from the project root: python3 scripts/preview.py
The demo is also usable by opening previews/csa-interface/index.html directly.
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PREVIEW = Path(__file__).resolve().parents[1] / 'previews' / 'csa-interface'


class PreviewHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_POST(self):
        self.send_error(405, 'This is a static interface preview.')


def main():
    parser = argparse.ArgumentParser(description='Open the isolated LyFind CSA interface demo')
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    handler = partial(PreviewHandler, directory=str(PREVIEW))
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler)
    except OSError as error:
        raise SystemExit(f'Could not start the preview: {error}. Try --port 8767.') from None
    print(f'LyFind CSA interface demo: http://127.0.0.1:{args.port}', flush=True)
    print('Fictional records only. The main website and its database are unchanged.', flush=True)
    print('Press Control+C to stop the preview.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
