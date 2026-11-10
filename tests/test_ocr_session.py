import io
import json
import unittest
from unittest.mock import patch

from tools.live.ocr_session import OcrSession


class Process:
    def __init__(self, stdout='', stderr='', code=1):
        self.stdin = io.StringIO()
        self.stdout = io.StringIO(stdout)
        self.stderr = io.StringIO(stderr)
        self.code = code
        self.finished = False

    def poll(self):return self.code if self.finished else None
    def wait(self, timeout=None):self.finished = True;return self.code
    def terminate(self):self.finished = True
    def kill(self):self.finished = True


class OcrStartupTests(unittest.TestCase):
    def test_worker_reports_exit_code_and_bounded_stderr(self):
        process = Process(stderr='policy blocked shipped script\n'+'x'*3000+'\n', code=7)
        session = OcrSession()
        with patch('tools.live.ocr_session.popen',return_value=process):
            with self.assertRaisesRegex(RuntimeError,'code=7.*policy blocked') as error:
                session.recognize('unused.bmp')
        self.assertLess(len(str(error.exception)),1700)
        self.assertIsNone(session.process)
        self.assertTrue(process.stderr.closed)

    def test_worker_uses_process_policy_and_can_restart_after_exit(self):
        first = Process(stderr='Startup failure\n')
        second = Process(stdout=json.dumps({'id':2,'screen':{'ocr_status':'recognized'}})+'\n')
        session = OcrSession()
        with patch('tools.live.ocr_session.popen',side_effect=[first,second]) as launch:
            with self.assertRaisesRegex(RuntimeError,'Startup failure'):
                session.recognize('unused.bmp')
            self.assertEqual(session.recognize('unused.bmp')['ocr_status'],'recognized')
            for call in launch.call_args_list:
                args = call.args[0]
                self.assertEqual(args[args.index('-ExecutionPolicy')+1],'Bypass')
                self.assertIn('-NonInteractive',args)
            session.close()
