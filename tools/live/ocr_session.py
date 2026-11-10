"""One private PowerShell OCR worker; no process launch per captured frame."""
import json
from collections import deque
from pathlib import Path
import queue
import subprocess
import threading
from tools.system_process import popen, powershell_script


class OcrSession:
    def __init__(self):
        self.process = None
        self.responses = None
        self.counter = 0
        self.stderr_tail = deque(maxlen=12)
        self.stderr_reader = None

    def _start(self):
        self.process = popen(powershell_script(Path(__file__).with_name("ocr_server.ps1")),
                                        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                        text=True,encoding="utf-8",errors="replace",bufsize=1,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
        responses = self.responses = queue.Queue()
        stderr_tail = self.stderr_tail = deque(maxlen=12)
        process = self.process
        def read_stderr():
            try:
                for line in process.stderr:
                    stderr_tail.append(line.strip()[:256])
            except (ValueError,OSError):
                pass
        self.stderr_reader = threading.Thread(target=read_stderr,daemon=True,name="mayhem-ocr-errors")
        self.stderr_reader.start()
        def reader():
            try:
                for line in process.stdout:
                    responses.put(line)
            except (ValueError,OSError):
                pass
            finally:
                responses.put(None)
        threading.Thread(target=reader,daemon=True,name="mayhem-ocr-responses").start()

    def recognize(self, image, native_titles=False):
        if self.process is None or self.process.poll() is not None:
            self.close()
            self._start()
        self.counter += 1
        try:
            self.process.stdin.write(json.dumps({"id":self.counter,"image":str(Path(image).resolve()),"native_titles":native_titles})+"\n")
            self.process.stdin.flush()
            line = self.responses.get(timeout=8)
            if line is None:
                process = self.process
                try:
                    code = process.wait(timeout=.2)
                except subprocess.TimeoutExpired:
                    code = process.poll()
                if self.stderr_reader:
                    self.stderr_reader.join(timeout=.2)
                detail = " ".join(self.stderr_tail)[-1600:]
                raise RuntimeError(f"OCR worker exited (code={code})"+(": "+detail if detail else ""))
            response = json.loads(line.lstrip("\ufeff"))
            if response.get("id") != self.counter:
                raise RuntimeError("OCR response identity mismatch")
            return response["screen"]
        except Exception:
            self.close()
            raise

    def close(self):
        process, self.process = self.process, None
        if process is not None:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=.5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=.5)
            for reader in (self.stderr_reader,):
                if reader:
                    reader.join(timeout=.2)
            for stream in (process.stdin,process.stdout,process.stderr):
                if stream:
                    stream.close()
