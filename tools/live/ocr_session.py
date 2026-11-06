"""One private PowerShell OCR worker; no process launch per captured frame."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading


class OcrSession:
    def __init__(self):
        self.process = None
        self.responses = None
        self.counter = 0

    def _start(self):
        executable = Path(os.environ.get("SystemRoot","C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        self.process = subprocess.Popen([str(executable),"-NoProfile","-File",str(Path(__file__).with_name("ocr_server.ps1"))],
                                        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                        text=True,encoding="utf-8",errors="replace",bufsize=1,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
        responses = self.responses = queue.Queue()
        process = self.process
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
                raise RuntimeError("OCR worker exited")
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
            for stream in (process.stdin,process.stdout):
                if stream:
                    stream.close()
