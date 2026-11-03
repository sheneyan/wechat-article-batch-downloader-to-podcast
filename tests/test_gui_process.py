import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
import time
from pathlib import Path


class GuiProcessTests(unittest.TestCase):
    def test_foundation_style_process_group_leader_can_start_gui_bridge(self):
        with tempfile.TemporaryDirectory() as tmp:
            request=dict(action='dashboard',library=tmp+'/library',config=tmp+'/config.json')
            result=subprocess.run([sys.executable,'-m','wechat2podcast.gui'],
                        input=json.dumps(request),text=True,capture_output=True,start_new_session=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['articles'],[])

    def test_cancel_stops_the_bridge_child_process_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker=Path(tmp)/'child.pid'
            child='import os,pathlib,time; pathlib.Path('+repr(str(marker))+').write_text(str(os.getpid())); time.sleep(60)'
            code=('import subprocess,sys; import wechat2podcast.gui as g; '
                  'g.handle=lambda req: subprocess.run([sys.executable,"-c",'+repr(child)+'],check=True); g.main()')
            process=subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,text=True,start_new_session=True)
            try:
                process.stdin.write(json.dumps(dict(action='test',library=tmp,config=tmp+'/config.json')))
                process.stdin.close()
                deadline=time.monotonic()+5
                while not marker.exists() and time.monotonic()<deadline:
                    time.sleep(0.02)
                self.assertTrue(marker.exists(),'child failed to start')
                child_pid=int(marker.read_text())
                process.terminate()
                process.wait(timeout=5)
                with self.assertRaises(ProcessLookupError):
                    os.kill(child_pid,0)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid,signal.SIGKILL)
                    process.wait()
                process.stdout.close()
                process.stderr.close()


if __name__ == '__main__':
    unittest.main()
