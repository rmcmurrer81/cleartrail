"""Copy this stdlib-only module into an app to discover the optional voice pack."""
from pathlib import Path
import json
import os
import queue
import subprocess
import threading
import uuid


class VoiceUnavailable(RuntimeError):
    pass


def discover_pack(app_directory, environment=None):
    environment = os.environ if environment is None else environment
    base = Path(app_directory).resolve()
    configured = environment.get('SARAH_VOICE_PACK')
    candidates = [Path(configured)] if configured else [base/'sarah-voice-pack',base.parent/'sarah-voice-pack']
    for candidate in candidates:
        root = candidate.resolve()
        if all((root/name).is_file() for name in ('pack.json','runtime/python.exe','voice_worker.py','voices.json','model-manifest.json')):
            return root
    return None


class SarahVoiceClient:
    def __init__(self, pack_directory, timeout=180):
        self.root = Path(pack_directory).resolve()
        self.timeout = timeout
        self.process = None
        self.responses = queue.Queue()
        self.lock = threading.Lock()
        self.log = None

    def _start(self):
        if self.process is not None and self.process.poll() is None:
            return
        if not (self.root/'runtime/python.exe').is_file():
            raise VoiceUnavailable('The optional voice runtime is missing. Written conversation remains available.')
        self.responses = queue.Queue()
        self.log = (self.root/'voice-worker.log').open('a',encoding='utf-8')
        environment = {**os.environ,'PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8'}
        environment.pop('PYTHONPATH',None)
        environment.pop('PYTHONHOME',None)
        self.process = subprocess.Popen([str(self.root/'runtime/python.exe'),'-B',str(self.root/'voice_worker.py')],
            cwd=self.root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,encoding='utf-8',
            env=environment,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        process = self.process
        responses = self.responses
        def read():
            for line in process.stdout:
                try:
                    responses.put(json.loads(line))
                except ValueError:
                    responses.put({'ok':False,'error':{'message':'The voice runtime returned an invalid response.'}})
            responses.put(None)
        threading.Thread(target=read,daemon=True).start()

    def request(self, op, **values):
        with self.lock:
            self._start()
            identity = uuid.uuid4().hex
            try:
                self.process.stdin.write(json.dumps({'id':identity,'op':op,**values},ensure_ascii=False)+'\n')
                self.process.stdin.flush()
                response = self.responses.get(timeout=self.timeout)
            except (OSError,queue.Empty) as error:
                self.close()
                raise VoiceUnavailable('The voice runtime timed out or stopped. Written conversation remains available.') from error
            if not response or response.get('id')!=identity:
                self.close()
                raise VoiceUnavailable('The voice runtime stopped or returned a mismatched request.')
            if not response.get('ok'):
                raise VoiceUnavailable(response.get('error',{}).get('message','Local speech could not finish.'))
            result = response['result']
            if op=='speak':
                target = Path(result['wav_path']).resolve()
                if not target.is_relative_to(self.root/'artifacts') or not target.is_file():
                    raise VoiceUnavailable('The voice result is outside the pack artifact folder.')
            return result

    def health(self):
        return self.request('health')

    def speak(self, project_id, text, allow_unapproved=False):
        return self.request('speak',project_id=project_id,text=text,allow_unapproved=allow_unapproved)

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=10)
            self.process = None
        if self.log is not None:
            self.log.close()
            self.log = None

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.close()
