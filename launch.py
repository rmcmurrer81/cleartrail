"""Start an app-local ClearTrail server and open its browser workspace."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent


def run():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    port = 8794
    for candidate in range(8794, 8800):
        url = f'http://127.0.0.1:{candidate}'
        try:
            with opener.open(url + '/api/bootstrap', timeout=.5) as response:
                value = json.load(response)
            if value.get('name') == 'ClearTrail' and value.get('version') == '2026.09.07-fixed-4':
                webbrowser.open(url)
                return
        except Exception:
            pass
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', candidate))
                port = candidate
                break
            except OSError:
                continue
    else:
        raise RuntimeError('ClearTrail cannot find a free local port from 8794 to 8799.')
    (ROOT / 'data').mkdir(exist_ok=True)
    log = (ROOT / 'data' / 'startup.log').open('ab')
    creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    process = subprocess.Popen([sys.executable, '-B', str(ROOT / 'server.py'), '--port', str(port), '--no-browser'],
        cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, creationflags=creationflags)
    url = f'http://127.0.0.1:{port}'
    for attempt in range(80):
        if process.poll() is not None:
            raise RuntimeError('ClearTrail stopped during startup. See data/startup.log.')
        try:
            with opener.open(url + '/api/bootstrap', timeout=.5) as response:
                if json.load(response).get('version') == '2026.09.07-fixed-4':
                    webbrowser.open(url)
                    return
        except Exception:
            time.sleep(.15)
    raise RuntimeError('ClearTrail did not finish starting. See data/startup.log.')


if __name__ == '__main__':
    try:
        run()
    except Exception as error:
        if os.name == 'nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(error), 'ClearTrail', 0x10)
        else:
            raise
